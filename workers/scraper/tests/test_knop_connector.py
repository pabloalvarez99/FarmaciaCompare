"""Fixtures are trimmed copies of real www.farmaciasknop.com payloads
(/products/<slug>.json and /products.json rows) captured during recon.
No network is touched here.
"""
import pytest

from src.connectors.knop_connector import KNOP_CONFIGS, KnopConnector


@pytest.fixture
def connector():
    return KnopConnector(KNOP_CONFIGS["knop"])


# GLOB.COMPUESTO 49 VARICES — a real medicine row, single variant, no discount.
MEDICINE = {
    "id": 528409,
    "slug": "glob-compuesto-49-varices",
    "url": "https://www.farmaciasknop.com/products/glob-compuesto-49-varices",
    "name": "GLOB.COMPUESTO 49 VARICES",
    "model": "GLOB.COMPUESTO 49 VARICES",
    "blocked": False,
    "available": True,
    "currency_code": "CLP",
    "price": 6090,
    "regular_price": 6090,
    "sale_price": None,
    "product_type": {"name": "Medicamentos", "slug": "medicamentos"},
    "vendor": {"name": "Knop Laboratorios", "slug": "knop-laboratorios"},
    "images": [{
        "file_name": "glob.jpg",
        "variant_ids": [],
        "src": {
            "thumbnail": "https://r.bolder.run/22994/thumbnail/glob.jpg",
            "small": "https://r.bolder.run/22994/small/glob.jpg",
            "medium": "https://r.bolder.run/22994/medium/glob.jpg",
            "large": "https://r.bolder.run/22994/large/glob.jpg",
            "original": "https://r.bolder.run/22994/original/glob.jpg",
        },
    }],
    "variants": [{
        "id": 951377,
        "name": "GLOB.COMPUESTO 49 VARICES",
        "sku": "2000221100495",
        "price": 6090,
        "regular_price": 6090,
        "sale_price": None,
        "available": True,
        "online_stock": 12,
    }],
    "attributes": [
        {"name": "Cantidad", "slug": "cantidad", "value": 10},
        {"name": "Unidad de medida", "slug": "unidad-de-medida", "value": "GR"},
        {"name": "Marca", "slug": "marca", "value": "Knop"},
    ],
    "collections": [{"name": "Medicamento Natural", "slug": "medicamento-natural"}],
    "tags": ["Medicamentos", "PPUM 100"],
}

# Bio-Oil — two variants at different prices, variant names are bare sizes.
MULTI_VARIANT = {
    "id": 1,
    "slug": "aceite-corporal-bio-oil",
    "url": "https://www.farmaciasknop.com/products/aceite-corporal-bio-oil",
    "name": "Aceite Corporal Bio Oil",
    "blocked": False,
    "available": True,
    "price": 10490,
    "product_type": {"name": "Aceites Corporales", "slug": "aceites-corporales"},
    "vendor": {"name": "Bio Oil", "slug": "bio-oil"},
    "images": [
        {"variant_ids": [], "src": {"large": "https://r.bolder.run/x/large/default.jpg"}},
        {"variant_ids": [22], "src": {"large": "https://r.bolder.run/x/large/60ml.jpg"}},
    ],
    "variants": [
        {"id": 11, "name": "125 mL", "sku": "6001159111719", "price": 15990,
         "regular_price": 18990, "available": True, "online_stock": 1},
        {"id": 22, "name": "60 mL", "sku": "6001159111702", "price": 10490,
         "regular_price": 10490, "available": True, "online_stock": 3},
    ],
    "tags": [],
}


# --- parse_product happy path -------------------------------------------


def test_parse_medicine_product(connector):
    products = connector.parse_product(MEDICINE)
    assert len(products) == 1
    p = products[0]
    assert p.sku == "951377"
    assert p.name == "GLOB.COMPUESTO 49 VARICES"
    assert p.brand == "Knop Laboratorios"
    assert p.laboratory == "Knop Laboratorios"
    assert p.price == 6090
    assert p.original_price is None
    assert p.discount_pct is None
    assert p.stock_status == "in_stock"
    assert p.stock_quantity == 12
    assert p.barcode == "2000221100495"
    assert p.url == "https://www.farmaciasknop.com/products/glob-compuesto-49-varices"
    assert p.image_url == "https://r.bolder.run/22994/large/glob.jpg"
    assert p.pharmacy_chain == "knop"
    assert p.source == "api"


def test_prices_are_integer_clp(connector):
    p = connector.parse_product(MEDICINE)[0]
    assert isinstance(p.price, int)


