# FarmaciaCompare Phase 3 — Price Collection Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Build the automated price collection system — Playwright scrapers for Cruz Verde, Salcobrand, Ahumada, and Dr. Simi — plus VTEX/Magento API connectors, and the drug matching engine that links scraped products to the canonical medication database.

**Architecture:** Python 3.12 + Playwright workers that run on schedule (APScheduler), write raw price data to the prices table, and trigger the matching pipeline. VTEX API connector uses JSON search APIs directly. Each pharmacy scraper is an independent module implementing a common `BaseScraper` interface. Anti-detection via playwright-stealth, rotating user agents, and delays.

**Tech Stack:** Python 3.12, Poetry, playwright, playwright-stealth, APScheduler, SQLAlchemy async, rapidfuzz, httpx, pytest, pytest-asyncio.

**Prerequisites:** Phase 2 complete. ISP data imported. Docker running.

---

## Chunk 1: Scraper Base Infrastructure

### Task 1: Set up scraper worker package

**Files:**
- Create: `workers/scraper/pyproject.toml`
- Create: `workers/scraper/src/__init__.py`
- Create: `workers/scraper/src/base_scraper.py`
- Create: `workers/scraper/src/models.py`
- Create: `workers/scraper/src/db.py`
- Create: `workers/scraper/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p workers/scraper/src/pharmacies workers/scraper/src/connectors workers/scraper/tests
```

- [ ] **Step 2: Create `workers/scraper/pyproject.toml`**

```toml
[tool.poetry]
name = "farmacia-scraper"
version = "0.1.0"
description = "Pharmacy price scraping workers"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.12"
playwright = "^1.44.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
asyncpg = "^0.29.0"
rapidfuzz = "^3.9.0"
unidecode = "^1.3.0"
httpx = "^0.27.0"
python-dotenv = "^1.0.0"
click = "^8.1.0"
loguru = "^0.7.0"
apscheduler = "^3.10.0"
tenacity = "^8.3.0"  # retry logic

[tool.poetry.group.dev.dependencies]
pytest = "^8.2.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^5.0.0"

[tool.poetry.scripts]
scraper = "src.cli:main"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `workers/scraper/src/base_scraper.py`**

Every pharmacy scraper must implement this interface:

```python
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
```

- [ ] **Step 4: Write tests for BaseScraper utilities**

Create `workers/scraper/tests/test_base_scraper.py`:

```python
import pytest
from src.base_scraper import BaseScraper, ScrapedProduct


class ConcreteScraper(BaseScraper):
    chain = "test"
    base_url = "http://test.com"

    async def scrape_products(self):
        yield ScrapedProduct(
            sku="TEST-001", name="Test", brand=None, laboratory=None,
            price=1000, original_price=None, discount_pct=None,
            stock_status="in_stock", stock_quantity=None, barcode=None,
            url=None, image_url=None, pharmacy_chain="test", source="scraper"
        )


class TestParsePrice:
    def setup_method(self):
        self.scraper = ConcreteScraper()

    def test_dollar_sign_with_dots(self):
        assert self.scraper.parse_price("$12.990") == 12990

    def test_no_symbol(self):
        assert self.scraper.parse_price("12990") == 12990

    def test_with_comma(self):
        assert self.scraper.parse_price("12,990") == 12990

    def test_invalid_returns_none(self):
        assert self.scraper.parse_price("N/A") is None

    def test_empty_returns_none(self):
        assert self.scraper.parse_price("") is None

    def test_large_price(self):
        assert self.scraper.parse_price("$1.234.567") == 1234567


