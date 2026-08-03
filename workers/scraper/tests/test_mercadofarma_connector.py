"""MercadoFarma connector tests.

Fixtures are real payloads captured from
https://www.mercadofarma.cl/products.json?limit=250&page=N during recon.
No network is touched here.
"""
import pytest

from src.connectors.mercadofarma_connector import (
    MERCADOFARMA_CONFIGS,
    MercadoFarmaConnector,
    fold,
    strip_html,
)


@pytest.fixture
def connector():
    return MercadoFarmaConnector(MERCADOFARMA_CONFIGS["mercadofarma"])


# Real product: Baclofeno 10mg, product_type "medicamento", full description
# template. Description trimmed to the sections the connector reads.
BACLOFENO = {
    "id": 9527433756930,
    "title": "Baclofeno 10mg 20 Comprimidos (CENABAST)",
    "handle": "baclofeno-10mg-20-comprimidos-cenabast",
    "vendor": "VITAFARMA",
    "product_type": "medicamento",
    "tags": ["baclofeno"],
    "body_html": (
        "<style>a { color: #464feb; }</style>\n<div>\n"
        "<h2>Baclofeno 10 mg 20 Comprimidos</h2>\n"
        "<h2>Baclofeno</h2>\n"
        "<h3>Laboratorio Vitafarma</h3>\n"
        "<p>&nbsp;</p>\n"
        "<h4>Composición de Baclofeno</h4>\n<p>Baclofeno 10 mg.</p>\n"
        "<h4>Presentación de Baclofeno</h4>\n<p>Comprimidos.</p>\n"
        "</div>"
    ),
    "images": [{"src": "https://cdn.shopify.com/s/files/1/0461/5595/6392/files/Baclofeno.webp?v=1"}],
    "variants": [{
        "id": 48241110778114,
        "title": "Default Title",
        "sku": "MF43930",
        "available": True,
        "price": "3890",
        "compare_at_price": None,
        "featured_image": None,
    }],
}

# Real product: a wrist brace. product_type is the negative flag, and the
# second <h2> holds a brand ("Blunding"), not an active ingredient.
MUNEQUERA = {
    "id": 9516553896194,
    "title": "Muñequera Inmovilizadora Dedo Pulgar Blunding",
    "handle": "munequera-inmovilizadora-dedo-pulgar-blunding",
    "vendor": "ACTIMOVE",
    "product_type": "sin medicamento",
    "tags": ["muñequera", "sm"],
    "body_html": (
        "<div><h2>Muñequera Inmovilizadora Dedo Pulgar</h2>"
        "<h2>Blunding</h2></div>"
    ),
    "images": [],
    "variants": [{
        "id": 48184624087298,
        "title": "Default Title",
        "sku": "MF4587",
        "available": True,
        "price": "6990",
        "compare_at_price": None,
        "featured_image": None,
    }],
}


# --- config / url -------------------------------------------------------

def test_config_registered():
    assert set(MERCADOFARMA_CONFIGS) == {"mercadofarma"}
    config = MERCADOFARMA_CONFIGS["mercadofarma"]
    assert config.chain == "mercadofarma"
    assert config.base_url == "https://www.mercadofarma.cl"


def test_build_page_url(connector):
    assert connector.build_page_url(3) == (
        "https://www.mercadofarma.cl/products.json?limit=250&page=3"
    )


def test_uses_identifiable_bot_user_agent(connector):
    assert connector.user_agent.startswith("FarmaciaCompareBot/")


# --- helpers ------------------------------------------------------------

def test_strip_html_flattens_and_unescapes():
    assert strip_html("<p>Baclofeno&nbsp;10 mg.</p>") == "Baclofeno 10 mg."


def test_strip_html_on_empty_input():
    assert strip_html(None) == ""
    assert strip_html("") == ""


@pytest.mark.parametrize("raw,expected", [
    ("Medicamento", "medicamento"),
    ("  SIN   MEDICAMENTO ", "sin medicamento"),
    ("Belleza y perfumería", "belleza y perfumeria"),
])
def test_fold_lowercases_and_deaccents(raw, expected):
    assert fold(raw) == expected


# --- medicine classification -------------------------------------------
# MercadoFarma publishes a binary flag, not a category, and misspells it.
# "sin medicamento" contains "medicamento", so the negative form must win.

@pytest.mark.parametrize("product_type", [
    "medicamento", "Medicamento", "medicamentos", "medicamaento",
    "Medicinas y medicamentos",
])
def test_medicine_types_including_typos(product_type):
    assert MercadoFarmaConnector.classify_medicine(product_type) is True


@pytest.mark.parametrize("product_type", [
    "sin medicamento", "Sin medicamento", "sin medicamentos",
    "sin medicaento", "sin medicamnto", "  SIN MEDICAMENTO  ",
])
def test_negative_flag_beats_the_medicamento_substring(product_type):
    assert MercadoFarmaConnector.classify_medicine(product_type) is False


