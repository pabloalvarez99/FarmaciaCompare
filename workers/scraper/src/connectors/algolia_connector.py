"""Salcobrand — Spree storefront backed by a public Algolia index.

The search UI ships an Algolia search-only key in its JS bundle. The key is
referer-restricted, so requests must carry a salcobrand.cl Referer/Origin.

Algolia caps a single query at 1000 reachable hits, so a blank browse query
cannot walk the whole index. We partition by the `taxonomies` facet and fall
back to letter-prefix queries for any bucket that hits the ceiling.
"""
from dataclasses import dataclass, field
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client

ALGOLIA_MAX_HITS = 1000


@dataclass
class AlgoliaConfig:
    chain: str
    base_url: str
    app_id: str
    api_key: str
    index_name: str
    referer: str
    facet_field: str = "taxonomies"
    hits_per_page: int = 200
    fallback_prefixes: list[str] = field(
        default_factory=lambda: list("abcdefghijklmnopqrstuvwxyz")
    )


ALGOLIA_CONFIGS: dict[str, AlgoliaConfig] = {
    "salcobrand": AlgoliaConfig(
        chain="salcobrand",
        base_url="https://salcobrand.cl",
        app_id="GM3RP06HJG",
        api_key="0259fe250b3be4b1326eb85e47aa7d81",
        index_name="sb_variant_production",
        referer="https://salcobrand.cl/",
    ),
}