class TestParseStock:
    def setup_method(self):
        self.scraper = ConcreteScraper()

    def test_agotado(self):
        assert self.scraper.parse_stock("Agotado") == "out_of_stock"

    def test_sin_stock(self):
        assert self.scraper.parse_stock("Sin stock") == "out_of_stock"

    def test_ultimas_unidades(self):
        assert self.scraper.parse_stock("Últimas unidades") == "low_stock"

    def test_none_is_in_stock(self):
        assert self.scraper.parse_stock(None) == "in_stock"

    def test_disponible(self):
        assert self.scraper.parse_stock("Disponible") == "in_stock"
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd workers/scraper
poetry install
poetry run pytest tests/test_base_scraper.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add workers/scraper/
git commit -m "feat: scaffold scraper worker with BaseScraper interface and price/stock parsing"
```

---

## Chunk 2: VTEX API Connector

### Task 2: Build the VTEX API connector

VTEX is the e-commerce platform used by Cruz Verde and Salcobrand. Their product search and catalog APIs are accessible without authentication.

**Files:**
- Create: `workers/scraper/src/connectors/vtex_connector.py`
- Create: `workers/scraper/tests/test_vtex_connector.py`

- [ ] **Step 1: Write failing tests**

Create `workers/scraper/tests/test_vtex_connector.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.connectors.vtex_connector import VtexConnector, VtexConfig


class TestVtexConnector:
    @pytest.fixture
    def config(self):
        return VtexConfig(
            chain="cruz_verde",
            account_name="cruzverde",
            base_url="https://www.cruzverde.cl",
        )

    @pytest.fixture
    def connector(self, config):
        return VtexConnector(config)

    def test_builds_search_url(self, connector):
        url = connector.build_search_url(page=1, page_size=50)
        assert "cruzverde" in url or "cruzverde.vtexcommercestable.com.br" in url
        assert "from=0" in url or "_from=0" in url

    def test_parse_product_valid(self, connector):
        raw = {
            "productId": "12345",
            "productName": "Paracetamol 500mg x20 Comprimidos Cruz Verde",
            "brand": "Cruz Verde",
            "items": [{
                "itemId": "12345-001",
                "ean": "7891234567890",
                "sellers": [{
                    "commertialOffer": {
                        "Price": 2990,
                        "ListPrice": 3490,
                        "AvailableQuantity": 50,
                    }
                }]
            }]
        }
        products = connector.parse_product(raw)
        assert len(products) == 1
        p = products[0]
        assert p.price == 2990
        assert p.original_price == 3490
        assert p.stock_status == "in_stock"
        assert p.sku == "12345-001"

    def test_parse_product_out_of_stock(self, connector):
        raw = {
            "productId": "99999",
            "productName": "Test Med",
            "brand": None,
            "items": [{
                "itemId": "99999-001",
                "ean": None,
                "sellers": [{
                    "commertialOffer": {
                        "Price": 0,
                        "ListPrice": 1000,
                        "AvailableQuantity": 0,
                    }
                }]
            }]
        }
        products = connector.parse_product(raw)
        assert products[0].stock_status == "out_of_stock"

    def test_parse_product_missing_items_skipped(self, connector):
        raw = {"productId": "X", "productName": "Empty", "brand": None, "items": []}
        products = connector.parse_product(raw)
        assert products == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
poetry run pytest tests/test_vtex_connector.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `workers/scraper/src/connectors/vtex_connector.py`**