@pytest.mark.parametrize("product_type", [
    "", "   ", None, "no aplica", ", no aplica", "NO DISPONIBLE", "fnl",
    "Dermocream",
])
def test_valueless_product_type_yields_no_verdict(product_type):
    """Unlike the shared Shopify connector we do NOT default to isMedicine=True:
    MercadoFarma publishes an explicit flag, so an unrecognised value is a data
    hole rather than evidence of a drug."""
    assert MercadoFarmaConnector.classify_medicine(product_type) is None


# --- attributes ---------------------------------------------------------

def test_extract_attributes_medicine_mines_the_description():
    attributes = MercadoFarmaConnector.extract_attributes(BACLOFENO)
    assert attributes == {
        "category": "medicamento",
        "isMedicine": True,
        "activeIngredient": "Baclofeno",
        "composition": "Baclofeno 10 mg",
        "presentation": "Comprimidos",
        "laboratory": "Vitafarma",
        "tags": ["baclofeno"],
    }


def test_active_ingredient_not_mined_for_non_medicines():
    """The second <h2> of a wrist brace is a brand name, not an ingredient."""
    attributes = MercadoFarmaConnector.extract_attributes(MUNEQUERA)
    assert attributes["isMedicine"] is False
    assert "activeIngredient" not in attributes
    assert MercadoFarmaConnector.extract_active_ingredient(
        MUNEQUERA["body_html"]
    ) == "Blunding"


def test_category_keeps_the_published_label_typos_included():
    attributes = MercadoFarmaConnector.extract_attributes({"product_type": "medicamaento"})
    assert attributes["category"] == "medicamaento"
    assert attributes["isMedicine"] is True


def test_blank_product_type_leaves_category_and_flag_unset():
    assert MercadoFarmaConnector.extract_attributes({"product_type": "   "}) == {}


def test_extract_attributes_empty_payload_does_not_raise():
    assert MercadoFarmaConnector.extract_attributes({}) == {}


def test_extract_attributes_null_fields_do_not_raise():
    assert MercadoFarmaConnector.extract_attributes(
        {"product_type": None, "tags": None, "body_html": None}
    ) == {}


def test_single_h2_yields_no_active_ingredient():
    assert MercadoFarmaConnector.extract_active_ingredient("<h2>Solo uno</h2>") is None


def test_bioequivalent_and_prescription_tags_promoted():
    attributes = MercadoFarmaConnector.extract_attributes({
        "product_type": "medicamento",
        "tags": ["Bioequivalente", "receta", "ibuprofeno"],
    })
    assert attributes["isBioequivalent"] is True
    assert attributes["requiresPrescription"] is True


def test_ops_noise_tags_dropped():
    """'sm' is the store's shorthand for 'sin medicamento'; 'upretenido' and
    'suscripcion' are merchandising flags. None help matching."""
    attributes = MercadoFarmaConnector.extract_attributes({
        "tags": ["sm", "suscripcion", "upretenidos", "paracetamol"],
    })
    assert attributes["tags"] == ["paracetamol"]


def test_numeric_tags_dropped():
    attributes = MercadoFarmaConnector.extract_attributes({"tags": ["500", "ibuprofeno"]})
    assert attributes["tags"] == ["ibuprofeno"]


def test_tags_capped_at_ten():
    attributes = MercadoFarmaConnector.extract_attributes(
        {"tags": [f"tag{i}" for i in range(25)]}
    )
    assert attributes["tags"] == [f"tag{i}" for i in range(10)]


def test_tag_list_that_filters_to_nothing_leaves_key_unset():
    assert "tags" not in MercadoFarmaConnector.extract_attributes({"tags": ["sm", "7"]})


# --- parse_product ------------------------------------------------------

def test_parse_real_medicine(connector):
    products = connector.parse_product(BACLOFENO)
    assert len(products) == 1
    p = products[0]
    assert p.sku == "48241110778114"
    assert p.name == "Baclofeno 10mg 20 Comprimidos (CENABAST)"
    assert p.price == 3890
    assert p.original_price is None
    assert p.discount_pct is None
    assert p.brand == "VITAFARMA"
    assert p.laboratory == "VITAFARMA"
    assert p.stock_status == "in_stock"
    assert p.pharmacy_chain == "mercadofarma"
    assert p.source == "api"
    assert p.url == (
        "https://www.mercadofarma.cl/products/baclofeno-10mg-20-comprimidos-cenabast"
    )
    assert p.image_url.startswith("https://cdn.shopify.com/")


def test_merchant_sku_is_never_published_as_a_barcode(connector):
    """MercadoFarma has no EANs; `variant.sku` is an internal MF##### code.
    Mapping it to `barcode` (as the shared Shopify connector does for Farmex)
    would invent cross-chain identity keys — "MF777654323" survives
    normalize_barcode as a 9-digit "barcode"."""
    p = connector.parse_product(BACLOFENO)[0]
    assert p.barcode is None
    assert p.attributes["merchantSku"] == "MF43930"


def test_merchant_sku_that_looks_like_a_barcode_still_not_a_barcode(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], sku="MF777654323")])
    p = connector.parse_product(raw)[0]
    assert p.barcode is None
    assert p.attributes["merchantSku"] == "MF777654323"


def test_blank_merchant_sku_falls_back_to_variant_id(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], sku="")])
    p = connector.parse_product(raw)[0]
    assert p.sku == "48241110778114"
    assert "merchantSku" not in p.attributes


