import pytest
from src.connectors.shopify_connector import SHOPIFY_CONFIGS, ShopifyConnector


@pytest.fixture
def connector():
    return ShopifyConnector(SHOPIFY_CONFIGS["farmex"])


def test_registry_covers_both_shopify_stores():
    assert set(SHOPIFY_CONFIGS) == {"farmex", "curie"}


def test_build_page_url(connector):
    assert connector.build_page_url(2) == "https://farmex.cl/products.json?limit=250&page=2"


def test_parse_product_with_discount(connector):
    raw = {
        "title": "Tejania 0,075 mg x 28 comprimidos.",
        "handle": "tejania-0-075-mg-x-28-comprimidos-10",
        "vendor": "Farmex-Fonasa",
        "images": [{"src": "https://cdn/img.jpg"}],
        "variants": [{
            "id": 45311227330742,
            "title": "Default Title",
            "sku": "5997001361887",
            "available": True,
            "price": "7439",
            "compare_at_price": "7990",
        }],
    }
    products = connector.parse_product(raw)
    assert len(products) == 1
    p = products[0]
    assert p.sku == "45311227330742"
    assert p.name == "Tejania 0,075 mg x 28 comprimidos."
    assert p.price == 7439
    assert p.original_price == 7990
    assert p.discount_pct == 7
    assert p.stock_status == "in_stock"
    assert p.barcode == "5997001361887"
    assert p.url == "https://farmex.cl/products/tejania-0-075-mg-x-28-comprimidos-10"
    assert p.image_url == "https://cdn/img.jpg"


def test_decimal_price_is_not_read_as_thousands_separator(connector):
    """'1004.0' is a decimal, not the Chilean 1.004 thousands format."""
    raw = {
        "title": "Med",
        "handle": "med",
        "vendor": None,
        "variants": [{"id": 1, "title": "Default Title", "available": True, "price": "1004.0"}],
    }
    assert connector.parse_product(raw)[0].price == 1004


def test_variant_title_appended_when_not_default(connector):
    raw = {
        "title": "Vitamina C",
        "handle": "vitamina-c",
        "vendor": None,
        "variants": [{"id": 2, "title": "60 comprimidos", "available": False, "price": "5990"}],
    }
    p = connector.parse_product(raw)[0]
    assert p.name == "Vitamina C - 60 comprimidos"
    assert p.stock_status == "out_of_stock"


def test_compare_at_below_price_is_not_a_discount(connector):
    raw = {
        "title": "Med",
        "handle": "med",
        "vendor": None,
        "variants": [{"id": 3, "title": "Default Title", "available": True,
                      "price": "9990", "compare_at_price": "8990"}],
    }
    p = connector.parse_product(raw)[0]
    assert p.original_price is None
    assert p.discount_pct is None


def test_variant_without_price_skipped(connector):
    raw = {"title": "Med", "handle": "med", "vendor": None,
           "variants": [{"id": 4, "title": "Default Title", "available": True, "price": None}]}
    assert connector.parse_product(raw) == []


# --- extract_attributes -------------------------------------------------
# Shopify has no medicine flag, so `product_type` is the only thing separating
# a real drug from the cosmetics these stores also sell.


def test_extract_attributes_medicine_product():
    attributes = ShopifyConnector.extract_attributes({
        "product_type": "Medicamentos",
        "tags": ["paracetamol", "analgesico", "500"],
    })
    assert attributes == {
        "category": "Medicamentos",
        "isMedicine": True,
        "tags": ["paracetamol", "analgesico"],
    }


def test_extract_attributes_empty_payload_does_not_raise():
    assert ShopifyConnector.extract_attributes({}) == {}


def test_extract_attributes_null_fields_do_not_raise():
    assert ShopifyConnector.extract_attributes({"product_type": None, "tags": None}) == {}


@pytest.mark.parametrize("product_type", sorted(ShopifyConnector.NON_MEDICINE_TYPES))
def test_non_medicine_types_flagged_false(product_type):
    attributes = ShopifyConnector.extract_attributes({"product_type": product_type})
    assert attributes["isMedicine"] is False
    assert attributes["category"] == product_type


@pytest.mark.parametrize("product_type", ["Dermocosmetica", "DERMOCOSMETICA", "  Belleza  "])
def test_non_medicine_match_is_case_and_whitespace_insensitive(product_type):
    assert ShopifyConnector.extract_attributes({"product_type": product_type})["isMedicine"] is False


def test_category_keeps_original_casing_of_product_type():
    """Only the isMedicine lookup is lowercased; the label stays as published."""
    attributes = ShopifyConnector.extract_attributes({"product_type": " Dermocosmetica "})
    assert attributes["category"] == "Dermocosmetica"


