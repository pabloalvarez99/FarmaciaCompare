"""Single source of truth for every pharmacy chain we scrape.

Adding a chain means adding one entry here — the CLI choices, the scheduler
jobs and the pharmacy seeding all read from this table.
"""
from dataclasses import dataclass
from typing import Callable

from .base_scraper import BaseScraper


@dataclass(frozen=True)
class ChainSpec:
    chain: str                      # pharmacies.chain value
    name: str                       # human name shown in the UI
    website: str
    platform: str                   # how we get the data, for ops/debugging
    factory: Callable[[], BaseScraper]
    interval_hours: int = 6


def _cruz_verde() -> BaseScraper:
    from .connectors.ocapi_connector import OCAPI_CONFIGS, OcapiConnector
    return OcapiConnector(OCAPI_CONFIGS["cruz_verde"])


def _cruz_verde_search() -> BaseScraper:
    from .connectors.ocapi_connector import OCAPI_CONFIGS, OcapiConnector
    return OcapiConnector(OCAPI_CONFIGS["cruz_verde"], mode="search")


def _salcobrand() -> BaseScraper:
    from .connectors.algolia_connector import ALGOLIA_CONFIGS, AlgoliaConnector
    return AlgoliaConnector(ALGOLIA_CONFIGS["salcobrand"])


def _ahumada() -> BaseScraper:
    from .connectors.jsonld_connector import JSONLD_CONFIGS, JsonLdConnector
    return JsonLdConnector(JSONLD_CONFIGS["ahumada"])


def _dr_simi() -> BaseScraper:
    from .connectors.vtex_connector import VTEX_CONFIGS, VtexConnector
    return VtexConnector(VTEX_CONFIGS["dr_simi"])


def _farmex() -> BaseScraper:
    from .connectors.shopify_connector import SHOPIFY_CONFIGS, ShopifyConnector
    return ShopifyConnector(SHOPIFY_CONFIGS["farmex"])


def _curie() -> BaseScraper:
    from .connectors.shopify_connector import SHOPIFY_CONFIGS, ShopifyConnector
    return ShopifyConnector(SHOPIFY_CONFIGS["curie"])


def _farmaloop() -> BaseScraper:
    from .connectors.farmaloop_connector import FARMALOOP_CONFIGS, FarmaloopConnector
    return FarmaloopConnector(FARMALOOP_CONFIGS["farmaloop"])


def _mercadofarma() -> BaseScraper:
    from .connectors.mercadofarma_connector import (
        MERCADOFARMA_CONFIGS,
        MercadoFarmaConnector,
    )
    return MercadoFarmaConnector(MERCADOFARMA_CONFIGS["mercadofarma"])


def _knop() -> BaseScraper:
    from .connectors.knop_connector import KNOP_CONFIGS, KnopConnector
    return KnopConnector(KNOP_CONFIGS["knop"])


def _preunic() -> BaseScraper:
    from .connectors.preunic_connector import PREUNIC_CONFIGS, PreunicConnector
    return PreunicConnector(PREUNIC_CONFIGS["preunic"])


CHAINS: dict[str, ChainSpec] = {
    spec.chain: spec
    for spec in [
        ChainSpec("cruz_verde", "Cruz Verde", "https://www.cruzverde.cl",
                  "sfcc-ocapi", _cruz_verde, interval_hours=12),
        ChainSpec("salcobrand", "Salcobrand", "https://salcobrand.cl",
                  "algolia", _salcobrand, interval_hours=6),
        ChainSpec("ahumada", "Farmacias Ahumada", "https://www.farmaciasahumada.cl",
                  "sfcc-jsonld", _ahumada, interval_hours=12),
        ChainSpec("dr_simi", "Farmacias Dr. Simi", "https://www.drsimi.cl",
                  "vtex", _dr_simi, interval_hours=6),
        ChainSpec("farmex", "Farmex", "https://farmex.cl",
                  "shopify", _farmex, interval_hours=6),
        ChainSpec("curie", "Farmacias Curie", "https://www.farmaciascurie.cl",
                  "shopify", _curie, interval_hours=6),
        ChainSpec("farmaloop", "Farmaloop", "https://www.farmaloop.cl",
                  "nextjs-data", _farmaloop, interval_hours=6),
        # Shopify like Farmex/Curie, but it needs its own connector: it publishes
        # `product_type` as "medicamento" / "sin medicamento" (the negative
        # contains the positive), and its SKUs are internal codes, not EANs.
        ChainSpec("mercadofarma", "MercadoFarma", "https://www.mercadofarma.cl",
                  "shopify", _mercadofarma, interval_hours=6),
        # Bolder (not Shopify). Catalog at farmaciasknop.com; knop.cl is lab-only.
        ChainSpec("knop", "Farmacias Knop", "https://www.farmaciasknop.com",
                  "bolder", _knop, interval_hours=12),
        # Empathy.co browse (not Algolia). Beauty/drugstore; isMedicine false today.
        ChainSpec("preunic", "Preunic", "https://preunic.cl",
                  "empathy", _preunic, interval_hours=12),
    ]
}

# Cheap price-refresh variants that do not walk the whole catalog.
FAST_MODES: dict[str, Callable[[], BaseScraper]] = {
    "cruz_verde": _cruz_verde_search,
}

CHAIN_NAMES: list[str] = list(CHAINS.keys())


def build_scraper(chain: str, fast: bool = False) -> BaseScraper:
    if chain not in CHAINS:
        raise KeyError(f"Unknown chain '{chain}'. Known: {', '.join(CHAIN_NAMES)}")
    if fast and chain in FAST_MODES:
        return FAST_MODES[chain]()
    return CHAINS[chain].factory()
