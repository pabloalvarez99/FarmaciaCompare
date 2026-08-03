"""Unit tests for Preunic Empathy connector (no live network)."""

from src.connectors.preunic_connector import PREUNIC_CONFIGS, PreunicConnector


def _connector() -> PreunicConnector:
    return PreunicConnector(PREUNIC_CONFIGS["preunic"])


SAMPLE_HIT = {
    "id": "12345",
    "sku": "SKU-1",
    "name": "Labial Matte Rose",
    "brand": "Maybelline",
    "price": "8990.0",
    "displayPrice": "$8.990",
    "offerPrice": "6990.0",
    "displayOfferPrice": "$6.990",
    "cardPrice": "5990.0",
    "state": "active",
    "slug": "labial-matte-rose",
    "image": "https://static.preunic.cl/img/labial.jpg",
    "categories": ["brillos labiales", "maquillaje labios", "maquillaje"],
    "optionsText": "Formato: 4.5 g",
    "storeExclusive": False,
    "exclusiveBrand": False,
}


def test_config_chain():
    c = _connector()
    assert c.chain == "preunic"
    assert "empathy.co" in c.browse_url


def test_parse_product_offer_and_card():
    c = _connector()
    p = c.parse_product(SAMPLE_HIT)
    assert p is not None
    assert p.sku == "SKU-1"
    assert p.price == 6990
    assert p.original_price == 8990
    assert p.discount_pct == 22
    assert p.barcode is None
    assert p.image_url == "https://static.preunic.cl/img/labial.jpg"
    assert p.attributes is not None
    assert p.attributes["isMedicine"] is False
    assert p.attributes["category"] == "brillos labiales"
    assert p.attributes["presentation"] == "4.5 g"
    assert p.attributes["cardPrice"] == 5990
    assert p.url.endswith("/products/labial-matte-rose")


def test_parse_skips_zero_price():
    c = _connector()
    hit = {**SAMPLE_HIT, "price": "0", "offerPrice": None, "displayPrice": "$0"}
    assert c.parse_product(hit) is None


def test_is_medicine_true_if_farmacia_category():
    c = _connector()
    attrs = c.extract_attributes(
        {
            "categories": ["paracetamol", "medicamentos"],
            "optionsText": "Formato: 16 comprimidos",
        }
    )
    assert attrs["isMedicine"] is True
    assert attrs["presentation"] == "16 comprimidos"


def test_build_params_filter_category_spelling():
    c = _connector()
    qs = c.build_params([("facetCategory", "maquillaje")], rows=50, start=0)
    assert "filter=filterCategory%3Amaquillaje" in qs or "filterCategory" in qs
    assert "rows=50" in qs
    assert "start=0" in qs


def test_machine_vs_chilean_price_parsers():
    """Mixing parsers would inflate offer prices ×10."""
    c = _connector()
    assert c.parse_machine_price("2800.0") == 2800
    assert c.parse_price("$2.800") == 2800