def test_decimal_price_is_not_read_as_thousands_separator(connector):
    """Shopify sends machine numbers: '1004.0' is 1004 CLP, not 10040."""
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], price="1004.0")])
    assert connector.parse_product(raw)[0].price == 1004


def test_thousands_looking_price_is_taken_at_face_value(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], price="12990")])
    assert connector.parse_product(raw)[0].price == 12990


def test_prices_are_integers(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], price="3890.6")])
    price = connector.parse_product(raw)[0].price
    assert isinstance(price, int) and price == 3890


def test_zero_price_placeholder_skipped(connector):
    """$0 Cenabast/insurance variants are not offers and would win every
    'cheapest price' ranking."""
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], price="0")])
    assert connector.parse_product(raw) == []


def test_missing_price_skipped(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], price=None)])
    assert connector.parse_product(raw) == []


def test_discount_computed_from_compare_at(connector):
    raw = dict(BACLOFENO, variants=[
        dict(BACLOFENO["variants"][0], price="7439", compare_at_price="7990"),
    ])
    p = connector.parse_product(raw)[0]
    assert p.original_price == 7990
    assert p.discount_pct == 7


def test_compare_at_below_price_is_not_a_discount(connector):
    raw = dict(BACLOFENO, variants=[
        dict(BACLOFENO["variants"][0], price="9990", compare_at_price="8990"),
    ])
    p = connector.parse_product(raw)[0]
    assert p.original_price is None
    assert p.discount_pct is None


def test_unavailable_variant_is_out_of_stock(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], available=False)])
    p = connector.parse_product(raw)[0]
    assert p.stock_status == "out_of_stock"
    assert p.stock_quantity is None


def test_variant_title_appended_when_not_default(connector):
    raw = dict(BACLOFENO, variants=[dict(BACLOFENO["variants"][0], title="60 comprimidos")])
    assert connector.parse_product(raw)[0].name == (
        "Baclofeno 10mg 20 Comprimidos (CENABAST) - 60 comprimidos"
    )


def test_featured_image_wins_over_product_image(connector):
    raw = dict(BACLOFENO, variants=[
        dict(BACLOFENO["variants"][0], featured_image={"src": "https://cdn/variant.jpg"}),
    ])
    assert connector.parse_product(raw)[0].image_url == "https://cdn/variant.jpg"


def test_product_without_images_has_no_image_url(connector):
    assert connector.parse_product(MUNEQUERA)[0].image_url is None


def test_laboratory_falls_back_to_description_when_vendor_blank(connector):
    raw = dict(BACLOFENO, vendor="")
    p = connector.parse_product(raw)[0]
    assert p.brand is None
    assert p.laboratory == "Vitafarma"


def test_parse_product_attaches_attributes(connector):
    p = connector.parse_product(MUNEQUERA)[0]
    assert p.attributes["isMedicine"] is False
    assert p.attributes["category"] == "sin medicamento"
    assert p.attributes["tags"] == ["muñequera"]


def test_attributes_none_when_nothing_extracted(connector):
    """None, never {} — an empty dict reads as 'we looked and it has none'."""
    raw = {
        "title": "Med", "handle": "med", "vendor": None,
        "variants": [{"id": 1, "title": "Default Title", "available": True,
                      "price": "100", "sku": ""}],
    }
    assert connector.parse_product(raw)[0].attributes is None


def test_product_with_no_variants_yields_nothing(connector):
    assert connector.parse_product({"title": "x", "handle": "x", "variants": []}) == []


def test_missing_handle_yields_no_url(connector):
    raw = dict(BACLOFENO, handle="")
    assert connector.parse_product(raw)[0].url is None


# --- scrape_products ----------------------------------------------------

@pytest.mark.asyncio
async def test_scrape_products_pages_until_empty(connector, monkeypatch):
    pages = {1: [BACLOFENO], 2: [MUNEQUERA], 3: []}
    seen: list[str] = []

    async def fake_get_json(client, url, **kwargs):
        seen.append(url)
        page = int(url.rsplit("page=", 1)[1])
        return {"products": pages.get(page, [])}

    monkeypatch.setattr(
        "src.connectors.mercadofarma_connector.get_json", fake_get_json
    )

    async def no_delay(*args, **kwargs):
        return None

    monkeypatch.setattr(connector, "random_delay", no_delay)

    products = [p async for p in connector.scrape_products()]
    assert [p.price for p in products] == [3890, 6990]
    assert len(seen) == 3
    assert seen[0].endswith("page=1")


@pytest.mark.asyncio
async def test_scrape_products_stops_on_http_failure(connector, monkeypatch):
    async def boom(client, url, **kwargs):
        if url.endswith("page=1"):
            return {"products": [BACLOFENO]}
        raise RuntimeError("503")

    monkeypatch.setattr("src.connectors.mercadofarma_connector.get_json", boom)

    async def no_delay(*args, **kwargs):
        return None

    monkeypatch.setattr(connector, "random_delay", no_delay)

    products = [p async for p in connector.scrape_products()]
    assert len(products) == 1
