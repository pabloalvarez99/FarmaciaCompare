import pytest
from src.connectors.vtex_connector import VTEX_CONFIGS, VtexConfig, VtexConnector


class TestVtexConnector:
    @pytest.fixture
    def config(self):
        return VTEX_CONFIGS["dr_simi"]

    @pytest.fixture
    def connector(self, config):
        return VtexConnector(config)

    def test_registry_only_holds_live_vtex_stores(self):
        # Cruz Verde, Salcobrand and Ahumada left VTEX; their accounts 404 now.
        assert set(VTEX_CONFIGS) == {"dr_simi"}

    def test_builds_search_url_on_store_domain(self, connector):
        url = connector.build_search_url(page=1, page_size=50)
        assert url.startswith("https://www.drsimi.cl/api/catalog_system/pub/products/search")
        assert "_from=0" in url
        assert "_to=49" in url
        assert "vtexcommercestable" not in url

    def test_builds_search_url_on_vtex_host_when_configured(self):
        config = VtexConfig(
            chain="dr_simi",
            account_name="farmaciasdeldrsimicl",
            base_url="https://www.drsimi.cl",
            use_store_domain=False,
        )
        url = VtexConnector(config).build_search_url(page=2, page_size=50)
        assert url.startswith("https://farmaciasdeldrsimicl.vtexcommercestable.com.br/")
        assert "_from=50" in url

    def test_parse_product_valid(self, connector):
        raw = {
            "productId": "12345",
            "productName": "Paracetamol 500mg x20 Comprimidos",
            "brand": "Dr. Simi",
            "linkText": "paracetamol-500mg",
            "items": [{
                "itemId": "12345-001",
                "ean": "7891234567890",
                "images": [{"imageUrl": "https://img/1.jpg"}],
                "sellers": [{
                    "commertialOffer": {"Price": 2990, "ListPrice": 3490, "AvailableQuantity": 50}
                }],
            }],
        }
        products = connector.parse_product(raw)
        assert len(products) == 1
        p = products[0]
        assert p.price == 2990
        assert p.original_price == 3490
        assert p.discount_pct == 14
        assert p.stock_status == "in_stock"
        assert p.sku == "12345-001"
        assert p.url == "https://www.drsimi.cl/paracetamol-500mg/p"
        assert p.image_url == "https://img/1.jpg"

    def test_parse_product_out_of_stock(self, connector):
        raw = {
            "productId": "99999",
            "productName": "Test Med",
            "brand": None,
            "items": [{
                "itemId": "99999-001",
                "ean": None,
                "sellers": [{"commertialOffer": {"Price": 0, "ListPrice": 1000, "AvailableQuantity": 0}}],
            }],
        }
        assert connector.parse_product(raw)[0].stock_status == "out_of_stock"

    def test_parse_product_low_stock(self, connector):
        raw = {
            "productId": "1",
            "productName": "Test Med",
            "brand": None,
            "items": [{
                "itemId": "1-1",
                "sellers": [{"commertialOffer": {"Price": 500, "ListPrice": 500, "AvailableQuantity": 2}}],
            }],
        }
        product = connector.parse_product(raw)[0]
        assert product.stock_status == "low_stock"
        assert product.original_price is None

    def test_parse_product_missing_items_skipped(self, connector):
        raw = {"productId": "X", "productName": "Empty", "brand": None, "items": []}
        assert connector.parse_product(raw) == []

    def test_parse_product_without_sellers_skipped(self, connector):
        raw = {"productId": "X", "productName": "No seller", "items": [{"itemId": "X-1", "sellers": []}]}
        assert connector.parse_product(raw) == []


