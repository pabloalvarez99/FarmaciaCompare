import pytest
from src.connectors.ocapi_connector import OCAPI_CONFIGS, OcapiConnector


@pytest.fixture
def connector():
    return OcapiConnector(OCAPI_CONFIGS["cruz_verde"])


def test_shop_api_root(connector):
    assert connector.shop_api == "https://beta.cruzverde.cl/s/Chile/dw/shop/v19_1"


def test_product_url_carries_client_id_and_expansions(connector):
    url = connector.product_url("266145")
    assert url.startswith("https://beta.cruzverde.cl/s/Chile/dw/shop/v19_1/products/266145")
    assert "client_id=c19ce24d-1677-4754-b9f7-c193997c5a92" in url
    assert "expand=prices,availability,images" in url


@pytest.mark.parametrize("url,expected", [
    ("https://www.cruzverde.cl/morelin-amitriptilina-125-mg-30-comprimidos/1006.html", "1006"),
    ("https://www.cruzverde.cl/xumadol-paracetamol/266145.html", "266145"),
    ("https://www.cruzverde.cl/medicamentos", None),
    ("https://www.cruzverde.cl/algo/abc.html", None),
])
def test_extract_product_id(url, expected):
    assert OcapiConnector.extract_product_id(url) == expected


def test_parse_product_full_payload(connector):
    raw = {
        "id": "1006",
        "name": "Morelin Amitriptilina 12,5 mg 30 Comprimidos",
        "brand": "LABORATORIO CHILE",
        "price": 27990,
        "prices": {"price-list-cl": 31990},
        "currency": "CLP",
        "ean": "7801234567890",
        "inventory": {"orderable": True, "stock_level": 15},
        "image_groups": [{"view_type": "large", "images": [{"link": "https://img/1.jpg"}]}],
    }
    p = connector.parse_product(raw)
    assert p.sku == "1006"
    assert p.price == 27990
    assert p.original_price == 31990
    assert p.discount_pct == 13
    assert p.stock_status == "in_stock"
    assert p.stock_quantity == 15
    assert p.barcode == "7801234567890"
    assert p.image_url == "https://img/1.jpg"
    assert p.pharmacy_chain == "cruz_verde"


def test_parse_product_equal_list_price_is_no_discount(connector):
    raw = {
        "id": "1", "name": "Med", "price": 5000, "prices": {"price-list-cl": 5000},
        "inventory": {"orderable": True, "stock_level": 30},
    }
    p = connector.parse_product(raw)
    assert p.original_price is None
    assert p.discount_pct is None


def test_parse_product_low_and_out_of_stock(connector):
    low = connector.parse_product(
        {"id": "1", "name": "Med", "price": 100, "inventory": {"orderable": True, "stock_level": 2}}
    )
    gone = connector.parse_product(
        {"id": "2", "name": "Med", "price": 100, "inventory": {"orderable": False, "stock_level": 0}}
    )
    assert low.stock_status == "low_stock"
    assert gone.stock_status == "out_of_stock"


def test_parse_product_without_price_skipped(connector):
    assert connector.parse_product({"id": "1", "name": "Med"}) is None
    assert connector.parse_product({"id": "1", "price": 100}) is None


def test_parse_search_hit(connector):
    hit = {
        "product_id": "266145",
        "product_name": "Xumadol Paracetamol 1000 mg 20 Comprimidos",
        "price": 7690,
        "prices": {"price-list-cl": 11390},
        "orderable": True,
        "image": {"link": "https://img/x.jpg"},
    }
    p = connector.parse_search_hit(hit)
    assert p.price == 7690
    assert p.original_price == 11390
    assert p.discount_pct == 32
    assert p.stock_status == "in_stock"
    assert p.image_url == "https://img/x.jpg"


def test_search_url_shape(connector):
    url = connector.search_url("paracetamol", start=200, count=200)
    assert "q=paracetamol" in url
    assert "start=200" in url
    assert "count=200" in url


# --- extract_attributes -------------------------------------------------
# Cruz Verde publishes no EAN, so the c_* custom attributes are the only
# identity signal we get for this chain. Losing one silently unmatches a drug.

FULL_CV_PAYLOAD = {
    "id": "266145",
    "name": "Xumadol Paracetamol 1000 mg 20 Comprimidos",
    "price": 7690,
    "c_activeIngredient": "PARACETAMOL",
    "c_dose": 582,
    "c_format": "20-unidades",
    "c_laboratory": "LABORATORIO CHILE",
    "c_isMedProduct": True,
    "c_isBioequivalent": True,
    "c_bioequivalentSubCategoryID": "paracetamol-1000-mg",
    "c_prescription": "venta-directa",
    "primary_category_id": "medicamentos",
    "manufacturer_sku": "XUM-1000-20",
}


def test_extract_attributes_full_payload():
    attributes = OcapiConnector.extract_attributes(FULL_CV_PAYLOAD)
    assert attributes == {
        "activeIngredient": "PARACETAMOL",
        "dose": 582,
        "format": "20-unidades",
        "laboratory": "LABORATORIO CHILE",
        "isMedicine": True,
        "isBioequivalent": True,
        "bioequivalentGroup": "paracetamol-1000-mg",
        "prescription": "venta-directa",
        "category": "medicamentos",
        "manufacturerSku": "XUM-1000-20",
    }


def test_extract_attributes_empty_payload_does_not_raise():
    assert OcapiConnector.extract_attributes({}) == {}


def test_extract_attributes_skips_null_custom_fields():
    """OCAPI omits or nulls c_* fields for non-medicine SKUs."""
    raw = {"id": "1", "name": "Shampoo", "c_activeIngredient": None, "c_dose": None}
    assert OcapiConnector.extract_attributes(raw) == {}


