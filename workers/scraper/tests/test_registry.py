import pytest
from src.base_scraper import BaseScraper
from src.registry import CHAIN_NAMES, CHAINS, FAST_MODES, build_scraper

EXPECTED_CHAINS = {
    "cruz_verde", "salcobrand", "ahumada", "dr_simi", "farmex", "curie", "farmaloop",
    "mercadofarma", "knop", "preunic",
}


def test_registry_covers_every_national_chain():
    assert set(CHAINS) == EXPECTED_CHAINS


def test_chain_names_matches_registry():
    assert set(CHAIN_NAMES) == set(CHAINS)


@pytest.mark.parametrize("chain", sorted(EXPECTED_CHAINS))
def test_every_chain_builds_a_scraper(chain):
    scraper = build_scraper(chain)
    assert isinstance(scraper, BaseScraper)
    assert scraper.chain == chain


@pytest.mark.parametrize("chain", sorted(EXPECTED_CHAINS))
def test_spec_metadata_is_populated(chain):
    spec = CHAINS[chain]
    assert spec.name
    assert spec.website.startswith("https://")
    assert spec.platform
    assert spec.interval_hours > 0


def test_fast_mode_returns_search_traversal():
    scraper = build_scraper("cruz_verde", fast=True)
    assert scraper.mode == "search"
    assert build_scraper("cruz_verde").mode == "sitemap"


def test_fast_flag_is_ignored_for_chains_without_a_fast_mode():
    assert "farmex" not in FAST_MODES
    assert build_scraper("farmex", fast=True).chain == "farmex"


def test_unknown_chain_raises():
    with pytest.raises(KeyError):
        build_scraper("farmacias_inventadas")
