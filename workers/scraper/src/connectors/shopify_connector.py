"""Shopify storefronts (Farmex, Farmacias Curie).

Shopify exposes the whole catalog at /products.json, paginated 250 at a time.
No auth, no browser, prices and stock come straight from the variant payload.
"""
from dataclasses import dataclass
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, get_json


@dataclass
class ShopifyConfig:
    chain: str
    base_url: str
    page_size: int = 250
    max_pages: int = 200


SHOPIFY_CONFIGS: dict[str, ShopifyConfig] = {
    "farmex": ShopifyConfig(chain="farmex", base_url="https://farmex.cl"),
    "curie": ShopifyConfig(chain="curie", base_url="https://www.farmaciascurie.cl"),
}


class ShopifyConnector(BaseScraper):
    def __init__(self, config: ShopifyConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    def build_page_url(self, page: int) -> str:
        return f"{self.base_url}/products.json?limit={self.config.page_size}&page={page}"

    # Shopify has no medicine flag, so `product_type` is the only separator
    # between an actual drug and the cosmetics these stores also sell.
    NON_MEDICINE_TYPES = {
        "dermocosmetica", "cosmetica", "belleza", "cuidado personal",
        "higiene", "maquillaje", "capilar", "solar", "bebidas", "alimentos",
    }

    @classmethod
    def extract_attributes(cls, raw: dict) -> dict:
        attributes: dict = {}
        product_type = (raw.get("product_type") or "").strip()
        if product_type:
            attributes["category"] = product_type
            attributes["isMedicine"] = product_type.lower() not in cls.NON_MEDICINE_TYPES
        tags = raw.get("tags") or []
        if tags:
            attributes["tags"] = [t for t in tags if not t.isdigit()][:10]
        return attributes

    def parse_product(self, raw: dict) -> list[ScrapedProduct]:
        handle = raw.get("handle", "")
        title = raw.get("title", "")
        vendor = raw.get("vendor")
        # Shopify only sets `variant.featured_image` when the merchant pinned a
        # distinct photo to that variant; on Farmex/Curie it is null for ~99% of
        # variants, so `images[0]` (the product's primary photo) is what actually
        # gets stored. Verified against both live catalogs: where featured_image
        # does exist it is the same file as images[0], and the genuinely
        # multi-variant products (sizes/presentations) share one product photo.
        images = raw.get("images") or []
        default_image = next((i.get("src") for i in images if i.get("src")), None)

        attributes = self.extract_attributes(raw) or None

        results: list[ScrapedProduct] = []
        for variant in raw.get("variants") or []:
            price = self.parse_machine_price(variant.get("price"))
            # Farmex publishes $0 placeholder variants (Cenabast / insurance listings).
            # They are not real offers and would poison the "cheapest price" ranking.
            if not price:
                continue
            compare_at = self.parse_machine_price(variant.get("compare_at_price"))
            original_price = compare_at if compare_at and compare_at > price else None
            discount_pct = round((1 - price / original_price) * 100) if original_price else None

            variant_title = variant.get("title") or ""
            name = title if variant_title in ("", "Default Title") else f"{title} - {variant_title}"

            results.append(ScrapedProduct(
                sku=str(variant.get("id") or variant.get("sku") or ""),
                name=name,
                brand=vendor,
                laboratory=vendor,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                stock_status="in_stock" if variant.get("available") else "out_of_stock",
                stock_quantity=None,
                barcode=variant.get("sku") or None,
                url=f"{self.base_url}/products/{handle}" if handle else None,
                # `or default_image` rather than a plain if/else: a variant can
                # carry a featured_image object whose `src` is null, and the old
                # form stored None for it instead of the product photo.
                image_url=(variant.get("featured_image") or {}).get("src") or default_image,
                pharmacy_chain=self.chain,
                source="api",
                attributes=attributes,
            ))
        return results

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        total = 0
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            for page in range(1, self.config.max_pages + 1):
                try:
                    payload = await get_json(client, self.build_page_url(page))
                except Exception as exc:
                    logger.error(f"[{self.chain}] page {page} failed: {exc}")
                    break

                raw_products = payload.get("products") or []
                if not raw_products:
                    break

                for raw in raw_products:
                    for product in self.parse_product(raw):
                        yield product
                        total += 1

                logger.info(f"[{self.chain}] page {page}: {len(raw_products)} products, total variants: {total}")
                await self.random_delay(400, 1200)
