"""Cruz Verde — Salesforce Commerce Cloud OCAPI Shop API.

Cruz Verde dropped VTEX for SFCC. The storefront is an Angular SPA that talks to
the public OCAPI Shop API with a client_id baked into its bundle.

Two traversal modes:
  - "sitemap": walk sitemap_index.xml for product ids, fetch each product.
    Complete, slow, and the only mode robots.txt sanctions for bulk discovery
    (beta.cruzverde.cl/robots.txt disallows any URL carrying `start`, which
    rules out paginating product_search).
  - "search": run product_search for a list of terms (medication names from our
    own catalog). Cheap and fast for frequent price refreshes.
"""
import re
from dataclasses import dataclass, field
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, fetch_sitemap_urls, get_json

PRODUCT_ID_RE = re.compile(r"/(\d+)\.html?$")


@dataclass
class OcapiConfig:
    chain: str
    base_url: str            # public storefront, used for product URLs
    api_base: str            # OCAPI host, e.g. https://beta.cruzverde.cl
    site_id: str             # OCAPI site, e.g. Chile
    client_id: str
    api_version: str = "v19_1"
    sitemap_url: str = ""
    seed_terms: list[str] = field(default_factory=list)


# Seed terms only matter for "search" mode when the DB has no medication names yet.
DEFAULT_SEED_TERMS = [
    "paracetamol", "ibuprofeno", "omeprazol", "losartan", "metformina",
    "amoxicilina", "atorvastatina", "aspirina", "loratadina", "clonazepam",
    "sertralina", "levotiroxina", "enalapril", "diclofenaco", "salbutamol",
]

OCAPI_CONFIGS: dict[str, OcapiConfig] = {
    "cruz_verde": OcapiConfig(
        chain="cruz_verde",
        base_url="https://www.cruzverde.cl",
        api_base="https://beta.cruzverde.cl",
        site_id="Chile",
        client_id="c19ce24d-1677-4754-b9f7-c193997c5a92",
        sitemap_url="https://www.cruzverde.cl/sitemap_index.xml",
        seed_terms=DEFAULT_SEED_TERMS,
    ),
}


