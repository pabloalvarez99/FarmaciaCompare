from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
import random
import asyncio
from loguru import logger


@dataclass
class ScrapedProduct:
    """Raw product data extracted from a pharmacy."""
    sku: str
    name: str
    brand: str | None
    laboratory: str | None
    price: int                    # CLP, no decimals
    original_price: int | None    # before discount
    discount_pct: int | None
    stock_status: str             # 'in_stock', 'low_stock', 'out_of_stock'
    stock_quantity: int | None
    barcode: str | None
    url: str | None
    image_url: str | None
    pharmacy_chain: str           # 'cruz_verde', 'salcobrand', 'ahumada', 'dr_simi'
    source: str                   # 'scraper' | 'api'


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
]


class BaseScraper(ABC):
    """Base class for all pharmacy scrapers."""

    chain: str           # override in subclass: 'cruz_verde', etc.
    base_url: str        # override in subclass

    def __init__(self):
        self.user_agent = random.choice(USER_AGENTS)

    @abstractmethod
    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        """Yield products one by one as they are scraped."""
        ...

    async def random_delay(self, min_ms: int = 800, max_ms: int = 2500):
        """Add human-like delay between requests."""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    def parse_price(self, raw: str) -> int | None:
        """Parse Chilean price string to integer CLP. '$12.990' -> 12990"""
        if not raw:
            return None
        cleaned = raw.replace("$", "").replace(".", "").replace(",", "").strip()
        try:
            return int(float(cleaned))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse price: {raw!r}")
            return None

    def parse_stock(self, raw: str | None) -> str:
        """Normalize stock status string."""
        if not raw:
            return "in_stock"
        lower = raw.lower()
        if any(w in lower for w in ["agotado", "sin stock", "no disponible", "out"]):
            return "out_of_stock"
        if any(w in lower for w in ["poco", "últimas", "last", "low"]):
            return "low_stock"
        return "in_stock"
