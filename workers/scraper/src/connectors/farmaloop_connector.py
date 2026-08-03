"""Farmaloop — Next.js storefront read through its own _next/data routes.

Farmaloop serves every page's props as JSON at
/_next/data/<buildId>/<route>.json. Category routes only return the first 15
products (pagination happens through a private search backend), so we discover
product slugs from the sitemap and read each product's own data route.

The buildId rotates on every deploy, so it is scraped from the homepage HTML
rather than hardcoded.
"""
import json
import re
from dataclasses import dataclass
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, fetch_sitemap_urls, get_json, get_text

BUILD_ID_RE = re.compile(r'"buildId"\s*:\s*"([^"]+)"')
PRODUCT_PATH_RE = re.compile(r"/products/([^/?#]+)/?$")


@dataclass
class FarmaloopConfig:
    chain: str
    base_url: str
    sitemap_url: str


FARMALOOP_CONFIGS: dict[str, FarmaloopConfig] = {
    "farmaloop": FarmaloopConfig(
        chain="farmaloop",
        base_url="https://www.farmaloop.cl",
        sitemap_url="https://www.farmaloop.cl/sitemap.xml",
    ),
}


class FarmaloopConnector(BaseScraper):
    def __init__(self, config: FarmaloopConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    @staticmethod
    def extract_build_id(html: str) -> str | None:
        match = BUILD_ID_RE.search(html)
        return match.group(1) if match else None

    @staticmethod
    def extract_slug(url: str) -> str | None:
        match = PRODUCT_PATH_RE.search(url)
        return match.group(1) if match else None

    def data_url(self, build_id: str, slug: str) -> str:
        return f"{self.base_url}/_next/data/{build_id}/products/{slug}.json"

    # Categories that are clearly medicine on Farmaloop's taxonomy. Everything
    # else (Cuidado y Belleza, Higiene, …) is non-medicine for matcher gates.
    MEDICINE_CATEGORIES = frozenset(
        {
            "medicamentos",
            "medicamento",
            "receta",
            "bioequivalentes",
            "bioequivalente",
        }
    )

    @classmethod
    def extract_attributes(cls, raw: dict) -> dict:
        """Pull taxonomy + composition flags the matcher / UI can use.

        Live product JSON carries productCategory ('Medicamentos' vs
        'Cuidado y Belleza'), bioequivalent, requiresPrescription,
        composicionSearch, pharmaceuticalForm and presentation. Without these
        attributes prod rows stay attrs=NULL and --only-medicine relink skips
        the whole chain.
        """
        attributes: dict = {}

        category = (raw.get("productCategory") or "").strip()
        if category:
            attributes["category"] = category
            folded = category.casefold()
            attributes["isMedicine"] = any(
                token in folded for token in cls.MEDICINE_CATEGORIES
            ) or folded == "medicamentos"

        sub = (raw.get("productSubCategory") or "").strip()
        if sub:
            attributes["subCategory"] = sub

        form = (raw.get("pharmaceuticalForm") or raw.get("presentation") or "").strip()
        if form:
            attributes["presentation"] = form

        ingredient = (raw.get("composicionSearch") or "").strip()
        if not ingredient:
            comps = raw.get("composicion")
            if isinstance(comps, list) and comps:
                parts = []
                for item in comps:
                    if not isinstance(item, dict):
                        continue
                    act = (item.get("principio_activo") or "").strip()
                    conc = (item.get("concentracion") or "").strip()
                    unit = (item.get("unidad_de_medida") or "").strip()
                    if act and conc and unit:
                        parts.append(f"{act} {conc} {unit}".strip())
                    elif act:
                        parts.append(act)
                ingredient = "; ".join(parts)
        if ingredient:
            attributes["activeIngredient"] = ingredient

        if raw.get("bioequivalent") is True:
            attributes["isBioequivalent"] = True
        if raw.get("requiresPrescription") is True:
            attributes["requiresPrescription"] = True
        rx = (raw.get("prescriptionType") or "").strip()
        if rx:
            attributes["prescriptionType"] = rx

        tags = raw.get("tags") or []
        if isinstance(tags, list):
            clean = [t for t in tags if isinstance(t, str) and t.strip()]
            if clean:
                attributes["tags"] = clean[:10]

        return attributes

    def parse_product(self, raw: dict) -> ScrapedProduct | None:
        sku = raw.get("sku")
        name = raw.get("fullName") or raw.get("genericName")
        price = raw.get("bestPrice")
        if not sku or not name or price is None:
            return None

        price = int(price)
        base_price = raw.get("basePrice")
        original_price = int(base_price) if base_price and int(base_price) > price else None
        discount_pct = raw.get("bestDiscount")
        if discount_pct is None and original_price:
            discount_pct = round((1 - price / original_price) * 100)

        # `photoURL` is the product packshot. Two CDNs are in use depending on
        # how old the listing is — imagenes.fc.farmaloop.cl (webp, "-600"
        # suffix) and d35lrmue8i33t5.cloudfront.net (jpg) — both real product
        # photos, so no rewriting is needed; only empty strings are rejected so
        # they do not reach the DB as a broken <img src="">.
        photo_url = (raw.get("photoURL") or "").strip() or None

        attributes = self.extract_attributes(raw) or None
        slug = raw.get("slug")
        return ScrapedProduct(
            sku=str(sku),
            name=name.strip(),
            brand=raw.get("laboratoryName"),
            laboratory=raw.get("laboratoryName"),
            price=price,
            original_price=original_price,
            discount_pct=int(discount_pct) if discount_pct is not None else None,
            stock_status="in_stock" if raw.get("availableForSale") else "out_of_stock",
            stock_quantity=None,
            barcode=raw.get("ean"),
            url=f"{self.base_url}/products/{slug}/" if slug else None,
            image_url=photo_url,
            pharmacy_chain=self.chain,
            source="api",
            attributes=attributes,
        )

    @staticmethod
    def find_product_payload(page_props: dict) -> dict | None:
        """Product data route nests the payload under a key that varies by build."""
        for key in ("product", "productData", "productInfo", "data"):
            value = page_props.get(key)
            if isinstance(value, dict) and value.get("sku"):
                return value
        for value in page_props.values():
            if isinstance(value, dict) and value.get("sku") and value.get("bestPrice") is not None:
                return value
        return None

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            try:
                home = await get_text(client, f"{self.base_url}/")
            except Exception as exc:
                logger.error(f"[{self.chain}] homepage fetch failed, cannot resolve buildId: {exc}")
                return

            build_id = self.extract_build_id(home)
            if not build_id:
                logger.error(f"[{self.chain}] buildId not found in homepage HTML")
                return
            logger.info(f"[{self.chain}] buildId={build_id}")

            urls = await fetch_sitemap_urls(client, self.config.sitemap_url)
            slugs: list[str] = []
            seen: set[str] = set()
            for url in urls:
                slug = self.extract_slug(url)
                if slug and slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
            logger.info(f"[{self.chain}] sitemap yielded {len(slugs)} product slugs")

            # Bounded concurrency: sequential was ~1 product/s with delays; 4 workers
            # keep total load polite while finishing multi-k catalogs in time.
            from ..http_utils import gather_limited

            concurrency = 4
            emitted = 0
            for start in range(0, len(slugs), 100):
                chunk = slugs[start : start + 100]

                async def fetch_one(slug: str):
                    try:
                        payload = await get_json(client, self.data_url(build_id, slug))
                    except Exception as exc:
                        logger.warning(f"[{self.chain}] data route failed for {slug}: {exc}")
                        return None
                    page_props = payload.get("pageProps") or {}
                    raw = self.find_product_payload(page_props)
                    if not raw:
                        return None
                    return self.parse_product(raw)

                results = await gather_limited(chunk, fetch_one, concurrency=concurrency)
                for product in results:
                    if product:
                        emitted += 1
                        yield product
                done = min(start + len(chunk), len(slugs))
                logger.info(f"[{self.chain}] {done}/{len(slugs)} fetched, {emitted} emitted")
                await self.random_delay(400, 900)
