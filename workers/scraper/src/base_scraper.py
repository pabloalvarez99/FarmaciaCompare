from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
from urllib.parse import quote, urlsplit, urlunsplit
import random
import asyncio
from loguru import logger


# Every character RFC 3986 allows unescaped in a path segment, plus `/` and `%`.
# `%` must stay safe or an already-encoded `%20` would become `%2520`.
_URL_PATH_SAFE = "/%!$&'()*+,;=:@~"


def normalize_image_url(raw: str | None) -> str | None:
    """Make a storefront image URL safe to store and to put in `<img src>`.

    Storefronts hand back filenames with raw spaces (`Mupirocina - 613-1.jpg`
    from Dr. Simi's VTEX). Browsers paper over that, but anything server-side
    breaks: curl exits 000 and Python's urllib refuses it as a control
    character. Percent-encoding the path fixes it; the query string is left
    alone because cache-busters like `?v=638…` are already safe.

    Returns None for anything that is not a usable absolute http(s) URL, so a
    placeholder or a relative path never reaches the database.
    """
    if not raw:
        return None
    url = raw.strip()
    # Protocol-relative (`//cdn.host/a.jpg`) is what several storefront APIs
    # still emit. It is a real image, just missing a scheme — recover it instead
    # of discarding it, otherwise this function silently deletes good data.
    if url.startswith("//"):
        url = "https:" + url
    if not url.lower().startswith(("http://", "https://")):
        return None
    parts = urlsplit(url)
    if not parts.netloc:
        return None
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe=_URL_PATH_SAFE),
        parts.query,
        parts.fragment,
    ))


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
    # Structured identity signals the storefront publishes. Chains without a
    # barcode (Cruz Verde, Salcobrand, Dr. Simi) can only be matched through
    # these, so a connector should pass through everything it can name.
    # Conventional keys: activeIngredient, dose, format, presentation,
    # isMedicine, category, requiresPrescription, isBioequivalent.
    attributes: dict | None = None


# Identifiable bot UA (ethics). Browser-like tokens only as secondary Accept fallback.
BOT_USER_AGENT = (
    "FarmaciaCompareBot/1.0 (+https://farmaciacompare.cl/bot; contact=bots@farmaciacompare.cl)"
)

# Some storefront CDNs still 403 pure bot UAs on public JSON. Prefer BOT first;
# connectors that hit hard blocks may set browser UA explicitly and document why.
BROWSER_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Back-compat alias
USER_AGENTS = BROWSER_USER_AGENTS


class BaseScraper(ABC):
    """Base class for all pharmacy scrapers."""

    chain: str           # override in subclass: 'cruz_verde', etc.
    base_url: str        # override in subclass
    # Prefer identifiable bot UA; set True only when a CDN blocks BOT_USER_AGENT.
    use_browser_ua: bool = False

    def __init__(self):
        if self.use_browser_ua:
            self.user_agent = random.choice(BROWSER_USER_AGENTS)
        else:
            self.user_agent = BOT_USER_AGENT

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

    def parse_machine_price(self, raw) -> int | None:
        """Parse a machine-formatted price where '.' is a decimal point.

        JSON APIs (Shopify variants, Algolia hits) return '7439' or '1004.0'.
        `parse_price` must not be used on those: it treats '.' as the Chilean
        thousands separator and would turn '1004.0' into 10040.
        """
        if raw in (None, ""):
            return None
        try:
            return int(float(raw))
        except (ValueError, TypeError):
            logger.warning(f"Could not parse machine price: {raw!r}")
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
