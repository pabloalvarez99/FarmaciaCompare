import pytest
from src.connectors.vtex_connector import VtexConnector, VtexConfig


class TestVtexConnector:
    @pytest.fixture
    def config(self):
        return VtexConfig(
            chain="cruz_verde",
            account_name="cruzverde",
            base_url="https://www.cruzverde.cl",
        )

    @pytest.fixture
    def connector(self, config):
        return VtexConnector(config)

    def test_builds_search_url(self, connector):
        url = connector.build_search_url(page=1, page_size=50)
        assert "cruzverde" in url or "cruzverde.vtexcommercestable.com.br" in url
        assert "from=0" in url or "_from=0" in url

    def test_parse_product_valid(self, connector):
        raw = {
            "productId": "12345",
            "productName": "Paracetamol 500mg x20 Comprimidos Cruz Verde",
            "brand": "Cruz Verde",
            "items": [{
                "itemId": "12345-001",
                "ean": "7891234567890",
                "sellers": [{
                    "commertialOffer": {
                        "Price": 2990,
                        "ListPrice": 3490,
                        "AvailableQuantity": 50,
                    }
                }]
            }]
        }
        products = connector.parse_product(raw)
        assert len(products) == 1
        p = products[0]
        assert p.price == 2990
        assert p.original_price == 3490
        assert p.stock_status == "in_stock"
        assert p.sku == "12345-001"

    def test_parse_product_out_of_stock(self, connector):
        raw = {
            "productId": "99999",
            "productName": "Test Med",
            "brand": None,
            "items": [{
                "itemId": "99999-001",
                "ean": None,
                "sellers": [{
                    "commertialOffer": {
                        "Price": 0,
                        "ListPrice": 1000,
                        "AvailableQuantity": 0,
                    }
                }]
            }]
        }
        products = connector.parse_product(raw)
        assert products[0].stock_status == "out_of_stock"

    def test_parse_product_missing_items_skipped(self, connector):
        raw = {"productId": "X", "productName": "Empty", "brand": None, "items": []}
        products = connector.parse_product(raw)
        assert products == []
