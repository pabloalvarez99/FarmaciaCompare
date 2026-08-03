"""Tests for the tu-farmacia catalog importer.

Everything here is a pure function fed from a fake `pg_dump`; no database is
touched. `import_catalog` is deliberately untested — it needs a live session.
"""
import pytest

from src.tufarmacia_importer import (
    CatalogProduct,
    clean,
    extract_dosage,
    extract_form,
    load_catalog,
    normalize_name,
    parse_copy_block,
    split_ingredients,
)

# `\N` is how pg_dump writes NULL inside a COPY block.
NULL = "\\N"

PRODUCT_COLUMNS = [
    "id",
    "external_id",
    "name",
    "active_ingredient",
    "laboratory",
    "therapeutic_action",
    "prescription_type",
    "presentation",
    "active",
]

BARCODE_COLUMNS = ["id", "product_id", "barcode"]

# Values copied from the real dump.
ELITIRAN = [
    "1",
    "TF-0001",
    "ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML",
    "DICLOFENACO SODICO",
    "MINTLAB",
    "ANALGESICO",
    "direct",
    NULL,
    "f",  # inactive, but still a valid catalog entry
]

GLAUCOTENSIL = [
    "2",
    "TF-0002",
    "GLAUCOTENSIL T OFT 5ML",
    "DORZOLAMIDA  , TIMOLOL",
    "SAVAL",
    "OFTALMOLOGIA",
    "prescription",
    "MILILITROS",
    "t",
]


def build_copy_block(table: str, columns: list[str], rows: list[str]) -> str:
    header = f"COPY public.{table} ({', '.join(columns)}) FROM stdin;\n"
    return header + "".join(f"{row}\n" for row in rows) + "\\.\n"


def build_dump(product_rows: list[list[str]], barcode_rows: list[list[str]] | None = None) -> str:
    """A miniature but structurally faithful pg_dump."""
    parts = [
        "--\n-- PostgreSQL database dump\n--\n\n",
        "SET statement_timeout = 0;\n",
        "SET client_encoding = 'UTF8';\n\n",
        build_copy_block(
            "products", PRODUCT_COLUMNS, ["\t".join(r) for r in product_rows]
        ),
        "\n",
    ]
    if barcode_rows is not None:
        parts.append(
            build_copy_block(
                "product_barcodes", BARCODE_COLUMNS, ["\t".join(r) for r in barcode_rows]
            )
        )
    parts.append("\n--\n-- PostgreSQL database dump complete\n--\n")
    return "".join(parts)


def write_dump(tmp_path, product_rows, barcode_rows=None) -> str:
    path = tmp_path / "tufarmacia.sql"
    path.write_text(build_dump(product_rows, barcode_rows), encoding="utf-8")
    return str(path)


class TestParseCopyBlock:
    def test_returns_columns_and_rows(self):
        dump = build_copy_block("products", ["id", "name"], ["1\tFOO", "2\tBAR"])
        columns, rows = parse_copy_block(dump, "products")
        assert columns == ["id", "name"]
        assert rows == [["1", "FOO"], ["2", "BAR"]]

    def test_missing_table_returns_empty(self):
        dump = build_copy_block("products", ["id"], ["1"])
        assert parse_copy_block(dump, "product_barcodes") == ([], [])

    def test_picks_the_requested_table(self):
        dump = (
            build_copy_block("products", ["id", "name"], ["1\tFOO"])
            + "\n"
            + build_copy_block("product_barcodes", ["id", "barcode"], ["9\t7801"])
        )
        assert parse_copy_block(dump, "products") == (["id", "name"], [["1", "FOO"]])
        assert parse_copy_block(dump, "product_barcodes") == (
            ["id", "barcode"],
            [["9", "7801"]],
        )

    def test_column_list_is_stripped(self):
        dump = build_copy_block("products", ["id", "name", "active"], ["1\tFOO\tt"])
        columns, _ = parse_copy_block(dump, "products")
        assert columns == ["id", "name", "active"]

    def test_null_marker_is_left_raw(self):
        """parse_copy_block does not clean; that is `clean`'s job."""
        dump = build_copy_block("products", ["id", "presentation"], [f"1\t{NULL}"])
        _, rows = parse_copy_block(dump, "products")
        assert rows == [["1", NULL]]

    def test_blank_lines_are_skipped(self):
        dump = build_copy_block("products", ["id"], ["1", "", "2"])
        _, rows = parse_copy_block(dump, "products")
        assert rows == [["1"], ["2"]]

    def test_empty_block_returns_empty(self):
        dump = build_copy_block("products", ["id"], [])
        assert parse_copy_block(dump, "products") == ([], [])

    def test_stops_at_the_terminator(self):
        dump = (
            build_copy_block("products", ["id"], ["1", "2"])
            + "ALTER TABLE ONLY public.products ADD CONSTRAINT products_pkey PRIMARY KEY (id);\n"
        )
        _, rows = parse_copy_block(dump, "products")
        assert rows == [["1"], ["2"]]


