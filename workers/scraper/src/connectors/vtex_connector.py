"""VTEX storefronts.

Only Dr. Simi (drsimi.cl, VTEX account `farmaciasdeldrsimicl`) still runs VTEX.
Cruz Verde and Salcobrand left the platform — see ocapi_connector and
algolia_connector for those.

The catalog API answers on the store's own domain, which avoids the
vtexcommercestable.com.br host entirely.
"""
import re
from dataclasses import dataclass
from typing import AsyncIterator
from urllib.parse import quote, urlsplit, urlunsplit

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from ..base_scraper import BaseScraper, ScrapedProduct


@dataclass
class VtexConfig:
    chain: str
    account_name: str
    base_url: str
    use_store_domain: bool = True   # query base_url/api/... instead of the VTEX host
    max_pages: int = 400


VTEX_CONFIGS: dict[str, VtexConfig] = {
    "dr_simi": VtexConfig(
        chain="dr_simi",
        account_name="farmaciasdeldrsimicl",
        base_url="https://www.drsimi.cl",
    ),
}


# VTEX file IDs in an image URL: .../arquivos/ids/160249/BE0089-1.jpg
# A `-<w>-<h>` suffix on the id makes the CDN resize; without it the CDN serves
# the original upload. Only rewrite when the id has no suffix already.
VTEX_IMAGE_ID_RE = re.compile(r"(/arquivos/ids/\d+)(?=/)")

# What the storefront itself requests for a catalog tile, and enough for a 2x
# retina thumbnail in our price table.
VTEX_IMAGE_SIZE = 500

# Every character RFC 3986 allows unescaped in a path segment, plus `/` and `%`.
# `%` has to stay safe or an already-encoded `%20` would become `%2520`.
_PATH_SAFE = "/%!$&'()*+,;=:@~"


def encode_url_path(url: str) -> str:
    """Percent-encode the path so a filename with spaces stays a usable URL.

    Dr. Simi uploads files named `Mupirocina - 613-1.jpg`, and VTEX hands the
    space back raw. Verified: the raw form fails outright (curl exits 000, and
    Python's urllib refuses it as a control character), while the `%20` form
    returns 200 image/jpeg. Browsers paper over it in `<img src>`, but anything
    server-side that touches the URL breaks, so it is normalised on the way in.
    Query string is left alone — the `?v=` cache-buster is already safe.
    """
    parts = urlsplit(url)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        quote(parts.path, safe=_PATH_SAFE),
        parts.query,
        parts.fragment,
    ))


class VtexConnector(BaseScraper):
    SEARCH_PATH = "/api/catalog_system/pub/products/search?_from={from_}&_to={to}&O=OrderByScoreDESC"

    def __init__(self, config: VtexConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    @property
    def api_root(self) -> str:
        if self.config.use_store_domain:
            return self.config.base_url
        return f"https://{self.config.account_name}.vtexcommercestable.com.br"

    def build_search_url(self, page: int = 1, page_size: int = 50) -> str:
        from_ = (page - 1) * page_size
        to = from_ + page_size - 1
        return self.api_root + self.SEARCH_PATH.format(from_=from_, to=to)

    @staticmethod
    def pick_image(item: dict) -> str | None:
        """First product photo, resized by the CDN.

        `items[].images[0].imageUrl` is a real product photo (checked across 200
        Dr. Simi items: none missing, none a placeholder), but it points at the
        *original upload* — ~65 KB / >1000 px each, so a 30-row price table would
        pull ~2 MB of images. Asking the VTEX image server for a 500 px render
        (verified 200 image/jpeg, ~15-20 KB) is the same picture at a quarter of
        the weight. URLs that do not look like a VTEX file id are left untouched.
        """
        for image in item.get("images") or []:
            url = (image.get("imageUrl") or "").strip()
            if url:
                sized = VTEX_IMAGE_ID_RE.sub(
                    lambda m: f"{m.group(1)}-{VTEX_IMAGE_SIZE}-{VTEX_IMAGE_SIZE}", url, count=1
                )
                return encode_url_path(sized)
        return None

    @staticmethod
    def extract_attributes(raw: dict, item: dict) -> dict:
        """Dr. Simi's VTEX returns an empty `ean`, so identity has to come from
        the catalog metadata: the internal reference code and the category tree.
        """
        attributes: dict = {}

        for reference in item.get("referenceId") or []:
            if reference.get("Key") == "RefId" and reference.get("Value"):
                attributes["referenceCode"] = reference["Value"]

        categories = raw.get("categories") or []
        if categories:
            # VTEX category paths look like "/Medicamentos/Analgesicos/".
            attributes["category"] = categories[0].strip("/").replace("/", " > ")
            attributes["isMedicine"] = any(
                "medicamento" in str(c).lower() for c in categories
            )

        if raw.get("productReference"):
            attributes.setdefault("referenceCode", raw["productReference"])

        return attributes

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
                laboratory=raw.get("brand"),
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                stock_status=stock_status,
                stock_quantity=available_qty if available_qty > 0 else None,
                barcode=item.get("ean"),
                url=f"{self.base_url}/{raw.get('linkText', '')}/p",
                image_url=self.pick_image(item),
                pharmacy_chain=self.chain,
                source="api",
                attributes=self.extract_attributes(raw, item) or None,
            ))
        return results

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, client: httpx.AsyncClient, page: int, page_size: int) -> list[dict]:
        url = self.build_search_url(page, page_size)
        headers = {"User-Agent": self.user_agent, "Accept": "application/json", "Referer": self.base_url}
        response = await client.get(url, headers=headers, timeout=30)
        # VTEX answers paginated ranges with 206; 416 means we walked past the end.
        if response.status_code == 416:
            return []
        response.raise_for_status()
        return response.json()

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        page_size = 50
        total_scraped = 0
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for page in range(1, self.config.max_pages + 1):
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
