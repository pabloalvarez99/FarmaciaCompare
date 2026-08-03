import pytest

from src.anomaly import (
    MIN_PLAUSIBLE_CLP,
    MIN_SINGLE_UNIT_CLP,
    check_price,
    price_floor,
)
from src.scheduler import evaluate_health


def test_accepts_normal_price():
    assert check_price(12990, None).ok
    assert check_price(1004, 1290).ok


def test_rejects_zero_and_floor():
    assert not check_price(0, None).ok
    assert not check_price(50, None).ok


def test_rejects_catastrophic_drop():
    # Above MIN_PLAUSIBLE_CLP but < 15% of last → pure drop rule.
    v = check_price(1500, 12990)
    assert not v.ok
    assert "drop" in (v.reason or "")


def test_rejects_impossible_jump():
    v = check_price(100_000, 1000)
    assert not v.ok
    assert "jump" in (v.reason or "")


# --- single-unit floor --------------------------------------------------
# `price_floor` had no caller at all until `check_price` started taking the
# name: the exception below was dead code, and the products it exists for were
# quarantined on every run. Names here are verbatim from production rows that
# had a quarantine price and no accepted price ever.

SINGLE_UNIT_NAMES = [
    "Aguja 21g x 1 1/2 - 1 Aguja",                              # Curie, 100
    "Aguja Hipodérmica 23G x 1' - 1 unidad",                    # Curie, 100
    "Aguja Hipodérmica 27 g x 1/2 x 1 Unidad",                  # Farmaloop, 90
    "Jeringa Desechable Luer Lock 3 ml 21G x 1 1/2 x 1 Unidad",  # Farmaloop, 125
    "1 Paleta de Madera Desechable",                            # Cruz Verde, 60
    "Baja Lenguas de Madera 1 Baja Lenguas",                    # Cruz Verde, 60
    "Bajalengua de madera (1 unidad)",                          # MercadoFarma, 90
    "Higienix alcohol pad toallitas con alcohol al 70% 1 unidad",  # Dr. Simi, 30
    "Vitamina C sabor frutos rojos 100mg 1 tira",               # MercadoFarma, 90
    "Tapsin Caliente Noche - Sabor Limón - Sobre de 5 g ( 1 sobre ).",  # Farmex, 106
]

# Every one of these is also a real quarantined row. None says "one unit", so
# none may get the lower floor: a 179 CLP box of 30 amlodipino tablets and an
# 18 CLP sterile gauze are scraping errors, not cheap single units.
NOT_SINGLE_UNIT_NAMES = [
    "Amlodipino 10 mg x 30 comprimidos.",                       # Farmex, 179
    "Atenolol 50 mg x 20 comprimidos.",                         # Farmex, 15
    "Rosuvastatina 10 mg x 30 comprimidos.",                    # Farmex, 69
    "Gentamicina 0,3 % x 5 ml Solucion Oftalmica",              # Farmaloop, 100
    "Channelmed Gasa Estéril no Adherente 5x5 cm 4 Pliegues 2 Sobres",  # CV, 18
    "Pañuelos desechables 10 unidades",                         # Dr. Simi, 150
    "Paper Bolsa",                                              # Cruz Verde, 100
    "Paracetamol 500 mg 20 comprimidos",
]


@pytest.mark.parametrize("name", SINGLE_UNIT_NAMES)
def test_single_unit_name_lowers_floor(name):
    assert price_floor(name) == MIN_SINGLE_UNIT_CLP


@pytest.mark.parametrize("name", NOT_SINGLE_UNIT_NAMES)
def test_other_names_keep_general_floor(name):
    assert price_floor(name) == MIN_PLAUSIBLE_CLP


def test_price_floor_without_name():
    assert price_floor(None) == MIN_PLAUSIBLE_CLP
    assert price_floor("") == MIN_PLAUSIBLE_CLP


def test_accepts_cheap_needle_with_name():
    """The bug this fixes: a 90 CLP needle used to be quarantined every run."""
    assert check_price(90, None, name="Aguja Hipodérmica 27 g x 1/2 x 1 Unidad").ok
    assert check_price(60, None, name="1 Paleta de Madera Desechable").ok
    assert check_price(30, None, name="Higienix alcohol pad toallitas con alcohol al 70% 1 unidad").ok


def test_still_rejects_cheap_medicine_with_name():
    """A drug at 90 CLP is what MIN_PLAUSIBLE_CLP exists for. Unchanged."""
    v = check_price(90, None, name="Amlodipino 10 mg x 30 comprimidos.")
    assert not v.ok
    assert "below_floor" in (v.reason or "")
    assert not check_price(100, None, name="Gentamicina 0,3 % x 5 ml Solucion Oftalmica").ok


def test_single_unit_floor_is_a_floor_not_an_open_door():
    """A 1 CLP needle is still garbage — MIN_SINGLE_UNIT_CLP keeps guarding."""
    name = "Aguja 21g x 1 1/2 - 1 Aguja"
    assert not check_price(1, None, name=name).ok
    assert not check_price(14, None, name=name).ok
    assert check_price(15, None, name=name).ok


def test_name_omitted_behaves_exactly_as_before():
    """Default None must preserve the old behaviour for any caller."""
    for price in (0, 50, 199):
        assert not check_price(price, None).ok
    assert check_price(200, None).ok
    # Even a single-unit name is irrelevant when the caller does not pass it.
    assert not check_price(90, None).ok


def test_relative_rules_still_apply_to_single_units():
    """The lower floor only moves the floor; drop/jump are untouched."""
    name = "Jeringa Desechable 3ml 1 Unidad"
    assert not check_price(20, 190, name=name).ok      # <15% of last → drop
    assert not check_price(2000, 190, name=name).ok    # >8x last → jump
    assert check_price(160, 190, name=name).ok


def test_health_empty():
    status, reasons = evaluate_health("farmex", 0, 0)
    assert status == "empty"
    assert "zero_products" in reasons


def test_health_below_floor():
    status, reasons = evaluate_health("salcobrand", 10, 0)
    assert status == "failed"
    assert any(r.startswith("below_floor") for r in reasons)


def test_health_success():
    status, reasons = evaluate_health("farmex", 800, 0)
    assert status == "success"
    assert reasons == []
