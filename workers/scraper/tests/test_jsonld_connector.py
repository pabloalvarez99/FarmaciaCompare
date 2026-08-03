import pytest
from src.connectors.jsonld_connector import JSONLD_CONFIGS, JsonLdConnector

PRODUCT_HTML = """
<html><head>
<script type="application/ld+json">{"@context":"http://schema.org/","@type":"BreadcrumbList"}</script>
<script type="application/ld+json">
{"@context": "http://schema.org/", "@type": "Product",
 "name": "Reflexan 10 mg x 20 Comprimidos Recubiertos", "mpn": "6", "sku": "6",
 "brand": {"@type": "Thing", "name": "Reflexan"},
 "image": ["https://www.farmaciasahumada.cl/img/6.jpg"],
 "offers": {"@type": "Offer", "priceCurrency": "CLP", "price": "13609",
            "availability": "http://schema.org/InStock"}}
</script>
</head><body></body></html>
"""


@pytest.fixture
def connector():
    return JsonLdConnector(JSONLD_CONFIGS["ahumada"])


def test_extract_jsonld_product_skips_non_product_blocks(connector):
    data = connector.extract_jsonld_product(PRODUCT_HTML)
    assert data["@type"] == "Product"
    assert data["sku"] == "6"


def test_extract_jsonld_product_returns_none_without_product(connector):
    assert connector.extract_jsonld_product("<html><body>nada</body></html>") is None


def test_extract_jsonld_product_tolerates_broken_json(connector):
    html = '<script type="application/ld+json">{not json}</script>'
    assert connector.extract_jsonld_product(html) is None


def test_extract_jsonld_product_handles_array_payload(connector):
    html = (
        '<script type="application/ld+json">'
        '[{"@type":"Organization"},{"@type":"Product","sku":"9","name":"X"}]'
        "</script>"
    )
    assert connector.extract_jsonld_product(html)["sku"] == "9"


def test_parse_product(connector):
    url = "https://www.farmaciasahumada.cl/reflexan-10-mg-x-20-comprimidos-recubiertos-6.html"
    data = connector.extract_jsonld_product(PRODUCT_HTML)
    p = connector.parse_product(data, url)
    assert p.sku == "6"
    assert p.name == "Reflexan 10 mg x 20 Comprimidos Recubiertos"
    assert p.price == 13609
    assert p.brand == "Reflexan"
    assert p.stock_status == "in_stock"
    assert p.url == url
    assert p.image_url == "https://www.farmaciasahumada.cl/img/6.jpg"
    assert p.pharmacy_chain == "ahumada"


def test_parse_product_out_of_stock(connector):
    data = {
        "@type": "Product", "name": "Med", "sku": "1",
        "offers": {"price": "990", "availability": "http://schema.org/OutOfStock"},
    }
    assert connector.parse_product(data, "https://x").stock_status == "out_of_stock"


def test_parse_product_offer_list(connector):
    data = {
        "@type": "Product", "name": "Med", "sku": "1",
        "offers": [{"price": "990", "availability": "http://schema.org/InStock"}],
    }
    assert connector.parse_product(data, "https://x").price == 990


def test_parse_product_without_offers_skipped(connector):
    assert connector.parse_product({"@type": "Product", "name": "Med", "sku": "1"}, "https://x") is None


def test_parse_product_without_price_skipped(connector):
    data = {"@type": "Product", "name": "Med", "sku": "1", "offers": {"availability": "InStock"}}
    assert connector.parse_product(data, "https://x") is None


# --- schema.org `image` shapes ---------------------------------------------
# Ahumada publishes a list; the spec also allows a bare string or an ImageObject.

def test_pick_image_from_list():
    assert JsonLdConnector.pick_image(["https://a/1.jpg", "https://a/2.jpg"]) == "https://a/1.jpg"


def test_pick_image_from_string():
    assert JsonLdConnector.pick_image("https://a/1.jpg") == "https://a/1.jpg"


def test_pick_image_from_image_object():
    assert JsonLdConnector.pick_image({"@type": "ImageObject", "url": "https://a/1.jpg"}) == "https://a/1.jpg"


def test_pick_image_skips_null_and_empty_entries():
    assert JsonLdConnector.pick_image([None, "", "  ", "https://a/2.jpg"]) == "https://a/2.jpg"


def test_pick_image_rejects_relative_and_data_urls():
    assert JsonLdConnector.pick_image(["/img/1.jpg"]) is None
    assert JsonLdConnector.pick_image(["data:image/gif;base64,R0lGOD"]) is None


def test_pick_image_handles_missing():
    assert JsonLdConnector.pick_image(None) is None
    assert JsonLdConnector.pick_image([]) is None