class TestVtexExtractAttributes:
    """Dr. Simi's VTEX returns an empty `ean`, so the reference code and the
    category tree are the only identity signals available for this chain."""

    @pytest.fixture
    def connector(self):
        return VtexConnector(VTEX_CONFIGS["dr_simi"])

    def test_full_payload(self):
        raw = {
            "productName": "Paracetamol 500mg x20 Comprimidos",
            "categories": ["/Medicamentos/Analgesicos/", "/Medicamentos/"],
            "productReference": "PR-0001",
        }
        item = {"referenceId": [{"Key": "RefId", "Value": "DS-77821"}]}
        assert VtexConnector.extract_attributes(raw, item) == {
            "referenceCode": "DS-77821",
            "category": "Medicamentos > Analgesicos",
            "isMedicine": True,
        }

    def test_empty_payload_does_not_raise(self):
        assert VtexConnector.extract_attributes({}, {}) == {}

    def test_missing_reference_and_category_keys_do_not_raise(self):
        assert VtexConnector.extract_attributes(
            {"categories": None, "productReference": None}, {"referenceId": None}
        ) == {}

    def test_reference_id_wins_over_product_reference(self):
        """setdefault: the item-level RefId is the more specific identifier."""
        attributes = VtexConnector.extract_attributes(
            {"productReference": "PR-0001"},
            {"referenceId": [{"Key": "RefId", "Value": "DS-77821"}]},
        )
        assert attributes["referenceCode"] == "DS-77821"

    def test_falls_back_to_product_reference_without_ref_id(self):
        attributes = VtexConnector.extract_attributes(
            {"productReference": "PR-0001"},
            {"referenceId": [{"Key": "MPN", "Value": "ignored"}]},
        )
        assert attributes["referenceCode"] == "PR-0001"

    def test_blank_ref_id_value_falls_back_to_product_reference(self):
        attributes = VtexConnector.extract_attributes(
            {"productReference": "PR-0001"},
            {"referenceId": [{"Key": "RefId", "Value": ""}]},
        )
        assert attributes["referenceCode"] == "PR-0001"

    def test_no_reference_anywhere_leaves_key_unset(self):
        assert "referenceCode" not in VtexConnector.extract_attributes(
            {"categories": ["/Medicamentos/"]}, {"referenceId": []}
        )

    def test_first_category_is_the_deepest_path(self):
        """VTEX lists the leaf path first; keep it, not the root."""
        attributes = VtexConnector.extract_attributes(
            {"categories": ["/Medicamentos/Dolor/Analgesicos/", "/Medicamentos/Dolor/", "/Medicamentos/"]},
            {},
        )
        assert attributes["category"] == "Medicamentos > Dolor > Analgesicos"

    def test_is_medicine_false_for_non_medicine_tree(self):
        attributes = VtexConnector.extract_attributes(
            {"categories": ["/Belleza/Cuidado Facial/"]}, {}
        )
        assert attributes["isMedicine"] is False

    def test_is_medicine_matches_case_insensitively_at_any_depth(self):
        attributes = VtexConnector.extract_attributes(
            {"categories": ["/Salud/MEDICAMENTOS Populares/"]}, {}
        )
        assert attributes["isMedicine"] is True

    def test_parse_product_attaches_attributes_to_every_variant(self, connector):
        raw = {
            "productName": "Paracetamol 500mg",
            "linkText": "paracetamol-500mg",
            "categories": ["/Medicamentos/Analgesicos/"],
            "productReference": "PR-0001",
            "items": [
                {
                    "itemId": "1-1",
                    "ean": "",
                    "referenceId": [{"Key": "RefId", "Value": "DS-1"}],
                    "sellers": [{"commertialOffer": {"Price": 990, "ListPrice": 990, "AvailableQuantity": 20}}],
                },
                {
                    "itemId": "1-2",
                    "ean": "",
                    "referenceId": [{"Key": "RefId", "Value": "DS-2"}],
                    "sellers": [{"commertialOffer": {"Price": 1890, "ListPrice": 1890, "AvailableQuantity": 20}}],
                },
            ],
        }
        products = connector.parse_product(raw)
        assert [p.attributes["referenceCode"] for p in products] == ["DS-1", "DS-2"]
        # Every variant still gets the shared product-level category.
        assert all(p.attributes["category"] == "Medicamentos > Analgesicos" for p in products)
        assert all(p.attributes["isMedicine"] is True for p in products)

    def test_parse_product_attributes_none_when_nothing_extracted(self, connector):
        """None, never {} — an empty dict reads as 'we looked and it has none'."""
        raw = {
            "productName": "Med",
            "items": [{
                "itemId": "1-1",
                "sellers": [{"commertialOffer": {"Price": 100, "ListPrice": 100, "AvailableQuantity": 9}}],
            }],
        }
        assert connector.parse_product(raw)[0].attributes is None


