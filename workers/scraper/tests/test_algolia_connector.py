import pytest
from src.connectors.algolia_connector import ALGOLIA_CONFIGS, AlgoliaConnector


@pytest.fixture
def connector():
    return AlgoliaConnector(ALGOLIA_CONFIGS["salcobrand"])


def test_query_url(connector):
    assert connector.query_url == "https://GM3RP06HJG-dsn.algolia.net/1/indexes/sb_variant_production/query"


def test_headers_include_referer_restriction(connector):
    headers = connector._headers()
    # The search key is referer-restricted; without these the API answers 403.
    assert headers["Referer"] == "https://salcobrand.cl/"
    assert headers["Origin"] == "https://salcobrand.cl"
    assert headers["X-Algolia-Application-Id"] == "GM3RP06HJG"


def test_parse_hit_with_direct_discount(connector):
    hit = {
        "sku": "430924",
        "name": "Kitadol (B) Paracetamol 500mg 24 Comprimidos",
        "brand": "Kitadol",
        "normal_price": 1499,
        "direct_discount": "1004.0",
        "has_stock": True,
        "slug": "kitadol-b-paracetamol-500mg-24-comprimidos",
        "catalog_image_url": "https://static.salcobrand.cl/img.jpg",
    }
    p = connector.parse_hit(hit)
    assert p.sku == "430924"
    # '1004.0' must not become 10040 — it is a decimal, not a CLP thousands string.
    assert p.price == 1004
    assert p.original_price == 1499
    assert p.discount_pct == 33
    assert p.stock_status == "in_stock"
    assert p.url == "https://salcobrand.cl/products/kitadol-b-paracetamol-500mg-24-comprimidos"


def test_parse_hit_without_discount(connector):
    hit = {"sku": "1", "name": "Med", "normal_price": 3990, "direct_discount": None, "has_stock": False}
    p = connector.parse_hit(hit)
    assert p.price == 3990
    assert p.original_price is None
    assert p.discount_pct is None
    assert p.stock_status == "out_of_stock"
    assert p.url is None


def test_parse_hit_discount_above_normal_price_ignored(connector):
    hit = {"sku": "1", "name": "Med", "normal_price": 1000, "direct_discount": "1500.0", "has_stock": True}
    p = connector.parse_hit(hit)
    assert p.price == 1000
    assert p.original_price is None


def test_parse_hit_falls_back_to_object_id(connector):
    hit = {"objectID": "variant-9", "name": "Med", "normal_price": 100, "has_stock": True}
    assert connector.parse_hit(hit).sku == "variant-9"


def test_parse_hit_without_price_skipped(connector):
    assert connector.parse_hit({"sku": "1", "name": "Med"}) is None
    assert connector.parse_hit({"sku": "1", "normal_price": 100}) is None


# --- extract_attributes -------------------------------------------------
# Salcobrand publishes no EAN anywhere. The category breadcrumb and
# options_text are the whole identity signal for this chain.

PARACETAMOL_BREADCRUMB = (
    "Medicamentos > Dolor, Fiebre y Antiflamatorios > Analgésico General > Paracetamol"
)

FULL_SB_HIT = {
    "sku": "430924",
    "name": "Kitadol (B) Paracetamol 500mg 24 Comprimidos",
    "normal_price": 1499,
    "has_stock": True,
    "product_categories": {
        "lvl0": ["Medicamentos"],
        "lvl1": ["Medicamentos > Dolor, Fiebre y Antiflamatorios"],
        "lvl2": ["Medicamentos > Dolor, Fiebre y Antiflamatorios > Analgésico General"],
        "lvl3": [PARACETAMOL_BREADCRUMB],
    },
    "options_text": "24 Comprimidos",
    "sale_type": "unidad",
    "drug_patent_type_filter": "Bioequivalente",
    "needs_recipe": False,
    "bioequivalent_filter": {"has_bioequivalent": True},
    "taxonomies": ["Medicamentos", "Medicamentos > Dolor, Fiebre y Antiflamatorios"],
}


def test_extract_attributes_full_hit():
    attributes = AlgoliaConnector.extract_attributes(FULL_SB_HIT)
    assert attributes == {
        "category": PARACETAMOL_BREADCRUMB,
        "activeIngredient": "Paracetamol",
        "presentation": "24 Comprimidos",
        "saleType": "unidad",
        "patentType": "Bioequivalente",
        "requiresPrescription": False,
        "hasBioequivalent": True,
        "isMedicine": True,
    }


