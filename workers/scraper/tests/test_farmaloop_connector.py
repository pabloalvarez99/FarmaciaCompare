import pytest
from src.connectors.farmaloop_connector import FARMALOOP_CONFIGS, FarmaloopConnector


@pytest.fixture
def connector():
    return FarmaloopConnector(FARMALOOP_CONFIGS["farmaloop"])


def test_extract_build_id():
    html = 'window.__NEXT_DATA__ = {"props":{},"buildId":"_Um7JBd79k_rs-ARBjzbl","isFallback":false}'
    assert FarmaloopConnector.extract_build_id(html) == "_Um7JBd79k_rs-ARBjzbl"


def test_extract_build_id_missing():
    assert FarmaloopConnector.extract_build_id("<html></html>") is None


@pytest.mark.parametrize("url,expected", [
    ("https://www.farmaloop.cl/products/centrum-x-30-comprimidos-57049/", "centrum-x-30-comprimidos-57049"),
    ("https://www.farmaloop.cl/products/centrum-x-30-comprimidos-57049", "centrum-x-30-comprimidos-57049"),
    ("https://www.farmaloop.cl/categoria/medicamentos/", None),
])
def test_extract_slug(url, expected):
    assert FarmaloopConnector.extract_slug(url) == expected


def test_data_url(connector):
    url = connector.data_url("build123", "centrum-57049")
    assert url == "https://www.farmaloop.cl/_next/data/build123/products/centrum-57049.json"


def test_parse_product(connector):
    raw = {
        "sku": "159656",
        "fullName": "Mounjaro 10mg (Tirzepatida) Jeringa prellenada ",
        "genericName": "Mounjaro 10mg",
        "bestPrice": 526490,
        "basePrice": 635990,
        "bestDiscount": 17,
        "availableForSale": 1,
        "ean": "7798084688353",
        "slug": "mounjaro-10mg06ml-4-agujas-4mm-x-32g-159656",
        "photoURL": "https://imagenes.fc.farmaloop.cl/productos/159656-600.webp",
        "laboratoryName": "ELI LILLY INTERAMERICA INC Y COMPANIA LIMITADA",
        "productCategory": "Medicamentos",
        "productSubCategory": "Diabetes",
        "composicionSearch": "tirzepatida 10 mg",
        "pharmaceuticalForm": "Jeringa",
        "bioequivalent": False,
        "requiresPrescription": True,
        "prescriptionType": "Presentación receta médica",
    }
    p = connector.parse_product(raw)
    assert p.sku == "159656"
    assert p.name == "Mounjaro 10mg (Tirzepatida) Jeringa prellenada"
    assert p.price == 526490
    assert p.original_price == 635990
    assert p.discount_pct == 17
    assert p.stock_status == "in_stock"
    assert p.barcode == "7798084688353"
    assert p.url == "https://www.farmaloop.cl/products/mounjaro-10mg06ml-4-agujas-4mm-x-32g-159656/"
    assert p.laboratory == "ELI LILLY INTERAMERICA INC Y COMPANIA LIMITADA"
    assert p.attributes["isMedicine"] is True
    assert p.attributes["category"] == "Medicamentos"
    assert p.attributes["activeIngredient"] == "tirzepatida 10 mg"
    assert p.attributes["requiresPrescription"] is True


def test_extract_attributes_beauty_is_not_medicine(connector):
    attrs = connector.extract_attributes(
        {
            "productCategory": "Cuidado y Belleza",
            "productSubCategory": "Rostro",
            "composicionSearch": "manteca de cacao",
            "requiresPrescription": False,
            "bioequivalent": False,
            "tags": ["balsamo labial"],
        }
    )
    assert attrs["isMedicine"] is False
    assert attrs["category"] == "Cuidado y Belleza"
    assert attrs["activeIngredient"] == "manteca de cacao"
    assert "requiresPrescription" not in attrs


def test_parse_product_derives_discount_when_absent(connector):
    raw = {"sku": "1", "fullName": "Med", "bestPrice": 800, "basePrice": 1000, "availableForSale": 0}
    p = connector.parse_product(raw)
    assert p.discount_pct == 20
    assert p.stock_status == "out_of_stock"


def test_parse_product_no_discount_when_base_equals_price(connector):
    raw = {"sku": "1", "fullName": "Med", "bestPrice": 1000, "basePrice": 1000, "availableForSale": 1}
    p = connector.parse_product(raw)
    assert p.original_price is None


def test_parse_product_without_price_skipped(connector):
    assert connector.parse_product({"sku": "1", "fullName": "Med"}) is None


def test_find_product_payload_prefers_named_key():
    props = {"product": {"sku": "1", "bestPrice": 10}, "other": {"sku": "2", "bestPrice": 20}}
    assert FarmaloopConnector.find_product_payload(props)["sku"] == "1"


def test_find_product_payload_falls_back_to_scan():
    props = {"weird_key_name": {"sku": "42", "bestPrice": 999}}
    assert FarmaloopConnector.find_product_payload(props)["sku"] == "42"


def test_find_product_payload_returns_none():
    assert FarmaloopConnector.find_product_payload({"seo": {"title": "x"}}) is None


def test_empty_photo_url_becomes_none(connector):
    raw = {"sku": "1", "fullName": "Med", "bestPrice": 1000, "photoURL": "  "}
    assert connector.parse_product(raw).image_url is None


def test_photo_url_is_stripped(connector):
    raw = {"sku": "1", "fullName": "Med", "bestPrice": 1000,
           "photoURL": " https://imagenes.fc.farmaloop.cl/productos/1-600.webp "}
    assert connector.parse_product(raw).image_url == (
        "https://imagenes.fc.farmaloop.cl/productos/1-600.webp"
    )
