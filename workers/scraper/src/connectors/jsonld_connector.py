"""Farmacias Ahumada — SFCC storefront scraped through schema.org JSON-LD.

Ahumada runs Salesforce Commerce Cloud but, unlike Cruz Verde, exposes no
usable public OCAPI client_id. Its robots.txt also disallows any URL carrying
`start`, which rules out the Search-UpdateGrid pagination endpoint. Sitemap
discovery is the only sanctioned bulk route and robots.txt advertises it
explicitly, so that is what we use.

Every product detail page embeds a complete schema.org Product block, so we
discover URLs from the sitemap and read price/stock from the JSON-LD. No
browser needed.

Throughput matters here in a way it does not for the API-backed chains: a
product page is ~590 KB and the catalog is ~5.4k pages. Crawling that
sequentially with a per-request delay took ~95 minutes, during which the
scheduler's DB session sat idle waiting for the first 500-product batch and
got dropped by Cloud SQL — which is why this connector had never written a
row. Bounded concurrency (see `scrape_products`) brings a full run to ~10
minutes and keeps batches flowing to the writer.
"""
import json
import re
from dataclasses import dataclass
from html import unescape
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, fetch_sitemap_urls, gather_limited, get_text

JSONLD_RE = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)

# The "Ficha Técnica" tab renders as <h3>■ Label</h3><p>value</p> pairs. This is
# the only place Ahumada names the active ingredient and the real laboratory.
DETAIL_PAIR_RE = re.compile(
    r"<h3[^>]*>\s*(?:■\s*)?([^<]+?)\s*</h3>\s*<p>\s*(.*?)\s*</p>",
    re.IGNORECASE | re.DOTALL,
)
BREADCRUMB_RE = re.compile(
    r'<ol[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>(.*?)</ol>', re.IGNORECASE | re.DOTALL
)
BREADCRUMB_ITEM_RE = re.compile(r"<a[^>]*href=\"[^\"]*\"[^>]*>(.*?)</a>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

# Ficha Técnica labels worth keeping, keyed by accent-stripped lowercase label.
DETAIL_LABELS: dict[str, str] = {
    "principios activos": "activeIngredient",
    "principio activo": "activeIngredient",
    "laboratorio": "laboratory",
    "presentacion": "presentation",
    "formato": "format",
    "dosis": "dose",
    "via de administracion": "route",
}

# Long prose ("Almacenamiento", "Precauciones") is not identity — cap what we keep.
MAX_ATTRIBUTE_LEN = 300

_ACCENTS = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")


def _clean(raw: str) -> str:
    """Strip tags/entities/whitespace out of an HTML fragment."""
    return re.sub(r"\s+", " ", unescape(TAG_RE.sub(" ", raw))).strip()


def _normalize_label(label: str) -> str:
    return _clean(label).translate(_ACCENTS).lower()


@dataclass
class JsonLdConfig:
    chain: str
    base_url: str
    sitemap_url: str
    product_sitemap_marker: str = "product"
    # Bounded concurrency, mirroring farmaloop_connector. 4 in-flight requests is
    # roughly what a couple of real browsers open and keeps a full run ~10 min.
    concurrency: int = 4
    chunk_size: int = 100


JSONLD_CONFIGS: dict[str, JsonLdConfig] = {
    "ahumada": JsonLdConfig(
        chain="ahumada",
        base_url="https://www.farmaciasahumada.cl",
        sitemap_url="https://www.farmaciasahumada.cl/sitemap_index.xml",
    ),
}


class JsonLdConnector(BaseScraper):
    # Ahumada's CDN serves BOT_USER_AGENT a normal 200 with full JSON-LD
    # (verified against robots.txt-allowed product URLs), so we keep the
    # identifiable bot UA rather than masquerading as a browser.
    use_browser_ua = False

    def __init__(self, config: JsonLdConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    @staticmethod
    def extract_jsonld_product(html: str) -> dict | None:
        for block in JSONLD_RE.findall(html):
            try:
                data = json.loads(block.strip())
            except (ValueError, TypeError):
                continue
            candidates = data if isinstance(data, list) else [data]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") == "Product":
                    return candidate
        return None

    @staticmethod
    def _product_region(html: str) -> str:
        """Slice out the main product block.

        Badges ("bioequivalente") and prescription notices also render on the
        recommended-product carousels further down the page, so reading them off
        the whole document would mislabel most products.
        """
        start = html.find("product-wrapper")
        if start == -1:
            return html
        end = html.find("recommendation", start)
        return html[start:end] if end != -1 else html[start:]

    @classmethod
    def extract_breadcrumbs(cls, html: str) -> list[str]:
        match = BREADCRUMB_RE.search(html)
        if not match:
            return []
        crumbs = [_clean(item) for item in BREADCRUMB_ITEM_RE.findall(match.group(1))]
        return [c for c in crumbs if c]

    @classmethod
    def extract_attributes(cls, data: dict, html: str | None = None) -> dict:
        """Structured identity signals Ahumada publishes.

        The JSON-LD block alone is thin (name/sku/brand/offers), so the useful
        identity lives in the page body: the "Ficha Técnica" tab names the
        active ingredient and the manufacturing laboratory, and the breadcrumb
        gives the category path. Active ingredient plus presentation is what
        actually decides whether two chains list the same drug — Ahumada
        publishes no EAN.
        """
        attributes: dict = {}

        brand = data.get("brand")
        brand_name = brand.get("name") if isinstance(brand, dict) else brand
        if brand_name:
            attributes["brand"] = str(brand_name).strip()

        for key, source in (("gtin13", "gtin13"), ("gtin", "gtin"), ("mpn", "mpn")):
            value = data.get(source)
            if value:
                attributes[key] = str(value).strip()

        if not html:
            return attributes

        region = cls._product_region(html)

        for label, value in DETAIL_PAIR_RE.findall(html):
            key = DETAIL_LABELS.get(_normalize_label(label))
            if not key or key in attributes:
                continue
            cleaned = _clean(value)
            if cleaned and len(cleaned) <= MAX_ATTRIBUTE_LEN:
                attributes[key] = cleaned

        crumbs = cls.extract_breadcrumbs(html)
        if crumbs:
            attributes["category"] = " > ".join(crumbs)
            attributes["categoryLeaf"] = crumbs[-1]
            attributes["isMedicine"] = _normalize_label(crumbs[0]) == "medicamentos"

        if "bioequivalent-badge" in region:
            attributes["isBioequivalent"] = True
        if re.search(r"requiere receta", region, re.IGNORECASE):
            attributes["requiresPrescription"] = True

        return attributes

    @staticmethod
    def pick_image(image) -> str | None:
        """schema.org `image` is a URL, a list of URLs, or an ImageObject.

        Ahumada publishes a list whose first entry is the packshot, already sized
        by the SFCC imaging service (`?sw=1050&sh=1050&sm=fit`) — a real product
        photo, not a sprite or logo. The list form has to be walked rather than
        indexed at [0] because a null or an empty string in first position would
        otherwise be stored as the product's image.
        """
        candidates = image if isinstance(image, list) else [image]
        for candidate in candidates:
            if isinstance(candidate, dict):
                # ImageObject: {"@type": "ImageObject", "url": "..."}
                candidate = candidate.get("url") or candidate.get("contentUrl")
            if isinstance(candidate, str) and candidate.strip().startswith("http"):
                return candidate.strip()
        return None

    def parse_product(self, data: dict, url: str, html: str | None = None) -> ScrapedProduct | None:
        offers = data.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else None
        if not isinstance(offers, dict):
            return None

        price = self.parse_machine_price(offers.get("price"))
        sku = data.get("sku") or data.get("mpn")
        name = data.get("name")
        if not price or not sku or not name:
            return None

        availability = str(offers.get("availability") or "")
        stock_status = "in_stock" if "InStock" in availability else "out_of_stock"

        brand = data.get("brand")
        brand_name = brand.get("name") if isinstance(brand, dict) else brand

        image_url = self.pick_image(data.get("image"))

        attributes = self.extract_attributes(data, html)
        # Ficha Técnica names the real manufacturer; JSON-LD `brand` is the
        # commercial brand ("Reflexan"), which is not the same thing.
        laboratory = attributes.get("laboratory") or brand_name

        return ScrapedProduct(
            sku=str(sku),
            name=name,
            brand=brand_name,
            laboratory=laboratory,
            price=price,
            original_price=None,
            discount_pct=None,
            stock_status=stock_status,
            stock_quantity=None,
            barcode=data.get("gtin13") or data.get("gtin"),
            url=url,
            image_url=image_url,
            pharmacy_chain=self.chain,
            source="scraper",
            attributes=attributes or None,
        )

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        async with build_client(self.user_agent, {"Accept": "text/html"}) as client:
            urls = await fetch_sitemap_urls(
                client,
                self.config.sitemap_url,
                child_filter=lambda u: self.config.product_sitemap_marker in u,
            )
            seen: set[str] = set()
            targets: list[str] = []
            for url in urls:
                if url not in seen:
                    seen.add(url)
                    targets.append(url)
            logger.info(f"[{self.chain}] sitemap yielded {len(targets)} product urls")

            async def fetch_one(url: str) -> ScrapedProduct | None:
                try:
                    html = await get_text(client, url)
                except Exception as exc:
                    logger.warning(f"[{self.chain}] fetch failed {url}: {exc}")
                    return None
                data = self.extract_jsonld_product(html)
                if not data:
                    return None
                return self.parse_product(data, url, html)

            emitted = 0
            for start in range(0, len(targets), self.config.chunk_size):
                chunk = targets[start : start + self.config.chunk_size]
                results = await gather_limited(
                    chunk, fetch_one, concurrency=self.config.concurrency
                )
                for product in results:
                    if product:
                        emitted += 1
                        yield product
                done = min(start + len(chunk), len(targets))
                logger.info(f"[{self.chain}] {done}/{len(targets)} fetched, {emitted} emitted")
                # Breather between chunks so we never look like a flood.
                await self.random_delay(400, 900)
