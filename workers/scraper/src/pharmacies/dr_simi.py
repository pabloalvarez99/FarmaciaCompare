from typing import AsyncIterator
from loguru import logger
from playwright.async_api import async_playwright, Page, Browser
from ..base_scraper import BaseScraper, ScrapedProduct


class DrSimiScraper(BaseScraper):
    chain = "dr_simi"
    base_url = "https://www.farmaciasimilares.cl"
    CATALOG_URL = f"{base_url}/medicamentos"
    PAGE_SIZE = 24

    # Placeholders a lazy-loading storefront puts in `src` before the real photo
    # loads. `scrape_products` aborts every image request, so those placeholders
    # are exactly what a naive `img.src` read would capture.
    PLACEHOLDER_IMAGE_MARKERS = (
        "data:image", "blank.", "placeholder", "spacer.", "loading.", "1x1.",
    )

    @classmethod
    def clean_image_url(cls, raw_url: str | None) -> str | None:
        """Reject placeholder/sprite srcs so a broken image is never stored."""
        if not raw_url:
            return None
        url = raw_url.strip()
        if not url.startswith("http"):
            return None
        lowered = url.lower()
        if any(marker in lowered for marker in cls.PLACEHOLDER_IMAGE_MARKERS):
            return None
        return url

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
            image_url=self.clean_image_url(raw.get("image_url")),
            pharmacy_chain=self.chain,
            source="scraper",
        )

    async def _scrape_page(self, page: Page, page_num: int) -> list[ScrapedProduct]:
        url = f"{self.CATALOG_URL}?page={page_num}"
        logger.info(f"[dr_simi] Scraping page {page_num}: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await self.random_delay()
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
                    // The first <img> in a card can be a "bioequivalente" badge
                    // or the chain logo, so target the product image first and
                    // read the lazy-load attributes before `src` — image
                    // requests are aborted, so `src` may still hold the
                    // placeholder the storefront ships with.
                    image_url: (() => {
                        const img =
                            card.querySelector('img.product-image, [class*="productImage"] img, [class*="product-image"] img') ||
                            card.querySelector('img');
                        if (!img) return null;
                        const srcset = img.getAttribute('srcset') || img.getAttribute('data-srcset');
                        const fromSet = srcset
                            ? srcset.split(',').pop().trim().split(/\s+/)[0]
                            : null;
                        return (
                            img.getAttribute('data-src') ||
                            fromSet ||
                            img.getAttribute('src') ||
                            null
                        );
                    })(),
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
            await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}", lambda route: route.abort())
            page_num = 1
            empty_pages = 0
            while empty_pages < 3:
                try:
                    products = await self._scrape_page(page, page_num)
                    if not products:
                        empty_pages += 1
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
