"""Farmacias Knop — Bolder storefront read through its public products JSON.

knop.cl is only the laboratory's corporate WordPress site (it 301s to
knoplabs.com and has no catalog). The retail chain sells at
www.farmaciasknop.com, which runs on Bolder (assets on static.bolder.run /
r.bolder.run), not Shopify.

Bolder publishes two unauthenticated JSON routes:

  * /products.json?page=N — paginated catalog envelope
    {"page", "per_page", "total_items", "total_pages", "products": [...]}.
    per_page is pinned server-side at 24 and ignores limit/per_page, so the
    whole catalog is ~70 pages. The list rows carry no SKU and no attributes.
  * /products/<slug>.json — the full product, including `variants` (each with
    an EAN-13 `sku`, its own price and `online_stock`), `attributes`
    (Cantidad, Unidad de medida, Ingredientes, Marca, ...), `collections`
    and `tags`.

robots.txt allows everything except /cart, /admin, /console and /preview/dev,
and advertises https://www.farmaciasknop.com/sitemap.xml. The sitemap lists
every product URL, so discovery costs one request instead of ~70 and uses the
route the site itself sanctions. Paginating /products.json is kept only as a
fallback for when the sitemap is unreachable.
"""
import re
from dataclasses import dataclass
from typing import Any, AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, fetch_sitemap_urls, gather_limited, get_json

PRODUCT_PATH_RE = re.compile(r"/products/([^/?#]+?)(?:\.json)?/?$")

# Warehouse/campaign labels Bolder's tag field is also used for: "PPUM 100",
# "carga2", "car3", "060426". They say nothing about the product.
INTERNAL_TAG_RE = re.compile(r"^(ppum\b|carga\s*\d*$|car\d+$|\d+$)", re.IGNORECASE)

# Knop left four staging rows live in the catalog: "test test" at $50, "MePa"
# at $80, "Test prueba" at $500 and "test retail" at $1.000.000. The cheap ones
# would win any "cheapest price" ranking and the expensive one is a fake
# outlier. anomaly.check_price only floors them at 200 CLP, so two survive.
# Both signals below were verified against all 1655 products: together they
# match exactly those four rows and no real product. Name matching is
# deliberately avoided — "Test de Embarazo" is a genuine pregnancy test.
PLACEHOLDER_SKU_RE = re.compile(r"^1234567\d*$")


@dataclass
class KnopConfig:
    chain: str
    base_url: str
    sitemap_url: str
    # Bolder pins the page size at 24 and ignores limit/per_page; this value
    # only exists so the fallback pager can log sane numbers.
    page_size: int = 24
    max_pages: int = 200
    concurrency: int = 4
    chunk_size: int = 100


KNOP_CONFIGS: dict[str, KnopConfig] = {
    "knop": KnopConfig(
        chain="knop",
        base_url="https://www.farmaciasknop.com",
        sitemap_url="https://www.farmaciasknop.com/sitemap.xml",
    ),
}


