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
