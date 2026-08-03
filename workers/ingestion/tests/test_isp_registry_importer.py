"""Tests for the ISP sanitary registry importer.

Every fixture is markup captured from the real "Exportar a Excel" response of
https://registrosanitario.ispch.gob.cl/ — same tags, same `<span id="lbl…">`
wrappers, same cp1252 bytes. Nothing here touches the network or the database;
`import_registry` is left untested because it needs a live session, exactly as
`test_tufarmacia_importer.py` leaves `import_catalog` alone.
"""
import pytest

from src.isp_registry_importer import (
    ESTADO_VIGENTE,
    ISPProduct,
    PHARMA_PREFIXES,
    _ca_issuer_url,
    _cell_text,
    generic_aliases,
    load_otc_registrations,
    parse_registry,
    requires_prescription,
    select_pharmaceuticals,
)

HEADER = (
    "<tr>\r\n\t\t"
    '<th scope="col">&nbsp;</th><th scope="col">Registro</th>'
    '<th scope="col">Nombre</th><th scope="col">Fecha Registro</th>'
    '<th scope="col">Empresa</th><th scope="col">Principio Activo</th>'
    '<th scope="col">Control Legal</th>\r\n\t</tr>'
)


def row(registration, name, date, company, ingredient, legal=""):
    """Rebuild one export row with the wrappers the real page emits."""
    return (
        "<tr>\r\n\t\t<td>\r\n     \r\n    </td>"
        f'<td>\r\n  <span id="lblProducto">{registration}</span>\r\n  </td>'
        f'<td>\r\n  <span id="lblNombre">\r\n\r\n{name}\r\n\r\n</span>\r\n  </td>'
        f'<td>\r\n  <span id="lblFechaRegistro">{date}</span>\r\n  </td>'
        f'<td>\r\n  <span id="lblTitular">{company}</span>\r\n  </td>'
        f'<td>\r\n  <span id="lblPA">{ingredient}</span>\r\n  </td>'
        f'<td>\r\n  <span id="lblLegal">{legal}</span>\r\n  </td>\r\n\t</tr>'
    )


# Rows copied from the live export, values unchanged.
GALVUS = row(
    "F-27368/23",
    "GALVUS COMPRIMIDOS 50 mg (Vildagliptina)",
    "2023-03-14",
    "NOVARTIS CHILE S.A.",
    "VILDAGLIPTINA",
)
GALVUS_OLD = row(
    "F-21478/24",
    "GALVUS COMPRIMIDOS 50 MG (VILDAGLIPTINA)",
    "2014-05-02",
    "NOVARTIS CHILE S.A.",
    "VILDAGLIPTINA",
)
GALVUS_MET = row(
    "F-25267/25",
    "GALVUS MET 50/1000 COMPRIMIDOS RECUBIERTOS",
    "2025-01-09",
    "NOVARTIS CHILE S.A.",
    "METFORMINA//VILDAGLIPTINA",
)
VIRGAN = row(
    "F-19120/21",
    "VIRGAN GEL OFT&#193;LMICO 1,5 mg/g",
    "2021-06-11",
    "LABORATORIO SOPHIA CHILE LTDA.",
    "GANCICLOVIR",
)
BUXON = row(
    "F-26326/21",
    "BUXON COMPRIMIDOS DE LIBERACI&#211;N PROLONGADA 150 mg",
    "2021-08-30",
    "LABORATORIOS SAVAL S.A.",
    "ANFEBUTAMONA CLORHIDRATO (BUPROPI&#211;N)",
)
SUERO = row(
    "F-27355/23",
    "CLORURO DE SODIO SOLUCI&#211;N INYECTABLE 0,9%",
    "2023-02-27",
    "FRESENIUS KABI CHILE LTDA.",
    "CLORURO DE SODIO (*)",
)
HOMEOPATICO = row(
    "H-894/25",
    "HEEL COMPUESTO SOLUCI&#211;N ORAL",
    "2025-02-10",
    "KNOP LABORATORIOS S.A.",
    "Alfalfa T.M.;Oleum Jecor D3",
)
PASTA_DENTAL = row(
    "102C-513/21",
    "PASTA DENTAL PEPSODENT TRIPLE.  ANTIBACTERIAL",
    "2021-09-26",
    "UNILEVER CHILE LIMITADA",
    "",
)
LIMPIAPISOS = row(
    "D-1372/21",
    "EXCELL LIMPIAPISOS DESINFECTANTE CITRICO FRUTAL SOLUCION 0,05%",
    "2021-10-19",
    "INDUSTRIAL Y COMERCIAL BRILLEX S.A.",
    "Cloruro De Benzalconio 50%",
)