def test_multi_variant_yields_one_offer_each(connector):
    products = connector.parse_product(MULTI_VARIANT)
    assert [p.price for p in products] == [15990, 10490]
    assert [p.name for p in products] == [
        "Aceite Corporal Bio Oil - 125 mL",
        "Aceite Corporal Bio Oil - 60 mL",
    ]
    assert [p.barcode for p in products] == ["6001159111719", "6001159111702"]


def test_discount_computed_from_regular_price(connector):
    big = connector.parse_product(MULTI_VARIANT)[0]
    assert big.original_price == 18990
    assert big.discount_pct == 16


def test_regular_price_equal_to_price_is_not_a_discount(connector):
    small = connector.parse_product(MULTI_VARIANT)[1]
    assert small.original_price is None
    assert small.discount_pct is None


def test_regular_price_below_price_is_not_a_discount(connector):
    raw = {**MEDICINE, "variants": [
        {**MEDICINE["variants"][0], "price": 9990, "regular_price": 8990}]}
    p = connector.parse_product(raw)[0]
    assert p.original_price is None
    assert p.discount_pct is None


def test_variant_image_preferred_over_default(connector):
    small = connector.parse_product(MULTI_VARIANT)[1]
    assert small.image_url == "https://r.bolder.run/x/large/60ml.jpg"


def test_variant_name_not_duplicated_when_it_repeats_the_title(connector):
    """Some Knop variants are named with the full product title plus the size."""
    raw = {**MEDICINE,
           "name": "Shampoo de Ortiga Equisetum Twice",
           "variants": [{**MEDICINE["variants"][0],
                         "name": "Shampoo de Ortiga Equisetum Twice 250 mL"}]}
    assert connector.parse_product(raw)[0].name == "Shampoo de Ortiga Equisetum Twice 250 mL"


# --- price sentinels ----------------------------------------------------


def test_zero_price_variant_skipped(connector):
    raw = {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "price": 0}]}
    assert connector.parse_product(raw) == []


def test_null_price_variant_skipped(connector):
    raw = {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "price": None}]}
    assert connector.parse_product(raw) == []


def test_zero_price_variant_skipped_but_siblings_kept(connector):
    raw = {**MULTI_VARIANT, "variants": [
        {**MULTI_VARIANT["variants"][0], "price": 0},
        MULTI_VARIANT["variants"][1],
    ]}
    products = connector.parse_product(raw)
    assert [p.price for p in products] == [10490]


def test_decimal_price_is_not_read_as_thousands_separator(connector):
    """'1004.0' is a decimal, not the Chilean 1.004 thousands format."""
    raw = {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "price": "1004.0"}]}
    assert connector.parse_product(raw)[0].price == 1004


# --- staging rows -------------------------------------------------------
# Knop left four test products live: "test test" $50, "MePa" $80,
# "Test prueba" $500, "test retail" $1.000.000. The cheap ones would win the
# cheapest-price ranking; anomaly.check_price's 200 CLP floor misses two.


def test_staging_row_without_vendor_or_barcode_skipped(connector):
    """'MePa' at $80 and 'test retail' at $1.000.000 look like this."""
    raw = {**MEDICINE, "vendor": None,
           "variants": [{**MEDICINE["variants"][0], "sku": None, "price": 80}]}
    assert connector.parse_product(raw) == []


def test_placeholder_sequential_sku_skipped(connector):
    """'Test prueba' ships sku 123456789, 'test test' ships 12345679."""
    raw = {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "sku": "123456789", "price": 500}]}
    assert connector.parse_product(raw) == []


def test_real_product_without_vendor_but_with_barcode_kept(connector):
    """A missing vendor alone must not delete a listing."""
    raw = {**MEDICINE, "vendor": None,
           "variants": [{**MEDICINE["variants"][0], "sku": "7804635392263"}]}
    assert len(connector.parse_product(raw)) == 1


def test_real_product_named_test_is_kept(connector):
    """'Test de Embarazo' is a genuine pregnancy test — never filter on name."""
    raw = {**MEDICINE, "name": "Test de Embarazo", "slug": "test-de-embarazo",
           "vendor": {"name": "ZenMed"},
           "variants": [{**MEDICINE["variants"][0], "sku": "6950996001656", "price": 2990}]}
    products = connector.parse_product(raw)
    assert len(products) == 1
    assert products[0].price == 2990