class TestClean:
    def test_null_marker_becomes_none(self):
        assert clean(NULL) is None

    def test_none_stays_none(self):
        assert clean(None) is None

    def test_empty_string_becomes_none(self):
        assert clean("") is None

    def test_whitespace_only_becomes_none(self):
        assert clean("   ") is None

    def test_strips_surrounding_whitespace(self):
        assert clean("  MINTLAB  ") == "MINTLAB"

    def test_keeps_ordinary_value(self):
        assert clean("DICLOFENACO SODICO") == "DICLOFENACO SODICO"


class TestNormalizeName:
    def test_lowercases(self):
        assert normalize_name("PARACETAMOL") == "paracetamol"

    def test_strips_accents(self):
        assert normalize_name("ÁCIDO ACETILSALICÍLICO") == "acido acetilsalicilico"

    def test_strips_dieresis_and_tilde(self):
        assert normalize_name("Ungüento Niño") == "unguento nino"

    def test_collapses_punctuation_to_single_space(self):
        # "400mg" is split into "400 mg" so it keys the same as "400 MG".
        assert normalize_name("Ibuprofeno 400mg (Recubierto)") == "ibuprofeno 400 mg recubierto"

    def test_collapses_runs_of_separators(self):
        assert normalize_name("A -- / -- B") == "a b"

    def test_trims(self):
        assert normalize_name("  TAPSIN®  ") == "tapsin"

    def test_punctuation_only_becomes_empty(self):
        assert normalize_name("---") == ""

    def test_real_product_name(self):
        assert (
            normalize_name("ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML")
            == "elitiran susp p gotas orales 15 mg ml 25 ml"
        )

    def test_accented_and_punctuated_variants_converge(self):
        """The whole point of the key: both spellings must produce it exactly.

        Chains write dosages both ways ("400mg" and "400 MG"). If the two keys
        differed, a branded listing would never match its generic twin.
        """
        a = normalize_name("Ibuprofeno 400mg (Recubierto)")
        b = normalize_name("IBUPROFENO 400 MG RECUBIERTO")
        assert a == b == "ibuprofeno 400 mg recubierto"

    def test_chilean_decimal_comma_survives_as_one_number(self):
        """"0,05%" is a strength; "0 05" is two integers no parser can read.

        This was the bug: the key written to `medication_names` said
        "clobetasol 0 05", so the row declared no dose at all and could never
        agree on strength with a scraped "Clobetasol 0,05%" title.
        """
        assert normalize_name("CLOBETASOL 0,05% CREMA") == "clobetasol 0.05% crema"

    def test_decimal_point_survives_too(self):
        """The dump writes both separators; both mean the same number."""
        assert normalize_name("ACULAR SOL. OFT 0.5% 5 ML") == "acular sol oft 0.5% 5 ml"

    def test_both_decimal_separators_converge(self):
        assert normalize_name("VIGAMOX 0,5%") == normalize_name("VIGAMOX 0.5%")

    def test_percent_is_kept_attached_to_its_number(self):
        assert normalize_name("HIDROCORTISONA 1%") == "hidrocortisona 1%"

    def test_letters_are_split_off_after_a_percent(self):
        """"1%CR" has to yield a readable "1%": a unit glued to a letter is
        not recognised as a dose."""
        assert normalize_name("DERMAFUNG 1%CR.20GR.") == "dermafung 1% cr 20 gr"

    def test_combo_strength_keeps_its_slash(self):
        """"50/12,5" is one strength (losartán + hidroclorotiazida).

        Split into "50 12 5" the row reads as a 5 mg product — a different
        drug strength, which is the failure this key exists to prevent.
        """
        assert normalize_name("LOSART-HIDRO.50/12,5COM30") == "losart hidro 50/12.5 com30"

    def test_slash_between_words_is_still_a_separator(self):
        """Only a slash flanked by digits is part of a number.

        In "SUSP.P/GOTAS" the slash is punctuation, and keeping it would hide
        the form keyword "gotas" inside the token "p/gotas".
        """
        assert normalize_name("SUSP.P/GOTAS ORALES") == "susp p gotas orales"
        assert extract_form("ELITIRAN SUSP.P/GOTAS ORALES", None) == "Suspensión"

    def test_slash_between_a_unit_and_a_unit_is_still_a_separator(self):
        """"15MG/ML" has a letter before the slash, so nothing is preserved
        and the key stays as it was before decimals were kept."""
        assert (
            normalize_name("ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML")
            == "elitiran susp p gotas orales 15 mg ml 25 ml"
        )

    def test_a_lone_dot_is_still_a_separator(self):
        """Only a dot *between digits* is a decimal point."""
        assert normalize_name("BRIMONIDINA 0,2% SOL.OFT 5ML") == "brimonidina 0.2% sol oft 5 ml"