class AlgoliaConnector(BaseScraper):
    def __init__(self, config: AlgoliaConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    @property
    def query_url(self) -> str:
        return f"https://{self.config.app_id}-dsn.algolia.net/1/indexes/{self.config.index_name}/query"

    def _headers(self) -> dict[str, str]:
        return {
            "X-Algolia-API-Key": self.config.api_key,
            "X-Algolia-Application-Id": self.config.app_id,
            "Content-Type": "application/json",
            "Referer": self.config.referer,
            "Origin": self.config.referer.rstrip("/"),
        }

    @staticmethod
    def extract_attributes(hit: dict) -> dict:
        """Salcobrand publishes no EAN, in the index or on the product page.

        What it does expose: the deepest `product_categories` level names the
        active ingredient ("Medicamentos > Dolor... > Paracetamol"), and
        `options_text` carries the presentation ("24 Comprimidos"). Together
        they are the only identity signal this chain gives.
        """
        attributes: dict = {}

        categories = hit.get("product_categories") or {}
        deepest = None
        for level in ("lvl3", "lvl2", "lvl1", "lvl0"):
            values = categories.get(level)
            if values:
                deepest = values[0] if isinstance(values, list) else values
                break
        if deepest:
            attributes["category"] = deepest
            # The leaf of the breadcrumb is the ingredient at lvl3.
            leaf = str(deepest).split(">")[-1].strip()
            if leaf and categories.get("lvl3"):
                attributes["activeIngredient"] = leaf

        for key, source in (
            ("presentation", "options_text"),
            ("saleType", "sale_type"),
            ("patentType", "drug_patent_type_filter"),
        ):
            if hit.get(source):
                attributes[key] = hit[source]

        if hit.get("needs_recipe") is not None:
            attributes["requiresPrescription"] = bool(hit["needs_recipe"])

        bioequivalent = hit.get("bioequivalent_filter") or {}
        if isinstance(bioequivalent, dict) and bioequivalent.get("has_bioequivalent") is not None:
            attributes["hasBioequivalent"] = bool(bioequivalent["has_bioequivalent"])

        taxonomies = hit.get("taxonomies")
        if taxonomies:
            attributes["isMedicine"] = "Medicamentos" in taxonomies

        return attributes

    def parse_hit(self, hit: dict) -> ScrapedProduct | None:
        sku = hit.get("sku") or hit.get("objectID")
        name = hit.get("name")
        price = hit.get("normal_price")
        if not sku or not name or price is None:
            return None

        price = int(price)
        discounted = self.parse_machine_price(hit.get("direct_discount"))
        if discounted and 0 < discounted < price:
            final_price, original_price = discounted, price
            discount_pct = round((1 - final_price / original_price) * 100)
        else:
            final_price, original_price, discount_pct = price, None, None

        # The index exposes the same Spree attachment at several sizes.
        # Measured on static.salcobrand.cl:
        #   thumbnail_image_url -> /thumbnail/  100x100,  2.9 KB  (blurry at 2x)
        #   catalog_image_url   -> /small/      260x260, 10.9 KB  <- what we keep
        #   (/large/            -> 1050x1050,  69.5 KB, 6x the bytes)
        # 260 px is the right size for a table thumbnail rendered at 48-64 px on
        # a retina screen, so `catalog_image_url` is the correct field, not the
        # thumbnail. Both were present on all 800 hits sampled; the fallback is
        # only there so a future null does not lose the image entirely.
        image_url = hit.get("catalog_image_url") or hit.get("thumbnail_image_url")

        slug = hit.get("slug")
        return ScrapedProduct(
            sku=str(sku),
            name=name,
            brand=hit.get("brand"),
            laboratory=hit.get("brand"),
            price=final_price,
            original_price=original_price,
            discount_pct=discount_pct,
            stock_status="in_stock" if hit.get("has_stock") else "out_of_stock",
            stock_quantity=None,
            barcode=None,
            url=f"{self.base_url}/products/{slug}" if slug else None,
            image_url=image_url,
            pharmacy_chain=self.chain,
            source="api",
            attributes=self.extract_attributes(hit) or None,
        )

    async def _query(self, client, params: str, *, max_retries: int = 5) -> dict:
        """POST search with respectful backoff on 429 (Algolia rate limits)."""
        import asyncio

        import httpx

        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await client.post(
                    self.query_url, headers=self._headers(), json={"params": params}
                )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    logger.warning(
                        f"[{self.chain}] Algolia 429, sleeping {wait:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    delay = min(delay * 2, 60.0)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response is not None and exc.response.status_code == 429:
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60.0)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError(f"[{self.chain}] Algolia query exhausted retries")

    async def _list_facet_values(self, client) -> dict[str, int]:
        """Facet value -> hit count.

        The dedicated /facets/<field>/query endpoint is rejected because
        `taxonomies` is not declared searchable, so we read the facet map off a
        zero-hit search instead.
        """
        params = (
            f"query=&hitsPerPage=0"
            f'&facets=["{self.config.facet_field}"]'
            f"&maxValuesPerFacet=100"
        )
        try:
            payload = await self._query(client, params)
        except Exception as exc:
            logger.warning(f"[{self.chain}] facet listing failed, falling back to letter sweep: {exc}")
            return {}
        return payload.get("facets", {}).get(self.config.facet_field, {})

    async def _paginate(self, client, params_prefix: str, seen: set[str]) -> AsyncIterator[ScrapedProduct]:
        """Walk pages of one query until exhausted or the 1000-hit ceiling."""
        page = 0
        while True:
            params = f"{params_prefix}&hitsPerPage={self.config.hits_per_page}&page={page}"
            try:
                payload = await self._query(client, params)
            except Exception as exc:
                logger.warning(f"[{self.chain}] query failed ({params_prefix}, page {page}): {exc}")
                return

            hits = payload.get("hits") or []
            if not hits:
                return
            for hit in hits:
                product = self.parse_hit(hit)
                if product and product.sku not in seen:
                    seen.add(product.sku)
                    yield product

            page += 1
            if page >= int(payload.get("nbPages") or 0):
                return
            if page * self.config.hits_per_page >= ALGOLIA_MAX_HITS:
                logger.info(f"[{self.chain}] hit Algolia 1000-result ceiling for '{params_prefix}'")
                return
            # Keep Algolia happy: human-paced pagination between pages.
            await self.random_delay(800, 1800)

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        seen: set[str] = set()
        async with build_client(self.user_agent) as client:
            facet_counts = await self._list_facet_values(client)
            if facet_counts:
                logger.info(
                    f"[{self.chain}] partitioning by {len(facet_counts)} "
                    f"'{self.config.facet_field}' values"
                )
            for value, count in facet_counts.items():
                facet_filter = f'["{self.config.facet_field}:{value}"]'
                if count <= ALGOLIA_MAX_HITS:
                    async for product in self._paginate(client, f"query=&facetFilters={facet_filter}", seen):
                        yield product
                else:
                    # Bucket is bigger than Algolia will page through; split it by
                    # letter so every product stays reachable.
                    logger.info(f"[{self.chain}] facet '{value}' has {count} hits, splitting by letter")
                    for letter in self.config.fallback_prefixes:
                        async for product in self._paginate(
                            client, f"query={letter}&facetFilters={facet_filter}", seen
                        ):
                            yield product
                logger.info(f"[{self.chain}] facet '{value}' done, {len(seen)} unique so far")

            # Final sweep catches products with no taxonomy assigned at all.
            for letter in self.config.fallback_prefixes:
                async for product in self._paginate(client, f"query={letter}", seen):
                    yield product
            logger.info(f"[{self.chain}] scrape complete: {len(seen)} unique products")
