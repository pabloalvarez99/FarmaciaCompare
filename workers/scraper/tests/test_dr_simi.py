import pytest
from src.pharmacies.dr_simi import DrSimiScraper


class TestDrSimiScraper:
    def test_parse_price_from_text(self):
        scraper = DrSimiScraper()
        assert scraper.parse_price("$4.990") == 4990
        assert scraper.parse_price("4990") == 4990

    def test_parse_product_row(self):
        scraper = DrSimiScraper()
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