def test_extract_attributes_keeps_false_flags():
    """`is not None` (not truthiness): 'explicitly not a medicine' must survive.

    Dropping c_isMedProduct=False would make a cosmetic indistinguishable from
    a product that simply never declared the flag.
    """
    attributes = OcapiConnector.extract_attributes(
        {"c_isMedProduct": False, "c_isBioequivalent": False}
    )
    assert attributes == {"isMedicine": False, "isBioequivalent": False}


def test_extract_attributes_ignores_blank_manufacturer_sku():
    assert OcapiConnector.extract_attributes({"manufacturer_sku": ""}) == {}
    assert OcapiConnector.extract_attributes({"manufacturer_sku": "MS-1"}) == {
        "manufacturerSku": "MS-1"
    }


def test_extract_attributes_groups_same_molecule_across_labs():
    """Two labs, two SKUs, no barcode — the bioequivalent group is the join key."""
    a = OcapiConnector.extract_attributes(
        {"c_activeIngredient": "PARACETAMOL", "c_dose": 1000,
         "c_bioequivalentSubCategoryID": "paracetamol-1000-mg", "c_laboratory": "LAB CHILE"}
    )
    b = OcapiConnector.extract_attributes(
        {"c_activeIngredient": "PARACETAMOL", "c_dose": 1000,
         "c_bioequivalentSubCategoryID": "paracetamol-1000-mg", "c_laboratory": "MINTLAB"}
    )
    assert a["bioequivalentGroup"] == b["bioequivalentGroup"]
    assert a["laboratory"] != b["laboratory"]


def test_parse_product_attaches_attributes(connector):
    product = connector.parse_product(FULL_CV_PAYLOAD)
    assert product.attributes["activeIngredient"] == "PARACETAMOL"
    assert product.attributes["dose"] == 582
    assert product.attributes["format"] == "20-unidades"
    assert product.attributes["isMedicine"] is True
    assert product.attributes["bioequivalentGroup"] == "paracetamol-1000-mg"


def test_parse_product_attributes_none_when_nothing_extracted(connector):
    """None, never {} — an empty dict reads as 'we looked and it has none'."""
    product = connector.parse_product({"id": "1", "name": "Med", "price": 100})
    assert product.attributes is None


# --- image selection -------------------------------------------------------
# `image_groups[0]` was taken blindly. SFCC also publishes `swatch` groups (the
# 30px colour chip of a variation attribute), so an ordering change upstream
# would have stored a colour square as the product photo.

def test_pick_image_prefers_large_over_swatch():
    groups = [
        {"view_type": "swatch", "images": [{"link": "https://img/swatch.png"}]},
        {"view_type": "large", "images": [{"link": "https://img/large.jpg"}]},
    ]
    assert OcapiConnector.pick_image(groups) == "https://img/large.jpg"


def test_pick_image_never_falls_back_to_a_swatch():
    groups = [{"view_type": "swatch", "images": [{"link": "https://img/swatch.png"}]}]
    assert OcapiConnector.pick_image(groups) is None


def test_pick_image_walks_resolution_preference():
    groups = [
        {"view_type": "small", "images": [{"link": "https://img/small.jpg"}]},
        {"view_type": "medium", "images": [{"link": "https://img/medium.jpg"}]},
    ]
    assert OcapiConnector.pick_image(groups) == "https://img/medium.jpg"


def test_pick_image_accepts_unknown_view_type():
    groups = [{"view_type": "pdp-main", "images": [{"link": "https://img/x.jpg"}]}]
    assert OcapiConnector.pick_image(groups) == "https://img/x.jpg"


def test_pick_image_skips_empty_groups():
    groups = [
        {"view_type": "large", "images": []},
        {"view_type": "medium", "images": [{"link": "https://img/m.jpg"}]},
    ]
    assert OcapiConnector.pick_image(groups) == "https://img/m.jpg"


def test_pick_image_falls_back_to_dis_base_link():
    groups = [{"view_type": "large", "images": [{"dis_base_link": "https://img/dis.jpg"}]}]
    assert OcapiConnector.pick_image(groups) == "https://img/dis.jpg"


def test_pick_image_handles_missing_groups():
    assert OcapiConnector.pick_image(None) is None
    assert OcapiConnector.pick_image([]) is None


def test_parse_product_picks_large_not_first_group(connector):
    raw = {
        "id": "1006", "name": "Med", "price": 1000,
        "inventory": {"orderable": True, "stock_level": 30},
        "image_groups": [
            {"view_type": "swatch", "images": [{"link": "https://img/swatch.png"}]},
            {"view_type": "large", "images": [{"link": "https://img/large.jpg"}]},
        ],
    }
    assert connector.parse_product(raw).image_url == "https://img/large.jpg"


def test_search_hit_image_falls_back_to_dis_base_link(connector):
    hit = {
        "product_id": "9", "product_name": "Med", "price": 100, "orderable": True,
        "image": {"dis_base_link": "https://img/dis.jpg"},
    }
    assert connector.parse_search_hit(hit).image_url == "https://img/dis.jpg"


def test_search_hit_without_image_is_none(connector):
    hit = {"product_id": "9", "product_name": "Med", "price": 100, "orderable": True}
    assert connector.parse_search_hit(hit).image_url is None


def test_fetch_by_skus_exists_for_targeted_backfill(connector):
    # backfill_images uses this to repair N specific products instead of
    # re-walking the ~10k sitemap. `sku` is the SFCC product id for this chain.
    assert hasattr(connector, "fetch_by_skus")
    assert connector.product_url("266145").startswith(
        "https://beta.cruzverde.cl/s/Chile/dw/shop/v19_1/products/266145"
    )