class OcapiConnector(BaseScraper):
    def __init__(self, config: OcapiConfig, mode: str = "sitemap", terms: list[str] | None = None):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url
        self.mode = mode
        self.terms = terms or config.seed_terms

    @property
    def shop_api(self) -> str:
        c = self.config
        return f"{c.api_base}/s/{c.site_id}/dw/shop/{c.api_version}"

    def product_url(self, product_id: str) -> str:
        return f"{self.shop_api}/products/{product_id}?expand=prices,availability,images&client_id={self.config.client_id}"

    def search_url(self, term: str, start: int = 0, count: int = 200) -> str:
        return (
            f"{self.shop_api}/product_search?q={term}&start={start}&count={count}"
            f"&expand=prices,availability,images&client_id={self.config.client_id}"
        )

    @staticmethod
    def extract_product_id(url: str) -> str | None:
        match = PRODUCT_ID_RE.search(url)
        return match.group(1) if match else None

    def _stock(self, orderable: bool | None, stock_level: int | None) -> tuple[str, int | None]:
        if not orderable:
            return "out_of_stock", stock_level
        if stock_level is not None and stock_level < 5:
            return "low_stock", stock_level
        return "in_stock", stock_level

    @staticmethod
    def extract_attributes(raw: dict) -> dict:
        """Cruz Verde publishes no EAN but does expose structured identity.

        The `c_*` custom attributes carry active ingredient, dose and format —
        for grouping generics that beats a barcode, since two labs selling the
        same molecule have different EANs but the same ingredient and dose.
        `c_isMedProduct` also separates real medicine from cosmetics.
        """
        mapping = {
            "activeIngredient": "c_activeIngredient",
            "dose": "c_dose",
            "format": "c_format",
            "laboratory": "c_laboratory",
            "isMedicine": "c_isMedProduct",
            "isBioequivalent": "c_isBioequivalent",
            "bioequivalentGroup": "c_bioequivalentSubCategoryID",
            "prescription": "c_prescription",
            "category": "primary_category_id",
        }
        attributes = {
            key: raw[source] for key, source in mapping.items() if raw.get(source) is not None
        }
        if raw.get("manufacturer_sku"):
            attributes["manufacturerSku"] = raw["manufacturer_sku"]
        return attributes

    # SFCC groups a product's images by `view_type`: `large` and `medium` are the
    # product photo at different resolutions, `swatch` is the 30px colour chip of
    # a variation attribute — a solid square of colour, not the product. Taking
    # `image_groups[0]` blindly trusts SFCC's ordering, and a product that
    # publishes a swatch group first would be stored with a colour chip as its
    # image. Order the preference explicitly instead and never fall back to a
    # swatch: no image beats a wrong image.
    IMAGE_VIEW_PREFERENCE = ("large", "hi-res", "medium", "small")
    IMAGE_VIEW_BLOCKLIST = ("swatch",)

    @classmethod
    def pick_image(cls, image_groups: list[dict] | None) -> str | None:
        """First usable image link, preferring the largest product view."""
        groups = [g for g in (image_groups or []) if (g.get("images") or [])]
        if not groups:
            return None

        def first_link(group: dict) -> str | None:
            for image in group.get("images") or []:
                link = image.get("link") or image.get("dis_base_link")
                if link:
                    return link
            return None

        for view_type in cls.IMAGE_VIEW_PREFERENCE:
            for group in groups:
                if (group.get("view_type") or "").lower() == view_type:
                    link = first_link(group)
                    if link:
                        return link
        # Unknown view_type (SFCC lets merchants define their own): accept it,
        # but still refuse anything explicitly known to be a swatch.
        for group in groups:
            if (group.get("view_type") or "").lower() in cls.IMAGE_VIEW_BLOCKLIST:
                continue
            link = first_link(group)
            if link:
                return link
        return None

    def parse_product(self, raw: dict) -> ScrapedProduct | None:
        """Parse a full product payload (GET /products/{id})."""
        product_id = raw.get("id")
        name = raw.get("name")
        price = raw.get("price")
        if not product_id or not name or price is None:
            return None

        inventory = raw.get("inventory") or {}
        stock_status, stock_quantity = self._stock(inventory.get("orderable"), inventory.get("stock_level"))

        list_prices = [p for p in (raw.get("prices") or {}).values() if isinstance(p, (int, float))]
        highest = max(list_prices) if list_prices else None
        original_price = int(highest) if highest and highest > price else None
        discount_pct = round((1 - price / original_price) * 100) if original_price else None

        image_url = self.pick_image(raw.get("image_groups"))

        return ScrapedProduct(
            sku=str(product_id),
            name=name,
            brand=raw.get("brand"),
            laboratory=raw.get("brand"),
            price=int(price),
            original_price=original_price,
            discount_pct=discount_pct,
            stock_status=stock_status,
            stock_quantity=stock_quantity,
            barcode=raw.get("ean"),
            url=f"{self.base_url}/{product_id}.html",
            image_url=image_url,
            pharmacy_chain=self.chain,
            source="api",
            attributes=self.extract_attributes(raw) or None,
        )

    def parse_search_hit(self, hit: dict) -> ScrapedProduct | None:
        """Parse a product_search hit (lighter payload than a full product)."""
        product_id = hit.get("product_id")
        name = hit.get("product_name")
        price = hit.get("price")
        if not product_id or not name or price is None:
            return None

        list_prices = [p for p in (hit.get("prices") or {}).values() if isinstance(p, (int, float))]
        highest = max(list_prices) if list_prices else None
        original_price = int(highest) if highest and highest > price else None
        discount_pct = round((1 - price / original_price) * 100) if original_price else None

        # A search hit carries a single flattened `image`, which SFCC resolves to
        # the default view (verified `.../images/large/...` on this site), so
        # there is no group to choose from here. `dis_base_link` is the same file
        # served through the dynamic imaging service — only a fallback.
        hit_image = hit.get("image") or {}
        image_url = hit_image.get("link") or hit_image.get("dis_base_link")

        return ScrapedProduct(
            sku=str(product_id),
            name=name,
            brand=None,
            laboratory=None,
            price=int(price),
            original_price=original_price,
            discount_pct=discount_pct,
            stock_status="in_stock" if hit.get("orderable") else "out_of_stock",
            stock_quantity=None,
            barcode=None,
            url=f"{self.base_url}/{product_id}.html",
            image_url=image_url,
            pharmacy_chain=self.chain,
            source="api",
        )

    async def fetch_by_skus(self, skus: list[str]) -> AsyncIterator[ScrapedProduct]:
        """Fetch only the given products, by id.

        For this chain `sku` *is* the SFCC product id (`parse_product` sets
        `sku=str(product_id)`), so a repair job that needs 300 specific products
        can ask for exactly those instead of walking the whole ~10k sitemap.
        Used by `backfill_images`; the normal crawl still goes through the
        sitemap because that is what robots.txt sanctions for *discovery*.
        """
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            for index, sku in enumerate(skus, start=1):
                try:
                    raw = await get_json(client, self.product_url(sku))
                except Exception as exc:
                    logger.warning(f"[{self.chain}] product {sku} failed: {exc}")
                    continue
                product = self.parse_product(raw)
                if product:
                    yield product
                if index % 100 == 0:
                    logger.info(f"[{self.chain}] targeted fetch {index}/{len(skus)}")
                await self.random_delay(200, 600)

    async def _scrape_via_sitemap(self) -> AsyncIterator[ScrapedProduct]:
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            urls = await fetch_sitemap_urls(
                client, self.config.sitemap_url, child_filter=lambda u: "product" in u
            )
            targets: list[tuple[str, str]] = []
            seen: set[str] = set()
            for url in urls:
                pid = self.extract_product_id(url)
                if pid and pid not in seen:
                    seen.add(pid)
                    targets.append((pid, url))
            logger.info(f"[{self.chain}] sitemap yielded {len(targets)} product ids")

            emitted = 0
            for index, (product_id, canonical_url) in enumerate(targets, start=1):
                try:
                    raw = await get_json(client, self.product_url(product_id))
                except Exception as exc:
                    logger.warning(f"[{self.chain}] product {product_id} failed: {exc}")
                    continue
                product = self.parse_product(raw)
                if product:
                    product.url = canonical_url
                    yield product
                    emitted += 1
                if index % 250 == 0:
                    logger.info(f"[{self.chain}] {index}/{len(targets)} fetched, {emitted} emitted")
                await self.random_delay(200, 600)

    async def _scrape_via_search(self) -> AsyncIterator[ScrapedProduct]:
        page_size = 200
        seen: set[str] = set()
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            for term in self.terms:
                start = 0
                while True:
                    try:
                        payload = await get_json(client, self.search_url(term, start, page_size))
                    except Exception as exc:
                        logger.warning(f"[{self.chain}] search '{term}' start={start} failed: {exc}")
                        break

                    hits = payload.get("hits") or []
                    if not hits:
                        break
                    for hit in hits:
                        product = self.parse_search_hit(hit)
                        if product and product.sku not in seen:
                            seen.add(product.sku)
                            yield product

                    start += len(hits)
                    if start >= int(payload.get("total") or 0):
                        break
                    await self.random_delay(400, 1000)
                logger.info(f"[{self.chain}] term '{term}' done, {len(seen)} unique products so far")

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        if self.mode == "search":
            async for product in self._scrape_via_search():
                yield product
        else:
            async for product in self._scrape_via_sitemap():
                yield product