ALL_ROWS = [
    GALVUS,
    GALVUS_OLD,
    GALVUS_MET,
    VIRGAN,
    BUXON,
    SUERO,
    HOMEOPATICO,
    PASTA_DENTAL,
    LIMPIAPISOS,
]


def write_export(tmp_path, rows, name="export.xls"):
    """The real response is cp1252 with a `.xls` name and HTML inside."""
    path = tmp_path / name
    body = '<table border="0">\r\n' + HEADER + "".join(rows) + "\r\n</table>"
    path.write_bytes(body.encode("cp1252"))
    return path


def product(**overrides):
    base = dict(
        registration="F-27368/23",
        name="GALVUS COMPRIMIDOS 50 mg (Vildagliptina)",
        registered_on="2023-03-14",
        company="NOVARTIS CHILE S.A.",
        active_ingredient="VILDAGLIPTINA",
    )
    base.update(overrides)
    return ISPProduct(**base)


# --------------------------------------------------------------------------
# Cell extraction
# --------------------------------------------------------------------------


def test_cell_text_unwraps_span_and_collapses_whitespace():
    cell = '\r\n  <span id="lblNombre">\r\n\r\nGALVUS  COMPRIMIDOS\r\n\r\n</span>\r\n  '
    assert _cell_text(cell) == "GALVUS COMPRIMIDOS"


def test_cell_text_unescapes_entities():
    assert _cell_text('<span id="lblNombre">SOLUCI&#211;N OFT&#193;LMICA</span>') == (
        "SOLUCIÓN OFTÁLMICA"
    )


def test_cell_text_of_empty_cell_is_empty():
    assert _cell_text('<span id="lblPA"></span>') == ""


# --------------------------------------------------------------------------
# parse_registry
# --------------------------------------------------------------------------


def test_parse_registry_reads_every_row(tmp_path):
    products = parse_registry(write_export(tmp_path, ALL_ROWS))
    assert len(products) == len(ALL_ROWS)


def test_parse_registry_maps_columns_by_header_name(tmp_path):
    products = parse_registry(write_export(tmp_path, [VIRGAN]))
    virgan = products[0]
    assert virgan.registration == "F-19120/21"
    assert virgan.name == "VIRGAN GEL OFTÁLMICO 1,5 mg/g"
    assert virgan.registered_on == "2021-06-11"
    assert virgan.company == "LABORATORIO SOPHIA CHILE LTDA."
    assert virgan.active_ingredient == "GANCICLOVIR"


def test_parse_registry_uppercases_registration(tmp_path):
    row_lower = row("f-100/20", "TEST COMPRIMIDOS 10 mg", "2020-01-01", "LAB", "TEST")
    assert parse_registry(write_export(tmp_path, [row_lower]))[0].registration == "F-100/20"


def test_parse_registry_leaves_missing_ingredient_as_none(tmp_path):
    assert parse_registry(write_export(tmp_path, [PASTA_DENTAL]))[0].active_ingredient is None


def test_parse_registry_skips_rows_with_a_malformed_registration(tmp_path):
    junk = row("Total: 46.434", "resumen", "", "", "")
    products = parse_registry(write_export(tmp_path, [GALVUS, junk]))
    assert [p.registration for p in products] == ["F-27368/23"]


def test_parse_registry_rejects_a_file_with_no_rows(tmp_path):
    path = tmp_path / "empty.xls"
    path.write_bytes(b"<html>sin tabla</html>")
    with pytest.raises(SystemExit):
        parse_registry(path)


def test_parse_registry_rejects_a_header_without_registro(tmp_path):
    path = tmp_path / "wrong.xls"
    path.write_bytes(
        b'<table><tr><th>Otra</th><th>Cosa</th></tr><tr><td>a</td><td>b</td></tr></table>'
    )
    with pytest.raises(SystemExit):
        parse_registry(path)


