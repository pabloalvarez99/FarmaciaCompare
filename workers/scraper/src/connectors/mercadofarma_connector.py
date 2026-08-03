"""MercadoFarma — Shopify storefront with its own medicine vocabulary.

Platform proof: robots.txt opens with "# Shopify storefront", the homepage
carries ~1000 `shopify` tokens, and /products.json?limit=250&page=N returns the
whole catalog unauthenticated (20 pages, 4970 products, 1 variant each).

robots.txt allows /products.json — the only AJAX surfaces it disallows are
/cart.js and /recommendations/products, plus the usual /cart, /checkout,
/account, /admin. We never touch those: this is a read-only price comparator,
and the file's "checkouts are for humans" clause is honoured by construction.

Why this is NOT a `ShopifyConfig` entry on `shopify_connector.py`
----------------------------------------------------------------
Two things about MercadoFarma's payload break the shared connector, and neither
can be expressed as config:

1. Inverted `product_type` vocabulary. MercadoFarma does not publish category
   names ("Dermocosmetica", "Belleza"); it publishes a binary flag, literally
   "medicamento" / "sin medicamento" — and misspells it six ways
   ("sin medicaento", "sin medicamnto", "medicamaento", ...). ShopifyConnector
   checks membership in NON_MEDICINE_TYPES and defaults anything unlisted to
   isMedicine=True, which mislabels 2162 of 4970 products (44% of the catalog)
   as medicines. Note "sin medicamento" *contains* "medicamento", so the
   negative form has to be tested before the positive one.

2. No barcodes. Every `variant.sku` here is an internal `MF#####` code, not an
   EAN — 0 of 4950 are 13 digits. ShopifyConnector maps sku -> barcode
   unconditionally (correct for Farmex, which publishes real EANs). Two of
   these codes ("MF777654323") survive `normalize_barcode` as 9-digit
   "barcodes" and would become false cross-chain identity keys, and the rest
   pollute the barcode column with junk. So barcode stays None and the merchant
   code is kept in `attributes` instead.

Because MercadoFarma publishes no barcode, `attributes` is the *only* route by
which its products can be matched to other chains, so we mine the product
description (a consistently structured template) for active ingredient,
presentation and laboratory on top of the tag/type signals.
"""
import html
import re
import unicodedata
from dataclasses import dataclass
from typing import AsyncIterator

from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client, get_json