class TestExtractDosage:
    def test_mg_with_space(self):
        assert extract_dosage("PARACETAMOL 500 MG") == "500 mg"

    def test_mg_without_space(self):
        assert extract_dosage("PARACETAMOL 500MG") == "500 mg"

    def test_mcg(self):
        assert extract_dosage("LEVOTIROXINA 50 MCG") == "50 mcg"

    def test_grams(self):
        assert extract_dosage("AMOXICILINA 1 G") == "1 g"

    def test_millilitres(self):
        assert extract_dosage("GLAUCOTENSIL T OFT 5ML") == "5 ml"

    def test_international_units(self):
        assert extract_dosage("VITAMINA D 2000 UI") == "2000 ui"

    def test_compound_dosage(self):
        assert extract_dosage("AMOXICILINA 250 MG/5 ML") == "250 mg/5 ml"

    def test_compound_dosage_without_spaces(self):
        assert extract_dosage("AMOXICILINA 250MG/5ML") == "250 mg/5 ml"

    def test_chilean_decimal_comma(self):
        assert extract_dosage("BETAMETASONA 0,05 %") == "0,05 %"

    def test_decimal_point(self):
        assert extract_dosage("CLOTRIMAZOL CREMA 0.5%") == "0.5 %"

    def test_unit_is_lowercased(self):
        assert extract_dosage("IBUPROFENO 400 Mg") == "400 mg"

    def test_first_match_wins(self):
        assert extract_dosage("PACK 500 MG X 20 ML") == "500 mg"

    def test_no_dosage_returns_empty_string(self):
        assert extract_dosage("VITAMINA C") == ""

    def test_bare_number_is_not_a_dosage(self):
        assert extract_dosage("PRODUCTO 12345") == ""

    def test_empty_name_returns_empty_string(self):
        assert extract_dosage("") == ""

    def test_denominator_without_digits_is_kept(self):
        """`15MG/ML` is a concentration and must survive as one.

        Dropping the "/ml" would turn it into an absolute 15 mg dose — a
        different drug strength, and a silently wrong matching key.
        """
        assert extract_dosage("ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML") == "15 mg/ml"