# --------------------------------------------------------------------------
# Registration prefixes
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "registration,prefix",
    [
        ("F-27368/23", "F"),
        ("B-3036/24", "B"),
        ("FX-347/25", "FX"),
        ("102C-513/21", "102C"),
        ("D-1372/21", "D"),
    ],
)
def test_prefix_is_the_text_before_the_dash(registration, prefix):
    assert product(registration=registration).prefix == prefix


@pytest.mark.parametrize("prefix", sorted(PHARMA_PREFIXES))
def test_pharmaceutical_prefixes_are_medicines(prefix):
    assert product(registration=f"{prefix}-1/20").is_pharmaceutical


@pytest.mark.parametrize("registration", ["102C-513/21", "D-1372/21", "S-31/24", "P-608/21"])
def test_non_medicine_families_are_not_pharmaceutical(registration):
    assert not product(registration=registration).is_pharmaceutical


# --------------------------------------------------------------------------
# Ingredients
# --------------------------------------------------------------------------


def test_single_ingredient_is_read_as_is():
    assert product(active_ingredient="VILDAGLIPTINA").ingredients == ["VILDAGLIPTINA"]


def test_double_slash_separates_combination_products():
    combo = product(active_ingredient="METFORMINA//VILDAGLIPTINA")
    assert combo.ingredients == ["METFORMINA", "VILDAGLIPTINA"]


def test_semicolon_separates_ingredients_too():
    """Trailing punctuation goes with it — "T.M." and "T.M" are one substance."""
    herbal = product(active_ingredient="Alfalfa T.M.;Oleum Jecor D3")
    assert herbal.ingredients == ["ALFALFA T.M", "OLEUM JECOR D3"]


def test_ingredients_are_uppercased_so_the_unique_index_does_not_split_them():
    assert product(active_ingredient="Aconitum D6").ingredients == ["ACONITUM D6"]


def test_asterisk_marker_is_not_part_of_the_substance_name():
    assert product(active_ingredient="CLORURO DE SODIO (*)").ingredients == ["CLORURO DE SODIO"]


def test_nuevo_marker_is_dropped():
    assert product(active_ingredient="AL-NOTA-OCTREOTIDE - (NUEVO)").ingredients == [
        "AL-NOTA-OCTREOTIDE"
    ]


def test_parenthetical_synonym_is_separated_from_the_substance():
    buxon = product(active_ingredient="ANFEBUTAMONA CLORHIDRATO (BUPROPIÓN)")
    assert buxon.ingredients == ["ANFEBUTAMONA CLORHIDRATO"]
    assert buxon.ingredient_synonyms == ["BUPROPIÓN"]


def test_a_synonym_equal_to_a_substance_is_not_repeated():
    same = product(active_ingredient="PARACETAMOL (PARACETAMOL)")
    assert same.ingredients == ["PARACETAMOL"]
    assert same.ingredient_synonyms == []


def test_missing_ingredient_yields_no_names():
    assert product(active_ingredient=None).ingredients == []
    assert product(active_ingredient="").ingredients == []


# --------------------------------------------------------------------------
# select_pharmaceuticals
# --------------------------------------------------------------------------


def test_select_drops_cosmetics_and_disinfectants(tmp_path):
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, ALL_ROWS)))
    assert all(p.is_pharmaceutical for p in selected)
    assert "102C-513/21" not in {p.registration for p in selected}
    assert "D-1372/21" not in {p.registration for p in selected}


def test_select_collapses_renewals_of_the_same_product(tmp_path):
    """The ISP issues a new number on renewal; both rows are the same drug."""
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, [GALVUS, GALVUS_OLD])))
    assert len(selected) == 1


def test_select_keeps_the_most_recent_registration_of_a_duplicate(tmp_path):
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, [GALVUS_OLD, GALVUS])))
    assert selected[0].registration == "F-27368/23"


def test_select_prefers_the_row_that_has_an_active_ingredient(tmp_path):
    """An ingredient outranks recency — it is what produces the generic alias."""
    blank = row("F-99999/26", "GALVUS COMPRIMIDOS 50 mg (Vildagliptina)", "2026-01-01", "LAB", "")
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, [GALVUS, blank])))
    assert selected[0].registration == "F-27368/23"


def test_select_treats_case_differences_as_the_same_product(tmp_path):
    """"50 mg" and "50 MG" are one drug; only normalized names decide."""
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, [GALVUS, GALVUS_OLD])))
    assert len(selected) == 1