class KnopConnector(BaseScraper):
    # BOT_USER_AGENT is served 200 on the sitemap, /products.json and the
    # per-product JSON, so the identifiable UA stays (no use_browser_ua).

    # The store is mostly supplements and cosmetics, so "unknown means drug"
    # (the Shopify connector's rule) would be wrong here. Knop publishes the
    # flag two ways instead: product_type `medicamentos`, and a "Medicamentos"
    # tag that also rides on ailment-shaped categories (varices, migrana,
    # colicos, ...). Either one is an explicit claim by the site.
    MEDICINE_TYPES = {"medicamentos"}
    MEDICINE_TAGS = {"medicamentos", "medicamento"}

    def __init__(self, config: KnopConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    # --- URLs ------------------------------------------------------------

    def build_page_url(self, page: int) -> str:
        return f"{self.base_url}/products.json?page={page}"

    def detail_url(self, slug: str) -> str:
        return f"{self.base_url}/products/{slug}.json"

    @staticmethod
    def extract_slug(url: str) -> str | None:
        match = PRODUCT_PATH_RE.search(url or "")
        return match.group(1) if match else None

    # --- parsing ---------------------------------------------------------

    @staticmethod
    def _attribute_map(raw: dict) -> dict[str, str]:
        """Flatten `attributes` into slug -> value, keeping only real values."""
        flat: dict[str, str] = {}
        for attribute in raw.get("attributes") or []:
            if not isinstance(attribute, dict):
                continue
            slug = (attribute.get("slug") or attribute.get("name") or "").strip().lower()
            value = attribute.get("value")
            if not slug or value in (None, ""):
                continue
            text = str(value).strip()
            if text:
                flat.setdefault(slug, text)
        return flat

    @classmethod
    def _clean_tags(cls, raw: dict) -> list[str]:
        tags = [t for t in (raw.get("tags") or []) if isinstance(t, str)]
        return [t.strip() for t in tags if t.strip() and not INTERNAL_TAG_RE.match(t.strip())]

    @classmethod
    def extract_attributes(cls, raw: dict) -> dict:
        attributes: dict[str, Any] = {}

        product_type = raw.get("product_type") or {}
        type_name = (product_type.get("name") or "").strip()
        type_slug = (product_type.get("slug") or "").strip().lower()
        if type_name:
            attributes["category"] = type_name

        tags = cls._clean_tags(raw)
        lower_tags = {t.lower() for t in tags}
        is_medicine = bool(type_slug in cls.MEDICINE_TYPES or lower_tags & cls.MEDICINE_TAGS)
        # Only claim isMedicine when the site actually said something about the
        # product; an untyped, untagged row is unknown, not "not a medicine".
        if type_slug or tags:
            attributes["isMedicine"] = is_medicine

        flat = cls._attribute_map(raw)

        # "Cantidad" + "Unidad de medida" is how Knop publishes pack size:
        # 50 + ML, 30 + CAPS, 90 + COMP.
        quantity = flat.get("cantidad")
        unit = flat.get("unidad de medida") or flat.get("unidad-de-medida")
        if quantity and unit:
            attributes["presentation"] = f"{quantity} {unit}"
        elif quantity:
            attributes["presentation"] = quantity
        presentation = flat.get("presentacion") or flat.get("presentación")
        if presentation and "presentation" not in attributes:
            attributes["presentation"] = presentation

        fmt = flat.get("formato") or unit
        if fmt:
            attributes["format"] = fmt

        # Knop lists the full ingredient panel, not an isolated API, so this is
        # deliberately NOT reported as `activeIngredient`.
        ingredients = flat.get("ingredientes")
        if ingredients:
            attributes["ingredients"] = ingredients[:500]

        brand = flat.get("marca")
        if brand:
            attributes["brand"] = brand

        if tags:
            attributes["tags"] = tags[:10]

        return attributes

    @staticmethod
    def _image_for(raw: dict, variant_id: Any) -> str | None:
        images = [i for i in (raw.get("images") or []) if isinstance(i, dict)]

        def pick(image: dict) -> str | None:
            src = image.get("src")
            if isinstance(src, dict):
                for size in ("large", "original", "medium", "small", "thumbnail"):
                    if src.get(size):
                        return src[size]
                return None
            return src or None

        for image in images:
            if variant_id is not None and variant_id in (image.get("variant_ids") or []):
                url = pick(image)
                if url:
                    return url
        for image in images:
            url = pick(image)
            if url:
                return url
        fallback = raw.get("image")
        return fallback if isinstance(fallback, str) and fallback else None

    def _stock_status(self, variant: dict) -> str:
        if not variant.get("available"):
            return "out_of_stock"
        quantity = variant.get("online_stock")
        if isinstance(quantity, int) and 0 < quantity <= 3:
            return "low_stock"
        return "in_stock"

    def _variant_name(self, product_name: str, variant: dict) -> str:
        variant_name = (variant.get("name") or "").strip()
        if not variant_name or variant_name == product_name:
            return product_name
        # Multi-size products come both ways: variants named "125 mL" (append)
        # and variants already named with the full title (don't duplicate it).
        if variant_name.lower() in product_name.lower():
            return product_name
        if product_name.lower() in variant_name.lower():
            return variant_name
        return f"{product_name} - {variant_name}"

    @staticmethod
    def _is_staging_row(raw: dict, vendor_name: str | None, variants: list[dict]) -> bool:
        """A product with neither a seller nor a single barcode is not a real listing."""
        if vendor_name:
            return False
        return not any(str(v.get("sku") or "").strip() for v in variants)

    def parse_product(self, raw: dict) -> list[ScrapedProduct]:
        name = (raw.get("name") or raw.get("model") or "").strip()
        if not name:
            return []
        # Bolder keeps delisted products in the feed with blocked=true. They are
        # not purchasable and would show up as phantom offers.
        if raw.get("blocked"):
            return []

        vendor = raw.get("vendor") or {}
        vendor_name = (vendor.get("name") or "").strip() or None
        attributes = self.extract_attributes(raw) or None

        slug = raw.get("slug")
        url = raw.get("url") or (f"{self.base_url}/products/{slug}" if slug else None)

        variants = [v for v in (raw.get("variants") or []) if isinstance(v, dict)]
        if not variants:
            # List rows have no `variants`; synthesise one from the product body
            # so a fallback-pager run still produces offers.
            variants = [{
                "id": raw.get("id"),
                "name": name,
                "sku": None,
                "price": raw.get("price"),
                "regular_price": raw.get("regular_price"),
                "available": raw.get("available"),
                "online_stock": None,
            }]

        if self._is_staging_row(raw, vendor_name, variants):
            logger.debug(f"[{self.chain}] skipping staging row {raw.get('slug')!r}")
            return []

        results: list[ScrapedProduct] = []
        for variant in variants:
            # JSON API: '.' would be a decimal point, never a thousands
            # separator — parse_price here would turn 1004.0 into 10040.
            price = self.parse_machine_price(variant.get("price"))
            if not price:
                # A $0 row is a placeholder (pack component, phone-order item),
                # not an offer, and would win any "cheapest price" ranking.
                continue

            regular = self.parse_machine_price(variant.get("regular_price"))
            original_price = regular if regular and regular > price else None
            discount_pct = round((1 - price / original_price) * 100) if original_price else None

            barcode = variant.get("sku")
            barcode = str(barcode).strip() if barcode not in (None, "") else None
            if barcode and PLACEHOLDER_SKU_RE.match(barcode):
                logger.debug(f"[{self.chain}] skipping placeholder sku {barcode} on {raw.get('slug')!r}")
                continue

            sku = str(variant.get("id") or barcode or raw.get("id") or "")
            quantity = variant.get("online_stock")

            results.append(ScrapedProduct(
                sku=sku,
                name=self._variant_name(name, variant),
                brand=vendor_name,
                laboratory=vendor_name,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                stock_status=self._stock_status(variant),
                stock_quantity=quantity if isinstance(quantity, int) else None,
                barcode=barcode,
                url=url,
                image_url=self._image_for(raw, variant.get("id")),
                pharmacy_chain=self.chain,
                source="api",
                attributes=attributes,
            ))
        return results

    # --- discovery -------------------------------------------------------

    async def discover_slugs(self, client) -> list[str]:
        """Product slugs from the robots.txt-advertised sitemap, pager as backup."""
        slugs: list[str] = []
        seen: set[str] = set()

        try:
            urls = await fetch_sitemap_urls(client, self.config.sitemap_url)
        except Exception as exc:
            logger.error(f"[{self.chain}] sitemap fetch failed: {exc}")
            urls = []

        for url in urls:
            if "/products/" not in url:
                continue
            slug = self.extract_slug(url)
            if slug and slug not in seen:
                seen.add(slug)
                slugs.append(slug)

        if slugs:
            logger.info(f"[{self.chain}] sitemap yielded {len(slugs)} product slugs")
            return slugs

        logger.warning(f"[{self.chain}] sitemap empty, falling back to /products.json paging")
        for page in range(1, self.config.max_pages + 1):
            try:
                payload = await get_json(client, self.build_page_url(page))
            except Exception as exc:
                logger.error(f"[{self.chain}] page {page} failed: {exc}")
                break
            rows = payload.get("products") or []
            if not rows:
                break
            for row in rows:
                slug = row.get("slug")
                if slug and slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
            if page >= (payload.get("total_pages") or self.config.max_pages):
                break
            await self.random_delay(200, 600)

        logger.info(f"[{self.chain}] pager yielded {len(slugs)} product slugs")
        return slugs

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        async with build_client(self.user_agent, {"Accept": "application/json"}) as client:
            slugs = await self.discover_slugs(client)
            if not slugs:
                logger.error(f"[{self.chain}] no product slugs discovered, nothing to scrape")
                return

            # Bounded concurrency: ~1.7k detail fetches sequentially with delays
            # runs long enough to time the DB session out. 4 workers keeps the
            # load polite and the run inside a single session.
            emitted = 0
            for start in range(0, len(slugs), self.config.chunk_size):
                chunk = slugs[start : start + self.config.chunk_size]

                async def fetch_one(slug: str):
                    try:
                        return await get_json(client, self.detail_url(slug))
                    except Exception as exc:
                        logger.warning(f"[{self.chain}] detail failed for {slug}: {exc}")
                        return None

                payloads = await gather_limited(chunk, fetch_one, concurrency=self.config.concurrency)
                for payload in payloads:
                    if not isinstance(payload, dict):
                        continue
                    for product in self.parse_product(payload):
                        emitted += 1
                        yield product

                done = min(start + len(chunk), len(slugs))
                logger.info(f"[{self.chain}] {done}/{len(slugs)} fetched, {emitted} emitted")
                await self.random_delay(400, 900)