class TestExtractForm:
    def test_keyword_in_name(self):
        assert extract_form("IBUPROFENO 400 MG COMPRIMIDOS", None) == "Comprimido"

    def test_abbreviation_in_name(self):
        assert extract_form("TAPSIN 500MG C/20 COMP", None) == "Comprimido"

    def test_accents_do_not_defeat_matching(self):
        assert extract_form("IBUPROFENO CÁPSULAS BLANDAS", None) == "Cápsula"

    def test_accented_unguento(self):
        assert extract_form("HIDROCORTISONA UNGÜENTO 1%", None) == "Ungüento"

    def test_punctuation_does_not_defeat_matching(self):
        assert extract_form("ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML", None) == "Suspensión"

    def test_keyword_wins_over_presentation(self):
        assert extract_form("GLAUCOTENSIL T OFT 5ML", "MILILITROS") == "Solución oftálmica"

    def test_keyword_can_come_from_presentation(self):
        assert extract_form("HIDROCORTISONA 1%", "CREMA DERMICA") == "Crema"

    def test_falls_back_to_presentation(self):
        assert extract_form("VITAMINA X", "CAJA") == "CAJA"

    def test_falls_back_to_empty_when_presentation_is_none(self):
        assert extract_form("VITAMINA X", None) == ""

    def test_falls_back_to_empty_when_presentation_is_blank(self):
        assert extract_form("VITAMINA X", "") == ""

    def test_inyectable(self):
        assert extract_form("CEFTRIAXONA 1 G INYECTABLE", None) == "Inyectable"