```python
from dataclasses import dataclass
from typing import AsyncIterator
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from ..base_scraper import BaseScraper, ScrapedProduct


@dataclass
class VtexConfig:
    chain: str                # 'cruz_verde', 'salcobrand', 'ahumada'
    account_name: str         # VTEX account identifier
    base_url: str             # pharmacy website base URL


# VTEX store configurations discovered via DevTools network inspection
VTEX_CONFIGS = {
    "cruz_verde": VtexConfig(
        chain="cruz_verde",
        account_name="cruzverde",
        base_url="https://www.cruzverde.cl",
    ),
    "salcobrand": VtexConfig(
        chain="salcobrand",
        account_name="salcobrand",
        base_url="https://www.salcobrand.cl",
    ),
    "ahumada": VtexConfig(
        chain="ahumada",
        account_name="farmaciasahumada",
        base_url="https://www.farmaciasahumada.cl",
    ),
}


class VtexConnector(BaseScraper):
    """
    Connector for pharmacies running on VTEX e-commerce platform.
    Uses VTEX's internal search API (same API the frontend uses).
    No auth required — these are public catalog endpoints.
    """

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
        return self.VTEX_API_TEMPLATE.format(
            account=self.config.account_name,
            from_=from_,
            to=to,
        )

    def parse_product(self, raw: dict) -> list[ScrapedProduct]:
        """Parse a VTEX product object into ScrapedProduct instances (one per SKU)."""
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
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Referer": self.base_url,
        }
        response = await client.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        """Iterate through all products using VTEX paginated API."""
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
                    logger.info(f"[{self.chain}] No more products at page {page}")
                    break

                for raw in raw_products:
                    for product in self.parse_product(raw):
                        yield product
                        total_scraped += 1

                logger.info(f"[{self.chain}] Page {page}: {len(raw_products)} products, total: {total_scraped}")
                await self.random_delay()
                page += 1
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
poetry run pytest tests/test_vtex_connector.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add workers/scraper/src/connectors/ workers/scraper/tests/
git commit -m "feat: implement VTEX API connector for Cruz Verde, Salcobrand, Ahumada"
```

---

## Chunk 3: Playwright Scrapers

### Task 3: Dr. Simi Playwright scraper

Dr. Simi uses a custom platform (not VTEX), so we use Playwright.

**Files:**
- Create: `workers/scraper/src/pharmacies/dr_simi.py`
- Create: `workers/scraper/tests/test_dr_simi.py`

- [ ] **Step 1: Install Playwright browsers**

```bash
cd workers/scraper
poetry run playwright install chromium
```

- [ ] **Step 2: Write tests with mocked playwright**

Create `workers/scraper/tests/test_dr_simi.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.pharmacies.dr_simi import DrSimiScraper


class TestDrSimiScraper:
    def test_parse_price_from_text(self):
        scraper = DrSimiScraper()
        assert scraper.parse_price("$4.990") == 4990
        assert scraper.parse_price("4990") == 4990

    def test_parse_product_row(self):
        scraper = DrSimiScraper()
        # Simulate parsed product data as DrSimi returns it
        raw = {
            "sku": "DR-001",
            "name": "Tapsin Forte 500mg x20 Comprimidos",
            "price": "$3.490",
            "original_price": None,
            "stock": "Disponible",
        }
        product = scraper.parse_product_row(raw)
        assert product.price == 3490
        assert product.stock_status == "in_stock"
        assert product.pharmacy_chain == "dr_simi"
        assert product.source == "scraper"
```

- [ ] **Step 3: Implement `workers/scraper/src/pharmacies/dr_simi.py`**