@pytest.mark.parametrize("sku", ["7804635392263", "2000221100495", "6001159111719"])
def test_real_barcodes_not_treated_as_placeholders(connector, sku):
    raw = {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "sku": sku}]}
    assert connector.parse_product(raw)[0].barcode == sku


# --- missing fields -----------------------------------------------------


def test_product_without_name_skipped(connector):
    assert connector.parse_product({**MEDICINE, "name": "", "model": ""}) == []


def test_blocked_product_skipped(connector):
    """Bolder keeps delisted products in the feed with blocked=true."""
    assert connector.parse_product({**MEDICINE, "blocked": True}) == []


def test_missing_vendor_leaves_brand_none(connector):
    p = connector.parse_product({**MEDICINE, "vendor": None})[0]
    assert p.brand is None
    assert p.laboratory is None


def test_missing_images_leaves_image_none(connector):
    p = connector.parse_product({**MEDICINE, "images": []})[0]
    assert p.image_url is None


def test_image_string_fallback_used_when_images_absent(connector):
    raw = {**MEDICINE, "images": [], "image": "https://r.bolder.run/x/small/fallback.jpg"}
    assert connector.parse_product(raw)[0].image_url == "https://r.bolder.run/x/small/fallback.jpg"


def test_missing_url_rebuilt_from_slug(connector):
    p = connector.parse_product({**MEDICINE, "url": None})[0]
    assert p.url == "https://www.farmaciasknop.com/products/glob-compuesto-49-varices"


def test_missing_sku_falls_back_to_variant_id(connector):
    p = connector.parse_product(
        {**MEDICINE, "variants": [{**MEDICINE["variants"][0], "sku": None}]})[0]
    assert p.barcode is None
    assert p.sku == "951377"


def test_list_row_without_variants_still_yields_an_offer(connector):
    """/products.json rows carry no `variants`; the fallback pager needs them."""
    row = {
        "id": 582235, "slug": "spray-breathing-space-room-100-ml",
        "name": "Spray breathing space room 100 mL", "blocked": False,
        "available": True, "price": 24990, "regular_price": 24990,
        "product_type": {"name": "Vias Respiratorias", "slug": "vias-respiratorias"},
        "vendor": {"name": "Perfect Potion", "slug": "perfect-potion"},
    }
    p = connector.parse_product(row)[0]
    assert p.price == 24990
    assert p.sku == "582235"
    assert p.barcode is None
    assert p.stock_status == "in_stock"
    assert p.stock_quantity is None


# --- stock --------------------------------------------------------------


def test_unavailable_variant_is_out_of_stock(connector):
    raw = {**MEDICINE, "variants": [
        {**MEDICINE["variants"][0], "available": False, "online_stock": 0}]}
    assert connector.parse_product(raw)[0].stock_status == "out_of_stock"


@pytest.mark.parametrize("quantity,expected", [
    (0, "in_stock"),      # available_if_no_stock backorders
    (1, "low_stock"),
    (3, "low_stock"),
    (4, "in_stock"),
    (None, "in_stock"),
])
def test_stock_status_from_online_stock(connector, quantity, expected):
    raw = {**MEDICINE, "variants": [
        {**MEDICINE["variants"][0], "available": True, "online_stock": quantity}]}
    assert connector.parse_product(raw)[0].stock_status == expected


# --- extract_attributes -------------------------------------------------


def test_extract_attributes_full_medicine():
    assert KnopConnector.extract_attributes(MEDICINE) == {
        "category": "Medicamentos",
        "isMedicine": True,
        "presentation": "10 GR",
        "format": "GR",
        "brand": "Knop",
        "tags": ["Medicamentos"],
    }


def test_medicamentos_tag_flags_medicine_on_an_ailment_category():
    """Knop tags real drugs "Medicamentos" even under categories like `varices`."""
    attributes = KnopConnector.extract_attributes({
        "product_type": {"name": "Varices", "slug": "varices"},
        "tags": ["Medicamentos"],
    })
    assert attributes["isMedicine"] is True
    assert attributes["category"] == "Varices"


def test_supplement_category_is_not_medicine():
    attributes = KnopConnector.extract_attributes({
        "product_type": {"name": "Vitaminas", "slug": "vitaminas"}, "tags": [],
    })
    assert attributes["isMedicine"] is False


def test_untyped_untagged_product_leaves_ismedicine_unset():
    """Unknown is not the same as 'not a medicine'."""
    assert "isMedicine" not in KnopConnector.extract_attributes({"product_type": None})


def test_extract_attributes_empty_payload_does_not_raise():
    assert KnopConnector.extract_attributes({}) == {}