class TestVtexImageSizing:
    """`images[0].imageUrl` points at the original upload (~65 KB, >1000 px).

    A `-<w>-<h>` suffix on the VTEX file id makes the CDN render a smaller copy
    (verified live: 200 image/jpeg, ~15-20 KB), which is what a 40px table
    thumbnail actually needs.
    """

    @pytest.fixture
    def connector(self):
        return VtexConnector(VTEX_CONFIGS["dr_simi"])

    def test_adds_size_suffix_to_vtex_file_id(self, connector):
        item = {"images": [{
            "imageUrl": "https://farmaciasdeldrsimicl.vteximg.com.br/arquivos/ids/160249/BE0089-1.jpg?v=639"
        }]}
        assert connector.pick_image(item) == (
            "https://farmaciasdeldrsimicl.vteximg.com.br/arquivos/ids/160249-500-500/BE0089-1.jpg?v=639"
        )

    def test_does_not_double_suffix_an_already_sized_url(self, connector):
        url = "https://farmaciasdeldrsimicl.vteximg.com.br/arquivos/ids/160249-800-800/x.jpg"
        assert connector.pick_image({"images": [{"imageUrl": url}]}) == url

    def test_leaves_non_vtex_urls_untouched(self, connector):
        url = "https://cdn.example.com/photo.jpg"
        assert connector.pick_image({"images": [{"imageUrl": url}]}) == url

    def test_skips_entries_without_a_url(self, connector):
        item = {"images": [{"imageId": "1"}, {"imageUrl": "https://cdn/a.jpg"}]}
        assert connector.pick_image(item) == "https://cdn/a.jpg"

    def test_no_images_is_none(self, connector):
        assert connector.pick_image({}) is None
        assert connector.pick_image({"images": []}) is None


class TestVtexUrlEncoding:
    """Dr. Simi uploads filenames with spaces; VTEX returns them raw.

    Raw spaces make the URL unusable server-side (curl 000, urllib rejects it as
    a control character); `%20` returns 200 image/jpeg.
    """

    @pytest.fixture
    def connector(self):
        return VtexConnector(VTEX_CONFIGS["dr_simi"])

    def test_spaces_in_filename_are_encoded(self, connector):
        item = {"images": [{
            "imageUrl": "https://x.vteximg.com.br/arquivos/ids/160019/Mupirocina - 613-1.jpg?v=638"
        }]}
        assert connector.pick_image(item) == (
            "https://x.vteximg.com.br/arquivos/ids/160019-500-500/Mupirocina%20-%20613-1.jpg?v=638"
        )

    def test_already_encoded_url_is_not_double_encoded(self, connector):
        url = "https://x.vteximg.com.br/arquivos/ids/1-500-500/a%20b.jpg?v=1"
        assert connector.pick_image({"images": [{"imageUrl": url}]}) == url

    def test_query_string_is_left_alone(self, connector):
        url = "https://x.vteximg.com.br/arquivos/ids/1-500-500/a.jpg?v=1&w=2"
        assert connector.pick_image({"images": [{"imageUrl": url}]}) == url

    def test_surrounding_whitespace_is_stripped(self, connector):
        item = {"images": [{"imageUrl": "  https://cdn/a.jpg  "}]}
        assert connector.pick_image(item) == "https://cdn/a.jpg"

    def test_blank_url_is_skipped(self, connector):
        item = {"images": [{"imageUrl": "   "}, {"imageUrl": "https://cdn/b.jpg"}]}
        assert connector.pick_image(item) == "https://cdn/b.jpg"
