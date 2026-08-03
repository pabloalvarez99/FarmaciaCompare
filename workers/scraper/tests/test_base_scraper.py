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


# --- normalize_image_url ----------------------------------------------------
# Applied in PriceWriter so all ten chains get the guarantee at one choke point.

from src.base_scraper import normalize_image_url


def test_normalize_encodes_spaces_in_path():
    assert normalize_image_url(
        "https://cdn.example.com/arquivos/ids/1/Mupirocina - 613-1.jpg?v=638"
    ) == "https://cdn.example.com/arquivos/ids/1/Mupirocina%20-%20613-1.jpg?v=638"


def test_normalize_does_not_double_encode():
    url = "https://cdn.example.com/a%20b.jpg?v=1"
    assert normalize_image_url(url) == url


def test_normalize_leaves_query_string_alone():
    url = "https://cdn.example.com/a.jpg?sw=1050&sh=1050&sm=fit"
    assert normalize_image_url(url) == url


def test_normalize_strips_surrounding_whitespace():
    assert normalize_image_url("  https://cdn/a.jpg ") == "https://cdn/a.jpg"


def test_normalize_rejects_non_http():
    assert normalize_image_url("data:image/gif;base64,R0lGOD") is None
    assert normalize_image_url("/relative/a.jpg") is None
    assert normalize_image_url("ftp://host/a.jpg") is None
    assert normalize_image_url("https://") is None


def test_normalize_handles_empty():
    assert normalize_image_url(None) is None
    assert normalize_image_url("") is None
    assert normalize_image_url("   ") is None


def test_normalize_keeps_already_valid_urls_untouched():
    for url in (
        "https://static.salcobrand.cl/spree/products/1/small/2.jpg?164",
        "https://beta.cruzverde.cl/on/demandware.static/-/Sites/images/large/1-a.jpg",
        "https://cdn.shopify.com/s/files/1/0024/a-b_c.webp?v=1692989408",
    ):
        assert normalize_image_url(url) == url


def test_normalize_upgrades_protocol_relative_urls():
    # Several storefront APIs emit `//cdn/...`. It is a real image missing only
    # a scheme; dropping it would silently delete good data.
    assert normalize_image_url("//cdn.shopify.com/s/files/a.jpg?v=1") == (
        "https://cdn.shopify.com/s/files/a.jpg?v=1"
    )


def test_normalize_encodes_protocol_relative_with_spaces():
    assert normalize_image_url("//cdn.host/a b.jpg") == "https://cdn.host/a%20b.jpg"