def test_unknown_product_type_defaults_to_medicine():
    """Farmex/Curie are pharmacies; an unlisted type is assumed to be a drug."""
    assert ShopifyConnector.extract_attributes({"product_type": "Antibióticos"})["isMedicine"] is True


def test_blank_product_type_leaves_category_and_flag_unset():
    attributes = ShopifyConnector.extract_attributes({"product_type": "   ", "tags": ["x"]})
    assert "category" not in attributes
    assert "isMedicine" not in attributes
    assert attributes["tags"] == ["x"]


def test_numeric_tags_dropped():
    """Shopify stores dump barcodes and dosages as bare-number tags; they are noise."""
    attributes = ShopifyConnector.extract_attributes({"tags": ["7801234567890", "500", "ibuprofeno"]})
    assert attributes["tags"] == ["ibuprofeno"]


def test_tags_capped_at_ten():
    attributes = ShopifyConnector.extract_attributes({"tags": [f"tag{i}" for i in range(25)]})
    assert attributes["tags"] == [f"tag{i}" for i in range(10)]


def test_empty_tag_list_leaves_key_unset():
    assert "tags" not in ShopifyConnector.extract_attributes({"tags": []})


def test_all_numeric_tags_yield_empty_list():
    # Current behaviour: the key is present but empty once every tag is filtered.
    assert ShopifyConnector.extract_attributes({"tags": ["1", "2"]}) == {"tags": []}


# Regression: parse_product used to compute `attributes` and then drop it on the
# floor, so every Shopify product reached the database with attributes = NULL.
def test_parse_product_attaches_attributes(connector):
    raw = {
        "title": "Ibuprofeno 400 mg x 20 comprimidos",
        "handle": "ibuprofeno-400",
        "vendor": "Farmex",
        "product_type": "Medicamentos",
        "tags": ["ibuprofeno", "400"],
        "variants": [{"id": 1, "title": "Default Title", "available": True, "price": "2990"}],
    }
    product = connector.parse_product(raw)[0]
    assert product.attributes == {
        "category": "Medicamentos",
        "isMedicine": True,
        "tags": ["ibuprofeno"],
    }


def test_parse_product_attributes_none_when_nothing_extracted(connector):
    """None, never {} — an empty dict reads as 'we looked and it has none'."""
    raw = {
        "title": "Med", "handle": "med", "vendor": None,
        "variants": [{"id": 1, "title": "Default Title", "available": True, "price": "100"}],
    }
    assert connector.parse_product(raw)[0].attributes is None


# --- variant image fallback ------------------------------------------------
# On Farmex/Curie `variant.featured_image` is null for ~99% of variants, so
# `images[0]` is what actually gets stored.

def test_variant_featured_image_wins(connector):
    raw = {
        "handle": "h", "title": "Med", "vendor": "Lab",
        "images": [{"src": "https://cdn/product.jpg"}],
        "variants": [{
            "id": 1, "price": "1000", "available": True,
            "featured_image": {"src": "https://cdn/variant.jpg"},
        }],
    }
    assert connector.parse_product(raw)[0].image_url == "https://cdn/variant.jpg"


def test_featured_image_with_null_src_falls_back_to_product_image(connector):
    # The old `if featured_image` form stored None here instead of the photo.
    raw = {
        "handle": "h", "title": "Med", "vendor": "Lab",
        "images": [{"src": "https://cdn/product.jpg"}],
        "variants": [{"id": 1, "price": "1000", "available": True, "featured_image": {"src": None}}],
    }
    assert connector.parse_product(raw)[0].image_url == "https://cdn/product.jpg"


def test_first_image_without_src_is_skipped(connector):
    raw = {
        "handle": "h", "title": "Med", "vendor": "Lab",
        "images": [{"alt": "no src"}, {"src": "https://cdn/real.jpg"}],
        "variants": [{"id": 1, "price": "1000", "available": True}],
    }
    assert connector.parse_product(raw)[0].image_url == "https://cdn/real.jpg"


def test_all_variants_share_the_product_photo(connector):
    raw = {
        "handle": "h", "title": "Med", "vendor": "Lab",
        "images": [{"src": "https://cdn/product.jpg"}],
        "variants": [
            {"id": 1, "title": "30 comp", "price": "1000", "available": True},
            {"id": 2, "title": "60 comp", "price": "1800", "available": True},
        ],
    }
    assert [p.image_url for p in connector.parse_product(raw)] == [
        "https://cdn/product.jpg", "https://cdn/product.jpg"
    ]