def test_extract_attributes_null_fields_do_not_raise():
    assert KnopConnector.extract_attributes(
        {"product_type": None, "tags": None, "attributes": None, "variants": None}) == {}


def test_internal_warehouse_tags_dropped():
    """Bolder's tag field doubles as a logistics label: PPUM 100, carga2, 060426."""
    attributes = KnopConnector.extract_attributes(
        {"tags": ["PPUM 100", "carga2", "car3", "060426", "minerales"]})
    assert attributes["tags"] == ["minerales"]


def test_tags_capped_at_ten():
    attributes = KnopConnector.extract_attributes({"tags": [f"tag{i}" for i in range(25)]})
    assert attributes["tags"] == [f"tag{i}" for i in range(10)]


def test_quantity_without_unit_still_reports_presentation():
    attributes = KnopConnector.extract_attributes(
        {"attributes": [{"name": "Cantidad", "slug": "cantidad", "value": 30}]})
    assert attributes["presentation"] == "30"
    assert "format" not in attributes


def test_presentacion_attribute_used_when_cantidad_absent():
    attributes = KnopConnector.extract_attributes(
        {"attributes": [{"name": "Presentacion", "slug": "presentacion", "value": "Frasco 120 mL"}]})
    assert attributes["presentation"] == "Frasco 120 mL"


def test_ingredients_reported_verbatim_not_as_active_ingredient():
    """Knop publishes the whole panel; calling it activeIngredient would lie."""
    attributes = KnopConnector.extract_attributes(
        {"attributes": [{"name": "Ingredientes", "slug": "ingredientes",
                         "value": "alcohol, aceite esencial de limon"}]})
    assert attributes["ingredients"] == "alcohol, aceite esencial de limon"
    assert "activeIngredient" not in attributes


def test_ingredients_truncated():
    attributes = KnopConnector.extract_attributes(
        {"attributes": [{"name": "Ingredientes", "slug": "ingredientes", "value": "x" * 900}]})
    assert len(attributes["ingredients"]) == 500


def test_blank_attribute_values_ignored():
    attributes = KnopConnector.extract_attributes(
        {"attributes": [{"name": "Marca", "slug": "marca", "value": "  "},
                        {"name": "Cantidad", "slug": "cantidad", "value": None},
                        "not-a-dict"]})
    assert attributes == {}


# Regression guard: the Shopify connector once computed attributes and then
# dropped them, so every product reached the database with attributes = NULL.
def test_parse_product_attaches_attributes(connector):
    p = connector.parse_product(MEDICINE)[0]
    assert p.attributes is not None
    assert p.attributes["isMedicine"] is True
    assert p.attributes["presentation"] == "10 GR"


def test_parse_product_attributes_none_when_nothing_extracted(connector):
    """None, never {} — an empty dict reads as 'we looked and it has none'."""
    raw = {
        "id": 9, "slug": "x", "name": "Sin metadatos", "blocked": False,
        "product_type": None, "vendor": None, "tags": [], "attributes": [],
        "variants": [{"id": 9, "name": "Sin metadatos", "sku": "7801234567890",
                      "price": 1990, "available": True}],
    }
    assert connector.parse_product(raw)[0].attributes is None


def test_attributes_shared_across_variants_of_one_product(connector):
    products = connector.parse_product(MULTI_VARIANT)
    assert products[0].attributes == products[1].attributes


# --- URLs / discovery helpers -------------------------------------------


def test_registry_has_the_single_knop_store():
    assert set(KNOP_CONFIGS) == {"knop"}


def test_build_page_url(connector):
    assert connector.build_page_url(2) == "https://www.farmaciasknop.com/products.json?page=2"


def test_detail_url(connector):
    assert connector.detail_url("abc") == "https://www.farmaciasknop.com/products/abc.json"


@pytest.mark.parametrize("url,expected", [
    ("https://www.farmaciasknop.com/products/spray-relax-aromatic-50-ml",
     "spray-relax-aromatic-50-ml"),
    ("https://www.farmaciasknop.com/products/abc/", "abc"),
    ("https://www.farmaciasknop.com/products/abc.json", "abc"),
    ("https://www.farmaciasknop.com/collections/suplementos", None),
    ("", None),
])
def test_extract_slug(url, expected):
    assert KnopConnector.extract_slug(url) == expected


def test_identifies_with_the_bot_user_agent(connector):
    """farmaciasknop.com serves 200 to the bot UA, so no browser spoofing."""
    assert connector.use_browser_ua is False
    assert "FarmaciaCompareBot" in connector.user_agent