```python
from typing import AsyncIterator
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser
from tenacity import retry, stop_after_attempt, wait_exponential
from ..base_scraper import BaseScraper, ScrapedProduct


class DrSimiScraper(BaseScraper):
    """
    Playwright-based scraper for Dr. Simi (farmaciasimilares.cl or drsimi.cl).
    Uses headless Chromium to render JavaScript-heavy pages.
    """

    chain = "dr_simi"
    base_url = "https://www.farmaciasimilares.cl"
    CATALOG_URL = f"{base_url}/medicamentos"
    PAGE_SIZE = 24

    def parse_product_row(self, raw: dict) -> ScrapedProduct:
        return ScrapedProduct(
            sku=raw.get("sku", ""),
            name=raw.get("name", ""),
            brand="Dr. Simi",
            laboratory=None,
            price=self.parse_price(raw.get("price", "0")),
            original_price=self.parse_price(raw.get("original_price")) if raw.get("original_price") else None,
            discount_pct=None,
            stock_status=self.parse_stock(raw.get("stock")),
            stock_quantity=None,
            barcode=None,
            url=raw.get("url"),
            image_url=raw.get("image_url"),
            pharmacy_chain=self.chain,
            source="scraper",
        )

    async def _scrape_page(self, page: Page, page_num: int) -> list[ScrapedProduct]:
        url = f"{self.CATALOG_URL}?page={page_num}"
        logger.info(f"[dr_simi] Scraping page {page_num}: {url}")

        await page.goto(url, wait_until="networkidle", timeout=30000)
        await self.random_delay()

        # Wait for product cards to render
        try:
            await page.wait_for_selector("[data-product-id], .product-card, .vtex-product-summary", timeout=10000)
        except Exception:
            logger.warning(f"[dr_simi] No product cards found on page {page_num}")
            return []

        products = await page.evaluate("""
            () => {
                const cards = document.querySelectorAll('[data-product-id], .product-card');
                return Array.from(cards).map(card => ({
                    sku: card.dataset.productId || card.dataset.sku || '',
                    name: card.querySelector('.product-name, h3, .vtex-product-summary__name')?.textContent?.trim() || '',
                    price: card.querySelector('.price, .sellingPrice, [class*="price"]')?.textContent?.trim() || '0',
                    original_price: card.querySelector('.listPrice, [class*="listPrice"]')?.textContent?.trim() || null,
                    stock: card.querySelector('.stock-status, .availability')?.textContent?.trim() || null,
                    url: card.querySelector('a')?.href || null,
                    image_url: card.querySelector('img')?.src || null,
                }));
            }
        """)

        return [self.parse_product_row(p) for p in products if p.get("sku") and p.get("name")]

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=self.user_agent,
                viewport={"width": 1366, "height": 768},
                locale="es-CL",
            )
            page = await context.new_page()

            # Block images and fonts to speed up loading
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}",
                lambda route: route.abort()
            )

            page_num = 1
            empty_pages = 0

            while empty_pages < 3:
                try:
                    products = await self._scrape_page(page, page_num)
                    if not products:
                        empty_pages += 1
                        logger.info(f"[dr_simi] Empty page {page_num}, streak: {empty_pages}")
                    else:
                        empty_pages = 0
                        for product in products:
                            yield product

                    page_num += 1
                    await self.random_delay(1000, 3000)

                except Exception as e:
                    logger.error(f"[dr_simi] Error on page {page_num}: {e}")
                    empty_pages += 1
                    page_num += 1

            await browser.close()
```

- [ ] **Step 4: Run unit tests**

```bash
poetry run pytest tests/test_dr_simi.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add workers/scraper/src/pharmacies/
git commit -m "feat: implement Dr. Simi Playwright scraper"
```

---

## Chunk 4: Drug Matching Engine

### Task 4: Build the scraped product → medication matcher

**Files:**
- Create: `workers/scraper/src/matcher.py`
- Create: `workers/scraper/tests/test_matcher.py`

- [ ] **Step 1: Write failing tests**

```python
# workers/scraper/tests/test_matcher.py
import pytest
from src.matcher import DrugMatcher, MatchResult


class TestDrugMatcher:
    @pytest.fixture
    def candidates(self):
        """Simulated medication name index from database."""
        return [
            {"medication_id": "med-001", "normalized_name": "paracetamol 500mg comprimido"},
            {"medication_id": "med-002", "normalized_name": "ibuprofeno 400mg capsula"},
            {"medication_id": "med-003", "normalized_name": "amoxicilina 500mg capsula"},
            {"medication_id": "med-001", "normalized_name": "tapsin forte 500mg comprimido"},
            {"medication_id": "med-001", "normalized_name": "panadol 500mg comprimido"},
        ]

    @pytest.fixture
    def matcher(self, candidates):
        return DrugMatcher(candidates)

    def test_exact_name_match(self, matcher):
        result = matcher.match("panadol 500mg comprimido")
        assert result is not None
        assert result.medication_id == "med-001"
        assert result.confidence >= 0.95

    def test_fuzzy_name_match(self, matcher):
        result = matcher.match("TAPSIN FORTE 500MG C/20 COMP")
        assert result is not None
        assert result.medication_id == "med-001"
        assert result.confidence >= 0.80

    def test_generic_name_match(self, matcher):
        result = matcher.match("paracetamol 500mg tabletas")
        assert result is not None
        assert result.medication_id == "med-001"

    def test_no_match_below_threshold(self, matcher):
        result = matcher.match("vitamina c efervescente 1g")
        # Should return None or low confidence if below threshold
        if result:
            assert result.confidence < 0.75

    def test_different_dosage_low_confidence(self, matcher):
        result = matcher.match("paracetamol 1000mg comprimido")
        # Different dosage should reduce confidence
        if result:
            assert result.confidence < 0.95
```

