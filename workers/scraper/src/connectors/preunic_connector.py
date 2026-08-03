"""Preunic — Spree storefront searched through Empathy.co, not Algolia.

Preunic belongs to the Salcobrand group, so the obvious guess is that it reuses
Salcobrand's Algolia index. It does not. Recon proved:

* The storefront is Spree (``/t/<taxon>`` listings, ``/products/<slug>`` detail
  pages, ``/user/spree_user/password/new``), same commerce engine as Salcobrand.
* The front end is Next.js split into module-federation micro-frontends
  (``pu-navbar``, ``pu-plp``, ``pu-footer``, ...). Every page is rendered
  client-side: ``__NEXT_DATA__`` carries ``{"pageProps": {}}`` and the served
  HTML has no product markup, so HTML/JSON-LD scraping yields nothing.
* Not one JS bundle references Algolia. The product listing pages call
  **Empathy.co** instead:
  ``https://api.empathy.co/search/v1/query/preunic/browse``.
  Salcobrand's Algolia key is referer-locked to salcobrand.cl and answers
  ``403 {"message": "Method not allowed with this referer"}`` for preunic.cl,
  which is further proof the two chains do not share a search backend.

Access notes, all verified against the live API:

* ``robots.txt`` returns **404** on both ``preunic.cl`` and ``www.preunic.cl``
  (the Next.js catch-all answers it), so nothing is disallowed. The sitemap
  index advertised at ``/sitemap.xml`` redirects to
  ``https://static.preunic.cl/sitemaps/preunic/sitemap.xml`` and lists ~13.8k
  ``/products/<slug>`` URLs — but those pages are client-rendered, so the
  sitemap is only useful as a catalog-size sanity check, not as a data source.
* The Empathy endpoint needs **no API key, no Referer and no Origin**. It
  answers the identifiable ``BOT_USER_AGENT`` with 200, so we keep it.
* Deep paging is capped: ``rows`` must be <= 500 and ``start + rows`` must stay
  <= 2600. Beyond that the API answers ``400 Bad Request``. A blank browse
  therefore reaches only 2600 of the ~8.9k active products, so the catalog has
  to be walked in facet partitions, the same trick the Salcobrand connector uses
  against Algolia's 1000-hit ceiling.
* Partitioning runs over two *orthogonal* axes, because one is not enough:
  sweeping ``facetCategory`` alone reached 8849/8881 products — the ~32 stragglers
  carry no category at all. A second pass over ``facetCurrentPrice`` picks those
  up. Buckets that are still above the ceiling are split again by the next facet
  in the chain.
* Facet values are read off a ``rows=1&facets=true`` query. Note the asymmetry:
  the facet is *named* ``facetCategory`` but must be *filtered* as
  ``filterCategory:<value>`` — filtering on ``facetCategory:`` returns 400.
  ``facetBrand`` and ``facetCurrentPrice`` filter under their own names.

Preunic's online catalog is drugstore/beauty (maquillaje, capilar, cuidado
personal, hogar, ...) and publishes **no medicines**: there is no ``farmacia``
value in ``facetCategory`` and ``/t/farmacia`` returns zero hits, falling back to
a "top clicked" carousel. `extract_attributes` still computes ``isMedicine`` from
the category list so the flag flips by itself if Preunic ever adds one.
"""
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator
from urllib.parse import quote

import httpx
from loguru import logger

from ..base_scraper import BaseScraper, ScrapedProduct
from ..http_utils import build_client

# Empathy rejects rows > 500 and any request where start + rows exceeds this.
EMPATHY_MAX_REACHABLE = 2600

# The facet whose *filter* field is spelled differently from its facet name.
FACET_FILTER_FIELDS: dict[str, str] = {"facetCategory": "filterCategory"}

# Categories that would mean "this is a medicine". None of them exist in the
# index today; kept so the flag turns itself on if a farmacia taxon shows up.
MEDICINE_CATEGORIES = {"farmacia", "medicamentos"}

PRESENTATION_PREFIX = "formato:"


@dataclass
class PreunicConfig:
    chain: str
    base_url: str
    instance: str                      # Empathy tenant, e.g. "preunic"
    api_base: str = "https://api.empathy.co/search/v1/query"
    browse_field: str = "state"
    browse_value: str = "active"
    lang: str = "es"
    rows: int = 200
    max_reachable: int = EMPATHY_MAX_REACHABLE
    # Each entry is one full pass over the catalog: (facet to split on, facets
    # to split by when a bucket is still too big). Two passes on independent
    # axes, because products missing a facet are invisible to that axis.
    sweeps: list[tuple[str, list[str]]] = field(
        default_factory=lambda: [
            ("facetCategory", ["facetCurrentPrice", "facetBrand"]),
            ("facetCurrentPrice", ["facetBrand"]),
        ]
    )