def test_select_keeps_genuinely_different_products(tmp_path):
    selected = select_pharmaceuticals(parse_registry(write_export(tmp_path, [GALVUS, GALVUS_MET])))
    assert len(selected) == 2


# --------------------------------------------------------------------------
# Generic aliases
# --------------------------------------------------------------------------


def test_generic_alias_pairs_the_substance_with_the_dose():
    display, normalized = generic_aliases(product(), "50 mg")[0]
    assert display == "VILDAGLIPTINA 50 mg"
    assert normalized == "vildagliptina 50 mg"


def test_generic_alias_uses_the_first_substance_of_a_combination():
    combo = product(active_ingredient="METFORMINA//VILDAGLIPTINA")
    assert [a for _, a in generic_aliases(combo, "50 mg")] == ["metformina 50 mg"]


def test_every_synonym_earns_its_own_alias():
    """A chain listing "Bupropión 150mg" must reach the same medication."""
    buxon = product(active_ingredient="ANFEBUTAMONA CLORHIDRATO (BUPROPIÓN)")
    assert [a for _, a in generic_aliases(buxon, "150 mg")] == [
        "anfebutamona clorhidrato 150 mg",
        "bupropion 150 mg",
    ]


def test_alias_equal_to_the_commercial_name_is_skipped():
    """The (medication_id, normalized_name) unique index would reject it."""
    plain = product(name="VILDAGLIPTINA 50 mg", active_ingredient="VILDAGLIPTINA")
    assert generic_aliases(plain, "50 mg", skip="vildagliptina 50 mg") == []


def test_alias_without_a_dose_is_still_the_substance_name():
    assert generic_aliases(product(), "")[0][1] == "vildagliptina"


def test_no_ingredient_means_no_alias():
    assert generic_aliases(product(active_ingredient=None), "50 mg") == []


# --------------------------------------------------------------------------
# Prescription flag
# --------------------------------------------------------------------------


def test_direct_sale_registration_needs_no_prescription():
    assert not requires_prescription(product(registration="B-1000/10"), {"B-1000/10"})


def test_pharmaceutical_registration_defaults_to_prescription_only():
    """Safe direction: warn wrongly on an OTC painkiller, never miss on an antibiotic."""
    assert requires_prescription(product(registration="F-27368/23"), set())


@pytest.mark.parametrize("registration", ["N-56/21", "H-894/25", "K-63/24", "E-5/25"])
def test_herbal_and_homeopathic_families_are_over_the_counter(registration):
    assert not requires_prescription(product(registration=registration), set())


# --------------------------------------------------------------------------
# OTC list
# --------------------------------------------------------------------------


def test_load_otc_registrations_reads_the_datos_gob_csv(tmp_path):
    path = tmp_path / "venta_directa.csv"
    path.write_bytes(
        "N° Registro;Nombre Producto;Razon Social Titular;Condicion Venta\r\n"
        "B-1000/10;SPERTI PREPARATION H UNGÜENTO TÓPICO;LABORATORIOS WYETH LLC.;Directa\r\n"
        "F-1234/20;OTRO PRODUCTO;LAB;Directa\r\n".encode("cp1252")
    )
    assert load_otc_registrations(path) == {"B-1000/10", "F-1234/20"}


def test_missing_otc_file_is_not_fatal(tmp_path):
    assert load_otc_registrations(tmp_path / "nope.csv") == set()


# --------------------------------------------------------------------------
# TLS chain completion
# --------------------------------------------------------------------------


def _aia_der(url: bytes) -> bytes:
    """Minimal DER for an AIA CA-Issuers entry holding `url`."""
    return b"\x30\x82" + bytes.fromhex("06082B06010505073002") + b"\x86" + bytes([len(url)]) + url


def test_ca_issuer_url_is_read_from_the_aia_extension():
    url = b"http://secure.globalsign.com/cacert/gsgccr6alphasslca2025.crt"
    assert _ca_issuer_url(_aia_der(url)) == url.decode()


def test_ca_issuer_url_is_none_when_the_extension_is_absent():
    assert _ca_issuer_url(b"\x30\x82\x01\x02not a real certificate") is None


def test_estado_vigente_matches_the_option_value_the_page_renders():
    """ASP.NET event validation rejects any other spelling with HTTP 500."""
    assert ESTADO_VIGENTE == "Sí"