# The description template is a flat <h2>/<h3>/<h4> + <p> sequence:
#   <h2>Baclofeno 10 mg 20 Comprimidos</h2>   <- full name
#   <h2>Baclofeno</h2>                        <- active ingredient
#   <h3>Laboratorio Vitafarma</h3>
#   <h4>Presentacion de Baclofeno</h4><p>Comprimidos.</p>
H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
LAB_RE = re.compile(r"<h3\b[^>]*>\s*Laboratorio\s+(.*?)</h3>", re.IGNORECASE | re.DOTALL)
PRESENTATION_RE = re.compile(
    r"<h4\b[^>]*>\s*Presentaci[oó]n\b.*?</h4>\s*<p\b[^>]*>(.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
COMPOSITION_RE = re.compile(
    r"<h4\b[^>]*>\s*Composici[oó]n\b.*?</h4>\s*<p\b[^>]*>(.*?)</p>",
    re.IGNORECASE | re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def strip_html(fragment: str | None) -> str:
    """Flatten an HTML fragment to plain text."""
    if not fragment:
        return ""
    text = html.unescape(TAG_RE.sub(" ", fragment))
    # \xa0 comes from the &nbsp; spacers the template puts between sections.
    return " ".join(text.replace("\xa0", " ").split())


def fold(value: str | None) -> str:
    """Lowercase, de-accent and collapse whitespace, for vocabulary lookups."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())


@dataclass
class MercadoFarmaConfig:
    chain: str
    base_url: str
    page_size: int = 250
    # Catalog is 20 pages today; the ceiling is only a runaway guard.
    max_pages: int = 60


MERCADOFARMA_CONFIGS: dict[str, MercadoFarmaConfig] = {
    "mercadofarma": MercadoFarmaConfig(
        chain="mercadofarma",
        base_url="https://www.mercadofarma.cl",
    ),
}


class MercadoFarmaConnector(BaseScraper):
    chain = "mercadofarma"
    base_url = "https://www.mercadofarma.cl"

    def __init__(self, config: MercadoFarmaConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    def build_page_url(self, page: int) -> str:
        return f"{self.base_url}/products.json?limit={self.config.page_size}&page={page}"

    # --- medicine flag ---------------------------------------------------
    # `product_type` is a binary flag, not a category. "sin ..." must be tested
    # first because "sin medicamento" contains "medicamento".
    MEDICINE_MARKERS = ("medicam", "medicin", "farmac")
    # Values that carry no signal either way; better to leave isMedicine unset
    # than to guess. MercadoFarma publishes an explicit flag, so an
    # unrecognised value is a data hole, not evidence of a drug.
    UNKNOWN_TYPES = {"no aplica", "no disponible", "fnl", "n/a", "-"}
    # Internal merchandising flags, useless for matching. "sm" is the store's
    # shorthand for "sin medicamento" (1573 of its 1619 uses sit on a
    # "sin medicamento" product); "upretenido" and friends are ops markers.
    NOISE_TAGS = {"sm", "suscripcion", "upretenido", "upretenida", "upretenidos"}

    @classmethod
    def classify_medicine(cls, product_type: str | None) -> bool | None:
        """True / False / None when the published value decides nothing."""
        folded = fold(product_type).lstrip(",. ").strip()
        if not folded or folded in cls.UNKNOWN_TYPES:
            return None
        # Negative form first: "sin medicamento" also contains "medicamento".
        # This catches the misspellings too ("sin medicaento", "sin medicamnto")
        # without needing to enumerate them.
        if re.match(r"^sin\b", folded):
            return False
        if any(marker in folded for marker in cls.MEDICINE_MARKERS):
            return True
        return None

    # --- description mining ----------------------------------------------
    @classmethod
    def extract_active_ingredient(cls, body_html: str | None) -> str | None:
        """Second <h2> of the template. Only meaningful for medicines — on a
        wrist brace the same slot holds a brand name."""
        headings = [strip_html(h) for h in H2_RE.findall(body_html or "")]
        headings = [h for h in headings if h]
        if len(headings) < 2:
            return None
        return headings[1] or None

    @staticmethod
    def _first_match(pattern: re.Pattern, body_html: str | None) -> str | None:
        match = pattern.search(body_html or "")
        if not match:
            return None
        return strip_html(match.group(1)).rstrip(".").strip() or None

    @classmethod
    def extract_attributes(cls, raw: dict) -> dict:
        attributes: dict = {}

        product_type = (raw.get("product_type") or "").strip()
        is_medicine = cls.classify_medicine(product_type)
        if product_type:
            # Keep the label exactly as published, typos included — it is the
            # raw evidence behind isMedicine.
            attributes["category"] = product_type
        if is_medicine is not None:
            attributes["isMedicine"] = is_medicine

        body_html = raw.get("body_html")
        if is_medicine:
            ingredient = cls.extract_active_ingredient(body_html)
            if ingredient:
                attributes["activeIngredient"] = ingredient
            composition = cls._first_match(COMPOSITION_RE, body_html)
            if composition:
                attributes["composition"] = composition

        presentation = cls._first_match(PRESENTATION_RE, body_html)
        if presentation:
            attributes["presentation"] = presentation

        laboratory = cls._first_match(LAB_RE, body_html)
        if laboratory:
            attributes["laboratory"] = laboratory

        tags = raw.get("tags") or []
        folded_tags = {fold(t) for t in tags}
        if "bioequivalente" in folded_tags:
            attributes["isBioequivalent"] = True
        if "receta" in folded_tags:
            attributes["requiresPrescription"] = True

        clean_tags = [
            t for t in tags
            if t and not t.isdigit() and fold(t) not in cls.NOISE_TAGS
        ]
        if clean_tags:
            attributes["tags"] = clean_tags[:10]

        return attributes

    # --- product ----------------------------------------------------------
    def parse_product(self, raw: dict) -> list[ScrapedProduct]:
        handle = raw.get("handle") or ""
        title = raw.get("title") or ""
        vendor = (raw.get("vendor") or "").strip() or None
        images = raw.get("images") or []
        default_image = images[0].get("src") if images else None

        attributes = self.extract_attributes(raw) or None
        # The description's "Laboratorio X" is the better lab name when the
        # Shopify vendor field is blank.
        laboratory = vendor or (attributes or {}).get("laboratory")

        results: list[ScrapedProduct] = []
        for variant in raw.get("variants") or []:
            # Shopify returns machine-formatted numbers ("3890", "1004.0"),
            # where "." is a decimal point — parse_price would read it as the
            # Chilean thousands separator and inflate the value tenfold.
            price = self.parse_machine_price(variant.get("price"))
            # A $0 variant is a Cenabast / insurance placeholder, not an offer;
            # letting it through would win every "cheapest price" ranking.
            if not price:
                continue

            compare_at = self.parse_machine_price(variant.get("compare_at_price"))
            original_price = compare_at if compare_at and compare_at > price else None
            discount_pct = round((1 - price / original_price) * 100) if original_price else None

            variant_title = variant.get("title") or ""
            name = title if variant_title in ("", "Default Title") else f"{title} - {variant_title}"

            # Merchant code is neither unique (66 collisions) nor always
            # present (20 blanks), so the variant id is the stable key.
            merchant_sku = (variant.get("sku") or "").strip() or None
            variant_attributes = attributes
            if merchant_sku:
                variant_attributes = {**(attributes or {}), "merchantSku": merchant_sku}

            featured = variant.get("featured_image") or {}
            results.append(ScrapedProduct(
                sku=str(variant.get("id") or merchant_sku or ""),
                name=name,
                brand=vendor,
                laboratory=laboratory,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                stock_status="in_stock" if variant.get("available") else "out_of_stock",
                stock_quantity=None,
                # MercadoFarma publishes no EAN — `sku` is an internal MF code.
                barcode=None,
                url=f"{self.base_url}/products/{handle}" if handle else None,
                image_url=featured.get("src") or default_image,
                pharmacy_chain=self.chain,
                source="api",
                attributes=variant_attributes,
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

                logger.info(
                    f"[{self.chain}] page {page}: {len(raw_products)} products, "
                    f"total variants: {total}"
                )
                await self.random_delay(400, 1200)