PREUNIC_CONFIGS: dict[str, PreunicConfig] = {
    "preunic": PreunicConfig(
        chain="preunic",
        base_url="https://preunic.cl",
        instance="preunic",
    ),
}


class PreunicConnector(BaseScraper):
    def __init__(self, config: PreunicConfig):
        super().__init__()
        self.config = config
        self.chain = config.chain
        self.base_url = config.base_url

    # --- request building ------------------------------------------------

    @property
    def browse_url(self) -> str:
        return f"{self.config.api_base}/{self.config.instance}/browse"

    def build_params(
        self,
        filters: list[tuple[str, str]],
        *,
        rows: int,
        start: int,
        facets: bool = False,
    ) -> str:
        """Query string for one browse call.

        `filter` is repeated once per constraint; Empathy ANDs them.
        """
        parts = [
            f"browseField={self.config.browse_field}",
            f"browseValue={self.config.browse_value}",
            f"lang={self.config.lang}",
            f"rows={rows}",
            f"start={start}",
        ]
        if facets:
            parts.append("facets=true")
        for facet, value in filters:
            field_name = FACET_FILTER_FIELDS.get(facet, facet)
            parts.append(f"filter={quote(field_name)}%3A{quote(str(value))}")
        return "&".join(parts)

    # --- parsing ---------------------------------------------------------

    @staticmethod
    def extract_attributes(hit: dict) -> dict:
        """Structured identity signals Preunic publishes.

        There is no EAN/barcode anywhere in the index or on the product page, so
        `categories` and `optionsText` carry the whole matching signal. The
        `categories` list is ordered most-specific first
        (["brillos labiales", "maquillaje labios", "maquillaje"]).
        """
        attributes: dict = {}

        categories = hit.get("categories")
        if isinstance(categories, list) and categories:
            attributes["category"] = categories[0]
            attributes["categoryPath"] = list(categories)
            attributes["isMedicine"] = any(
                str(c).strip().lower() in MEDICINE_CATEGORIES for c in categories
            )

        # "Formato: 24 Comprimidos" -> "24 Comprimidos"
        options_text = hit.get("optionsText")
        if options_text:
            text = str(options_text).strip()
            if text.lower().startswith(PRESENTATION_PREFIX):
                text = text[len(PRESENTATION_PREFIX):].strip()
            if text:
                attributes["presentation"] = text

        for key, source in (
            ("storeExclusive", "storeExclusive"),
            ("exclusiveBrand", "exclusiveBrand"),
        ):
            if hit.get(source) is not None:
                attributes[key] = bool(hit[source])

        return attributes

    def _list_price(self, hit: dict) -> int | None:
        """Undiscounted price. Numeric field first, Chilean display string second."""
        price = self.parse_machine_price(hit.get("price"))
        if price:
            return price
        return self.parse_price(hit.get("displayPrice") or "")

    def _offer_price(self, hit: dict) -> int | None:
        """Public promotional price — what anyone pays, no loyalty card needed.

        `offerPrice` is machine formatted, so it goes through
        `parse_machine_price`; `displayOfferPrice` is Chilean ("$2.800") and goes
        through `parse_price`. Mixing the two up turns 2800 into 28000.
        """
        offer = self.parse_machine_price(hit.get("offerPrice"))
        if offer:
            return offer
        return self.parse_price(hit.get("displayOfferPrice") or "")

    def parse_product(self, hit: dict) -> ScrapedProduct | None:
        sku = hit.get("sku") or hit.get("id")
        name = hit.get("name")
        list_price = self._list_price(hit)
        # Price 0 is not an offer, it is missing data.
        if not sku or not name or not list_price or list_price <= 0:
            return None

        offer = self._offer_price(hit)
        if offer and 0 < offer < list_price:
            final_price, original_price = offer, list_price
            discount_pct = round((1 - final_price / original_price) * 100)
        else:
            final_price, original_price, discount_pct = list_price, None, None

        attributes = self.extract_attributes(hit)
        # Loyalty ("Mi Preunic" card) price, when it beats the public one. Not an
        # identity signal, but it is the only place this offer is published.
        card_price = self.parse_machine_price(hit.get("cardPrice"))
        if card_price and 0 < card_price < final_price:
            attributes["cardPrice"] = card_price

        slug = hit.get("slug")
        return ScrapedProduct(
            sku=str(sku),
            name=str(name),
            brand=hit.get("brand"),
            laboratory=hit.get("brand"),
            price=final_price,
            original_price=original_price,
            discount_pct=discount_pct,
            stock_status="in_stock" if hit.get("state") == "active" else "out_of_stock",
            stock_quantity=None,
            barcode=None,          # Preunic publishes no EAN — hence `attributes`
            url=f"{self.base_url}/products/{slug}" if slug else None,
            image_url=hit.get("image"),
            pharmacy_chain=self.chain,
            source="api",
            attributes=attributes or None,
        )

    # Alias: sibling connectors that read a search index call this parse_hit.
    parse_hit = parse_product

    # --- transport -------------------------------------------------------

    async def _get(self, client, params: str, *, max_retries: int = 5) -> dict:
        """GET a browse page, backing off on 429/5xx."""
        delay = 2.0
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                response = await client.get(f"{self.browse_url}?{params}")
                if response.status_code == 429 or response.status_code >= 500:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
                    logger.warning(
                        f"[{self.chain}] Empathy {response.status_code}, sleeping "
                        f"{wait:.1f}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    delay = min(delay * 2, 60.0)
                    continue
                response.raise_for_status()
                return response.json().get("catalog") or {}
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                status = exc.response.status_code if exc.response is not None else None
                if status == 429 or (status is not None and status >= 500):
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 60.0)
                    continue
                raise
        if last_exc:
            raise last_exc
        raise RuntimeError(f"[{self.chain}] Empathy query exhausted retries")

    async def _count(self, client, filters: list[tuple[str, str]]) -> int:
        params = self.build_params(filters, rows=1, start=0)
        try:
            return int((await self._get(client, params)).get("numFound") or 0)
        except Exception as exc:
            logger.warning(f"[{self.chain}] count failed for {filters}: {exc}")
            return 0

    async def _facet_values(
        self, client, filters: list[tuple[str, str]], facet: str
    ) -> list[str]:
        """Values of `facet` under the current filters, biggest bucket first."""
        params = self.build_params(filters, rows=1, start=0, facets=True)
        try:
            catalog = await self._get(client, params)
        except Exception as exc:
            logger.warning(f"[{self.chain}] facet listing failed for {facet}: {exc}")
            return []
        for entry in catalog.get("facets") or []:
            if entry.get("facet") != facet:
                continue
            return [
                str(value.get("id"))
                for value in entry.get("values") or []
                if value.get("id") is not None
            ]
        return []

    # --- walking ---------------------------------------------------------

    async def _paginate(
        self, client, filters: list[tuple[str, str]], seen: set[str]
    ) -> AsyncIterator[ScrapedProduct]:
        """Walk one query until exhausted or the reachable-window ceiling."""
        rows = self.config.rows
        start = 0
        while start + rows <= self.config.max_reachable:
            params = self.build_params(filters, rows=rows, start=start)
            try:
                catalog = await self._get(client, params)
            except Exception as exc:
                logger.warning(f"[{self.chain}] page failed ({filters}, start={start}): {exc}")
                return

            hits = catalog.get("content") or []
            if not hits:
                return
            for hit in hits:
                product = self.parse_product(hit)
                if product and product.sku not in seen:
                    seen.add(product.sku)
                    yield product

            start += rows
            if start >= int(catalog.get("numFound") or 0):
                return
            # Human-paced between pages; this is a free public API, be polite.
            await self.random_delay(400, 1200)

        logger.info(
            f"[{self.chain}] hit the {self.config.max_reachable}-result window for {filters}"
        )

    async def _sweep(
        self,
        client,
        filters: list[tuple[str, str]],
        facet_chain: list[str],
        seen: set[str],
    ) -> AsyncIterator[ScrapedProduct]:
        """Yield everything under `filters`, splitting when it does not fit."""
        total = await self._count(client, filters)
        if total == 0:
            return

        if total <= self.config.max_reachable or not facet_chain:
            async for product in self._paginate(client, filters, seen):
                yield product
            return

        facet, *rest = facet_chain
        values = await self._facet_values(client, filters, facet)
        if not values:
            # Nothing to split on; take what the window allows.
            logger.warning(
                f"[{self.chain}] {total} hits for {filters} but no '{facet}' values "
                f"to split by — capped at {self.config.max_reachable}"
            )
            async for product in self._paginate(client, filters, seen):
                yield product
            return

        logger.info(
            f"[{self.chain}] {total} hits for {filters}, splitting by "
            f"{len(values)} '{facet}' values"
        )
        for value in values:
            async for product in self._sweep(client, filters + [(facet, value)], rest, seen):
                yield product

    async def scrape_products(self) -> AsyncIterator[ScrapedProduct]:
        seen: set[str] = set()
        async with build_client(self.user_agent) as client:
            for facet, sub_facets in self.config.sweeps:
                logger.info(f"[{self.chain}] sweep over '{facet}' starting at {len(seen)} unique")
                async for product in self._sweep(client, [], [facet, *sub_facets], seen):
                    yield product
            logger.info(f"[{self.chain}] scrape complete: {len(seen)} unique products")