class TestSplitIngredients:
    def test_real_comma_separated_value(self):
        assert split_ingredients("DORZOLAMIDA  , TIMOLOL") == ["DORZOLAMIDA", "TIMOLOL"]

    def test_single_ingredient_is_kept_whole(self):
        assert split_ingredients("DICLOFENACO SODICO") == ["DICLOFENACO SODICO"]

    def test_splits_on_plus(self):
        assert split_ingredients("AMOXICILINA + ACIDO CLAVULANICO") == [
            "AMOXICILINA",
            "ACIDO CLAVULANICO",
        ]

    def test_splits_on_slash(self):
        assert split_ingredients("LOSARTAN/HIDROCLOROTIAZIDA") == [
            "LOSARTAN",
            "HIDROCLOROTIAZIDA",
        ]

    def test_splits_on_the_word_y(self):
        assert split_ingredients("PARACETAMOL Y CODEINA") == ["PARACETAMOL", "CODEINA"]

    def test_word_y_is_case_insensitive(self):
        assert split_ingredients("HIDROCLOROTIAZIDA y LOSARTAN") == [
            "HIDROCLOROTIAZIDA",
            "LOSARTAN",
        ]

    def test_mixed_separators(self):
        assert split_ingredients("A, B + C / D Y E") == ["A", "B", "C", "D", "E"]

    def test_none_returns_empty_list(self):
        assert split_ingredients(None) == []

    def test_empty_string_returns_empty_list(self):
        assert split_ingredients("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert split_ingredients("   ") == []

    def test_separators_only_returns_empty_list(self):
        assert split_ingredients(", + /") == []


class TestLoadCatalog:
    def test_parses_products(self, tmp_path):
        path = write_dump(tmp_path, [ELITIRAN, GLAUCOTENSIL])
        products = load_catalog(path)
        assert [p.name for p in products] == [
            "ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML",
            "GLAUCOTENSIL T OFT 5ML",
        ]
        assert all(isinstance(p, CatalogProduct) for p in products)

    def test_maps_every_field(self, tmp_path):
        path = write_dump(tmp_path, [ELITIRAN])
        product = load_catalog(path)[0]
        assert product.external_id == "TF-0001"
        assert product.name == "ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML"
        assert product.active_ingredient == "DICLOFENACO SODICO"
        assert product.laboratory == "MINTLAB"
        assert product.therapeutic_action == "ANALGESICO"
        assert product.prescription_required is False
        assert product.presentation is None  # `\N` in the dump
        assert product.barcodes == []

    def test_prescription_type_other_than_direct_requires_a_prescription(self, tmp_path):
        path = write_dump(tmp_path, [GLAUCOTENSIL])
        product = load_catalog(path)[0]
        assert product.prescription_required is True
        assert product.presentation == "MILILITROS"

    def test_null_prescription_type_defaults_to_direct(self, tmp_path):
        row = list(ELITIRAN)
        row[PRODUCT_COLUMNS.index("prescription_type")] = NULL
        path = write_dump(tmp_path, [row])
        assert load_catalog(path)[0].prescription_required is False

    def test_null_external_id_falls_back_to_the_row_id(self, tmp_path):
        row = list(ELITIRAN)
        row[PRODUCT_COLUMNS.index("external_id")] = NULL
        path = write_dump(tmp_path, [row])
        assert load_catalog(path)[0].external_id == "1"

    def test_inactive_products_are_kept(self, tmp_path):
        """32.616 of 34.166 real rows are inactive; filtering them would drop
        95% of the catalog. `active` must never become a filter."""
        inactive = list(ELITIRAN)
        inactive[PRODUCT_COLUMNS.index("active")] = "f"
        active = list(GLAUCOTENSIL)
        active[PRODUCT_COLUMNS.index("active")] = "t"

        products = load_catalog(write_dump(tmp_path, [inactive, active]))

        assert len(products) == 2
        assert "ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML" in {p.name for p in products}

    def test_rows_with_too_few_fields_are_skipped(self, tmp_path):
        short = ["3", "TF-0003", "TRUNCADO"]
        products = load_catalog(write_dump(tmp_path, [ELITIRAN, short]))
        assert [p.external_id for p in products] == ["TF-0001"]

    def test_rows_with_a_blank_name_are_skipped(self, tmp_path):
        blank = list(GLAUCOTENSIL)
        blank[PRODUCT_COLUMNS.index("name")] = "   "
        null_name = list(GLAUCOTENSIL)
        null_name[PRODUCT_COLUMNS.index("id")] = "3"
        null_name[PRODUCT_COLUMNS.index("name")] = NULL

        products = load_catalog(write_dump(tmp_path, [ELITIRAN, blank, null_name]))
        assert [p.external_id for p in products] == ["TF-0001"]

    def test_barcodes_are_attached_to_the_right_product(self, tmp_path):
        barcodes = [
            ["10", "1", "7801234567890"],
            ["11", "2", "7805555555555"],
            ["12", "1", "7809999999999"],
        ]
        products = {p.name: p for p in load_catalog(write_dump(tmp_path, [ELITIRAN, GLAUCOTENSIL], barcodes))}
        assert products["ELITIRAN SUSP.P/GOTAS ORALES 15MG/ML.25ML"].barcodes == [
            "7801234567890",
            "7809999999999",
        ]
        assert products["GLAUCOTENSIL T OFT 5ML"].barcodes == ["7805555555555"]

    def test_duplicate_barcodes_are_deduped(self, tmp_path):
        barcodes = [
            ["10", "1", "7801234567890"],
            ["11", "1", "7801234567890"],
            ["12", "1", "  7801234567890  "],
        ]
        product = load_catalog(write_dump(tmp_path, [ELITIRAN], barcodes))[0]
        assert product.barcodes == ["7801234567890"]

    def test_barcodes_for_unknown_products_are_ignored(self, tmp_path):
        barcodes = [["10", "999", "7801234567890"]]
        product = load_catalog(write_dump(tmp_path, [ELITIRAN], barcodes))[0]
        assert product.barcodes == []

    def test_null_and_short_barcode_rows_are_ignored(self, tmp_path):
        barcodes = [
            ["10", "1", NULL],
            ["11", "1"],
            ["12", "1", "7801234567890"],
        ]
        product = load_catalog(write_dump(tmp_path, [ELITIRAN], barcodes))[0]
        assert product.barcodes == ["7801234567890"]

    def test_missing_barcode_block_leaves_products_intact(self, tmp_path):
        products = load_catalog(write_dump(tmp_path, [ELITIRAN, GLAUCOTENSIL]))
        assert len(products) == 2
        assert all(p.barcodes == [] for p in products)

    def test_missing_products_block_aborts(self, tmp_path):
        path = tmp_path / "wrong.sql"
        path.write_text(
            build_copy_block("clients", ["id", "name"], ["1\tACME"]), encoding="utf-8"
        )
        with pytest.raises(SystemExit):
            load_catalog(str(path))
