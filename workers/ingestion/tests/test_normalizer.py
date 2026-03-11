import pytest
from src.normalizer import (
    normalize_name,
    extract_dosage,
    extract_pharmaceutical_form,
    normalize_ingredient_name,
)


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("PARACETAMOL") == "paracetamol"

    def test_strips_whitespace(self):
        assert normalize_name("  paracetamol  ") == "paracetamol"

    def test_collapses_spaces(self):
        assert normalize_name("paracetamol   500mg") == "paracetamol 500mg"

    def test_removes_special_chars(self):
        assert normalize_name("Tapsin® Forte") == "tapsin forte"

    def test_real_product_name(self):
        result = normalize_name("TAPSIN FORTE 500MG C/20 COMP")
        assert result == "tapsin forte 500mg c/20 comp"


class TestExtractDosage:
    def test_mg(self):
        assert extract_dosage("Paracetamol 500mg") == "500mg"

    def test_mg_with_space(self):
        assert extract_dosage("Paracetamol 500 mg") == "500mg"

    def test_mcg(self):
        assert extract_dosage("Levotiroxina 50mcg") == "50mcg"

    def test_g(self):
        assert extract_dosage("Amoxicilina 1g") == "1g"

    def test_percentage(self):
        assert extract_dosage("Crema 1%") == "1%"

    def test_no_dosage(self):
        assert extract_dosage("Vitamina C") is None


class TestExtractPharmaceuticalForm:
    def test_comprimido(self):
        assert extract_pharmaceutical_form("Paracetamol 500mg Comprimido") == "comprimido"

    def test_comp_abbreviation(self):
        assert extract_pharmaceutical_form("TAPSIN 500MG C/20 COMP") == "comprimido"

    def test_capsulas(self):
        result = extract_pharmaceutical_form("Ibuprofeno 400mg Cápsulas")
        assert result == "capsula"

    def test_jarabe(self):
        assert extract_pharmaceutical_form("Amoxicilina Jarabe 250mg/5ml") == "jarabe"

    def test_inyectable(self):
        assert extract_pharmaceutical_form("Ceftriaxona 1g Inyectable") == "inyectable"

    def test_crema(self):
        assert extract_pharmaceutical_form("Hidrocortisona 1% Crema") == "crema"

    def test_unknown_returns_otro(self):
        assert extract_pharmaceutical_form("Medicamento X") == "otro"


class TestNormalizeIngredientName:
    def test_strips_and_lowercases(self):
        assert normalize_ingredient_name("  PARACETAMOL  ") == "paracetamol"

    def test_removes_accents_for_matching(self):
        assert normalize_ingredient_name("Ácido Acetilsalicílico") == "acido acetilsalicilico"