- [ ] **Step 2: Run tests — confirm failure**

```bash
poetry run pytest tests/test_matcher.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `workers/scraper/src/matcher.py`**

```python
from dataclasses import dataclass
from rapidfuzz import process, fuzz
from unidecode import unidecode
import re


def normalize_for_matching(text: str) -> str:
    """Lowercase, remove accents, collapse whitespace, remove special chars."""
    text = text.lower().strip()
    text = unidecode(text)
    text = re.sub(r"[®™©]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class MatchResult:
    medication_id: str
    matched_name: str
    confidence: float           # 0.0 - 1.0


class DrugMatcher:
    """
    Fuzzy-matches scraped product names against the canonical medication database.

    Uses RapidFuzz WRatio scorer (combines multiple string similarity algorithms)
    to find the best match among all known medication names.
    """

    THRESHOLD = 75.0    # below this score, we don't auto-link
    AUTO_LINK_THRESHOLD = 85.0  # above this, auto-link without review

    def __init__(self, candidates: list[dict]):
        """
        candidates: list of {"medication_id": str, "normalized_name": str}
        """
        self.candidates = candidates
        self.names = [c["normalized_name"] for c in candidates]

    def match(self, raw_name: str) -> MatchResult | None:
        """Find the best medication match for a scraped product name."""
        if not raw_name or not self.names:
            return None

        normalized = normalize_for_matching(raw_name)

        results = process.extract(
            normalized,
            self.names,
            scorer=fuzz.WRatio,
            limit=3,
        )

        if not results:
            return None

        best_name, best_score, best_idx = results[0]

        if best_score < self.THRESHOLD:
            return None

        medication_id = self.candidates[best_idx]["medication_id"]
        return MatchResult(
            medication_id=medication_id,
            matched_name=best_name,
            confidence=best_score / 100.0,
        )

    def match_all(self, raw_names: list[str]) -> dict[str, MatchResult | None]:
        """Batch match a list of raw names."""
        return {name: self.match(name) for name in raw_names}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
poetry run pytest tests/test_matcher.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add workers/scraper/
git commit -m "feat: implement fuzzy drug matcher using RapidFuzz WRatio"
```

---

## Chunk 5: Price Writer + Scheduler

### Task 5: Persist scraped prices and schedule jobs

**Files:**
- Create: `workers/scraper/src/price_writer.py`
- Create: `workers/scraper/src/scheduler.py`
- Create: `workers/scraper/src/cli.py`

- [ ] **Step 1: Create `workers/scraper/src/price_writer.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from .base_scraper import ScrapedProduct
from .matcher import DrugMatcher, MatchResult


class PriceWriter:
    """
    Persists scraped products and their prices to the database.
    Also runs drug matching to link products to the canonical catalog.
    """

    def __init__(self, session: AsyncSession, pharmacy_id: str, matcher: DrugMatcher):
        self.session = session
        self.pharmacy_id = pharmacy_id
        self.matcher = matcher

    async def write_product(self, product: ScrapedProduct) -> dict:
        # Upsert pharmacy_product
        result = await self.session.execute(
            text("""
                INSERT INTO pharmacy_products (id, pharmacy_id, sku, raw_name, brand, laboratory, barcode, source, is_active)
                VALUES (:id, :pharmacy_id, :sku, :raw_name, :brand, :laboratory, :barcode, :source, true)
                ON CONFLICT (pharmacy_id, sku) DO UPDATE SET
                    raw_name = EXCLUDED.raw_name,
                    brand = EXCLUDED.brand,
                    is_active = true,
                    updated_at = NOW()
                RETURNING id, medication_id
            """),
            {
                "id": str(uuid.uuid4()),
                "pharmacy_id": self.pharmacy_id,
                "sku": product.sku,
                "raw_name": product.name,
                "brand": product.brand,
                "laboratory": product.laboratory,
                "barcode": product.barcode,
                "source": product.source,
            }
        )
        row = result.fetchone()
        pharmacy_product_id = str(row[0])
        existing_medication_id = row[1]

        # Run drug matching if not already linked
        medication_id = existing_medication_id
        if not medication_id:
            match = self.matcher.match(product.name)
            if match and match.confidence >= 0.85:
                medication_id = match.medication_id
                await self.session.execute(
                    text("UPDATE pharmacy_products SET medication_id = :mid WHERE id = :id"),
                    {"mid": medication_id, "id": pharmacy_product_id}
                )

        # Insert price record (always append)
        if product.price > 0:
            await self.session.execute(
                text("""
                    INSERT INTO prices (id, pharmacy_product_id, price, original_price, discount_pct, stock_status, stock_quantity, source)
                    VALUES (:id, :ppid, :price, :original_price, :discount_pct, :stock_status, :stock_quantity, :source)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "ppid": pharmacy_product_id,
                    "price": product.price,
                    "original_price": product.original_price,
                    "discount_pct": product.discount_pct,
                    "stock_status": product.stock_status,
                    "stock_quantity": product.stock_quantity,
                    "source": product.source,
                }
            )

        return {"pharmacy_product_id": pharmacy_product_id, "medication_id": medication_id}

    async def write_batch(self, products: list[ScrapedProduct]) -> dict:
        stats = {"written": 0, "errors": 0}
        batch = []

        for product in products:
            batch.append(product)
            if len(batch) >= 100:
                for p in batch:
                    try:
                        await self.write_product(p)
                        stats["written"] += 1
                    except Exception as e:
                        logger.error(f"Error writing product {p.sku}: {e}")
                        stats["errors"] += 1
                await self.session.commit()
                batch = []

        if batch:
            for p in batch:
                try:
                    await self.write_product(p)
                    stats["written"] += 1
                except Exception as e:
                    logger.error(f"Error writing product {p.sku}: {e}")
                    stats["errors"] += 1
            await self.session.commit()

        return stats
```

- [ ] **Step 2: Create `workers/scraper/src/scheduler.py`**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
import asyncio


async def run_vtex_scrape(chain: str):
    """Run VTEX API connector for a given chain."""
    from .connectors.vtex_connector import VtexConnector, VTEX_CONFIGS
    from .db import AsyncSessionLocal
    from .price_writer import PriceWriter
    from .matcher import DrugMatcher
    from sqlalchemy import text

    config = VTEX_CONFIGS.get(chain)
    if not config:
        logger.error(f"Unknown VTEX chain: {chain}")
        return

    logger.info(f"Starting VTEX scrape for {chain}")
    connector = VtexConnector(config)

    async with AsyncSessionLocal() as session:
        # Load medication names for matching
        result = await session.execute(
            text("SELECT medication_id, normalized_name FROM medication_names")
        )
        candidates = [{"medication_id": str(r[0]), "normalized_name": r[1]} for r in result]
        matcher = DrugMatcher(candidates)

        # Get pharmacy_id for this chain
        pharmacy_result = await session.execute(
            text("SELECT id FROM pharmacies WHERE chain = :chain LIMIT 1"),
            {"chain": chain}
        )
        pharmacy_row = pharmacy_result.fetchone()
        if not pharmacy_row:
            logger.warning(f"No pharmacy found for chain {chain}. Creating placeholder.")
            # Pharmacies will be seeded via admin — for now skip
            return

        pharmacy_id = str(pharmacy_row[0])
        writer = PriceWriter(session, pharmacy_id, matcher)

        products = []
        async for product in connector.scrape_products():
            products.append(product)
            if len(products) >= 500:
                stats = await writer.write_batch(products)
                logger.info(f"[{chain}] Batch written: {stats}")
                products = []

        if products:
            stats = await writer.write_batch(products)
            logger.info(f"[{chain}] Final batch: {stats}")

    logger.info(f"Scrape complete for {chain}")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    # Run VTEX scrapers every 4 hours
    for chain in ["cruz_verde", "salcobrand", "ahumada"]:
        scheduler.add_job(
            run_vtex_scrape,
            "interval",
            hours=4,
            args=[chain],
            id=f"vtex_{chain}",
            name=f"VTEX scrape: {chain}",
            replace_existing=True,
        )

    # Dr. Simi Playwright scraper every 6 hours
    # (slower due to browser overhead)
    # scheduler.add_job(run_dr_simi_scrape, "interval", hours=6, ...)

    return scheduler


async def main():
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scraper scheduler started")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
```

- [ ] **Step 3: Create `workers/scraper/src/cli.py`**

```python
import asyncio
import click
from loguru import logger


@click.group()
def main():
    """FarmaciaCompare price scraper CLI."""
    pass


@main.command()
@click.argument("chain", type=click.Choice(["cruz_verde", "salcobrand", "ahumada", "dr_simi"]))
@click.option("--limit", default=0, help="Max products to scrape (0 = all)")
@click.option("--dry-run", is_flag=True)
def scrape(chain: str, limit: int, dry_run: bool):
    """Run scraper for a specific pharmacy chain."""
    asyncio.run(_scrape(chain, limit, dry_run))


async def _scrape(chain: str, limit: int, dry_run: bool):
    from .scheduler import run_vtex_scrape

    vtex_chains = ["cruz_verde", "salcobrand", "ahumada"]
    if chain in vtex_chains:
        if dry_run:
            from .connectors.vtex_connector import VtexConnector, VTEX_CONFIGS
            connector = VtexConnector(VTEX_CONFIGS[chain])
            count = 0
            async for product in connector.scrape_products():
                logger.info(f"{product.sku} | {product.name[:50]} | ${product.price:,}")
                count += 1
                if limit and count >= limit:
                    break
        else:
            await run_vtex_scrape(chain)
    elif chain == "dr_simi":
        from .pharmacies.dr_simi import DrSimiScraper
        scraper = DrSimiScraper()
        count = 0
        async for product in scraper.scrape_products():
            if dry_run:
                logger.info(f"{product.sku} | {product.name[:50]} | ${product.price:,}")
            count += 1
            if limit and count >= limit:
                break


@main.command()
def start_scheduler():
    """Start the price collection scheduler (runs continuously)."""
    from .scheduler import main as scheduler_main
    asyncio.run(scheduler_main())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test dry-run scrape**

```bash
cd workers/scraper
poetry run scraper scrape cruz_verde --dry-run --limit 10
```

Expected: 10 product lines printed with names and prices.

- [ ] **Step 5: Run all scraper tests**

```bash
poetry run pytest -v --cov=src
```

Expected: All PASS, >70% coverage.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add workers/scraper/
git commit -m "feat: implement price writer, VTEX API connector, scheduler, and CLI"
```

---

## Phase 3 Complete

**What was built:**
- `BaseScraper` interface with price/stock parsing utilities
- VTEX API connector (Cruz Verde, Salcobrand, Ahumada) — no browser needed
- Dr. Simi Playwright scraper (headless Chromium)
- Drug matching engine (RapidFuzz fuzzy matching)
- Price writer with upsert logic and batch commits
- APScheduler for periodic collection (4h VTEX, 6h Playwright)
- CLI: `scraper scrape <chain>` and `scraper start-scheduler`

**Next:** Phase 4 — Core Web App (medication search UI, price comparison, pharmacy map).

See: `docs/superpowers/plans/2026-03-11-farmaciacompare-phase-4-web.md`