def test_extract_attributes_empty_hit_does_not_raise():
    assert AlgoliaConnector.extract_attributes({}) == {}


def test_deepest_category_level_wins():
    """lvl3 beats lvl2/lvl1/lvl0 even though all four are present."""
    attributes = AlgoliaConnector.extract_attributes(FULL_SB_HIT)
    assert attributes["category"] == PARACETAMOL_BREADCRUMB
    assert attributes["category"] != "Medicamentos"


def test_active_ingredient_only_claimed_at_lvl3():
    """Without lvl3 the leaf is a category name, not a molecule.

    "Belleza > Piel > Rostro" ends in "Rostro" — calling that an active
    ingredient would create a bogus matching key.
    """
    attributes = AlgoliaConnector.extract_attributes(
        {"product_categories": {"lvl0": ["Belleza"], "lvl2": ["Belleza > Piel > Rostro"]}}
    )
    assert attributes["category"] == "Belleza > Piel > Rostro"
    assert "activeIngredient" not in attributes


def test_empty_lvl3_list_falls_through_to_shallower_level():
    attributes = AlgoliaConnector.extract_attributes(
        {"product_categories": {"lvl3": [], "lvl1": ["Medicamentos > Dolor"]}}
    )
    assert attributes["category"] == "Medicamentos > Dolor"
    assert "activeIngredient" not in attributes


def test_category_level_accepts_bare_string_not_only_list():
    attributes = AlgoliaConnector.extract_attributes(
        {"product_categories": {"lvl3": "Medicamentos > Dolor > Analgésico > Ibuprofeno"}}
    )
    assert attributes["activeIngredient"] == "Ibuprofeno"


def test_active_ingredient_leaf_is_stripped():
    attributes = AlgoliaConnector.extract_attributes(
        {"product_categories": {"lvl3": ["Medicamentos > Dolor > Analgésico >   Paracetamol  "]}}
    )
    assert attributes["activeIngredient"] == "Paracetamol"


def test_missing_product_categories_does_not_raise():
    attributes = AlgoliaConnector.extract_attributes({"options_text": "30 Cápsulas"})
    assert attributes == {"presentation": "30 Cápsulas"}


def test_needs_recipe_false_is_recorded_not_dropped():
    """False means 'sold over the counter', which is real information."""
    assert AlgoliaConnector.extract_attributes({"needs_recipe": False}) == {
        "requiresPrescription": False
    }
    assert AlgoliaConnector.extract_attributes({"needs_recipe": True}) == {
        "requiresPrescription": True
    }


def test_has_bioequivalent_false_is_recorded_not_dropped():
    assert AlgoliaConnector.extract_attributes(
        {"bioequivalent_filter": {"has_bioequivalent": False}}
    ) == {"hasBioequivalent": False}


def test_bioequivalent_filter_of_unexpected_shape_is_ignored():
    """Algolia sends [] for hits with no bioequivalence data."""
    assert AlgoliaConnector.extract_attributes({"bioequivalent_filter": []}) == {}
    assert AlgoliaConnector.extract_attributes({"bioequivalent_filter": None}) == {}
    assert AlgoliaConnector.extract_attributes({"bioequivalent_filter": {}}) == {}


def test_is_medicine_from_taxonomies():
    assert AlgoliaConnector.extract_attributes(
        {"taxonomies": ["Medicamentos", "Medicamentos > Dolor"]}
    )["isMedicine"] is True
    assert AlgoliaConnector.extract_attributes(
        {"taxonomies": ["Dermocosmética", "Belleza"]}
    )["isMedicine"] is False


def test_empty_taxonomies_leaves_is_medicine_unset():
    """Absent is not the same as False — don't assert 'not a medicine' blindly."""
    assert "isMedicine" not in AlgoliaConnector.extract_attributes({"taxonomies": []})
    assert "isMedicine" not in AlgoliaConnector.extract_attributes({})


def test_parse_hit_attaches_attributes(connector):
    product = connector.parse_hit(FULL_SB_HIT)
    assert product.barcode is None       # the whole reason attributes matter here
    assert product.attributes["activeIngredient"] == "Paracetamol"
    assert product.attributes["presentation"] == "24 Comprimidos"
    assert product.attributes["isMedicine"] is True


def test_parse_hit_attributes_none_when_nothing_extracted(connector):
    """None, never {} — an empty dict reads as 'we looked and it has none'."""
    product = connector.parse_hit({"sku": "1", "name": "Med", "normal_price": 100})
    assert product.attributes is None
