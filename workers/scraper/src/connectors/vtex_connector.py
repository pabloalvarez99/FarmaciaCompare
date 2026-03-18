from dataclasses import dataclass
from typing import AsyncIterator
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from ..base_scraper import BaseScraper, ScrapedProduct


@dataclass
class VtexConfig:
    chain: str
    account_name: str
    base_url: str


VTEX_CONFIGS = {
    "cruz_verde": VtexConfig(chain="cruz_verde", account_name="cruzverde", base_url="https://www.cruzverde.cl"),
    "salcobrand": VtexConfig(chain="salcobrand", account_name="salcobrand", base_url="https://www.salcobrand.cl"),
    "ahumada": VtexConfig(chain="ahumada", account_name="farmaciasahumada", base_url="https://www.farmaciasahumada.cl"),
}


class VtexConnector(BaseScraper):
    VTEX_API_TEMPLATE = (
        "https://{account}.vtexcommercestable.com.br/api/catalog_system/pub/products/"
        "search?_from={from_}&_to={to}&O=OrderByScoreDESC"
    )

    def __init__(self, config: VtexConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    def build_search_url(self, page: int = 1, page_size: int = 50) -> str:
        from_ = (page - 1) * page_size
        to = from_ + page_size - 1
        return self.VTEX_API_TEMPLATE.format(account=self.config.account_name, from_=from_, to=to)

    def parse_product(self, raw: dict) -> list[ScrapedProduct]:
        items = raw.get("items", [])
        if not items:
            return []
        results = []
        for item in items:
            sellers = item.get("sellers", [])
            if not sellers:
                continue
            offer = sellers[0].get("commertialOffer", {})
            price = int(offer.get("Price", 0))
            list_price = int(offer.get("ListPrice", 0))
            available_qty = int(offer.get("AvailableQuantity", 0))
            if price == 0 and available_qty == 0:
                stock_status = "out_of_stock"
            elif available_qty < 5:
                stock_status = "low_stock"
            else:
                stock_status = "in_stock"
            original_price = list_price if list_price > price else None
            discount_pct = None
            if original_price and price > 0:
                discount_pct = round((1 - price / original_price) * 100)
            results.append(ScrapedProduct(
                sku=item.get("itemId", ""),
                name=raw.get("productName", ""),
                brand=raw.get("brand"),
                laboratory=None,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                stock_status=stock_status,
                stock_quantity=available_qty if available_qty > 0 else None,
                barcode=item.get("ean"),
                url=f"{self.base_url}/{raw.get('linkText', '')}/p",
                image_url=None,
                pharmacy_chain=self.chain,
                source="api",
            ))
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, client: httpx.AsyncClient, page: int, page_size: int) -> list[dict]:
        url = self.build_search_url(page, page_size)
        headers = {"User-Agent": self.user_agent, "Accept": "application/json", "Referer": self.base_url}
        response = await client.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        page_size = 50
        page = 1
        total_scraped = 0
        async with httpx.AsyncClient() as client:
            while True:
                try:
                    raw_products = await self._fetch_page(client, page, page_size)
                except Exception as e:
                    logger.error(f"[{self.chain}] Page {page} failed: {e}")
                    break
                if not raw_products:
                    break
                for raw in raw_products:
                    for product in self.parse_product(raw):
                        yield product
                        total_scraped += 1
                logger.info(f"[{self.chain}] Page {page}: {len(raw_products)} products, total: {total_scraped}")
                await self.random_delay()
                page += 1
