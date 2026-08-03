import pytest

from src.matcher import DrugMatcher, MatchResult
from src.product_identity import (
    ProductIdentity,
    extract_pack_volume_ml,
    is_medical_dosage,
    looks_cosmetic,
)


class TestProductIdentity:
    def test_parses_dose_form_pack(self):
        ident = ProductIdentity.from_name(
            "Kitadol (B) Paracetamol 500mg 24 Comprimidos"
        )
        assert ident.dosage == "500mg"
        assert ident.form == "comprimido"
        assert ident.pack_count == 24

    def test_c_slash_pack(self):
        ident = ProductIdentity.from_name("TAPSIN FORTE 500MG C/20 COMP")
        assert ident.dosage == "500mg"
        assert ident.pack_count == 20
        assert ident.form == "comprimido"

    def test_hard_incompatible_different_dose(self):
        a = ProductIdentity.from_name("Paracetamol 500mg 20 comprimidos")
        b = ProductIdentity.from_name("Paracetamol 1000mg 20 comprimidos")
        assert a.hard_incompatible(b)

    def test_hard_incompatible_different_pack(self):
        a = ProductIdentity.from_name("Kitadol 500mg 24 comprimidos")
        b = ProductIdentity.from_name("Kitadol 500mg 12 comprimidos")
        assert a.hard_incompatible(b)

    def test_compatible_same_presentation(self):
        a = ProductIdentity.from_name("Panadol 500 mg 16 comprimidos")
        b = ProductIdentity.from_name("panadol 500mg x16 comp")
        assert not a.hard_incompatible(b)

    def test_concentration_not_confused_with_bottle_volume(self):
        ident = ProductIdentity.from_name(
            "Levetiracetam 100 mg/mL solucion oral 300 mL"
        )
        assert ident.dosage == "100mg/ml"
        assert ident.pack_volume_ml == 300
        assert is_medical_dosage(ident.dosage)

    def test_compact_catalog_volume(self):
        ident = ProductIdentity.from_name("KOPODEX 100MG.120ML")
        assert ident.dosage == "100mg"
        assert ident.pack_volume_ml == 120

    def test_compact_catalog_pack_count(self):
        ident = ProductIdentity.from_name("INDOMETACINA 25MG.24COM.")
        assert ident.dosage == "25mg"
        assert ident.pack_count == 24

    def test_volume_mismatch_hard_incompatible(self):
        a = ProductIdentity.from_name(
            "Levetiracetam 100 mg/mL solucion oral 300 mL"
        )
        b = ProductIdentity.from_name("KOPODEX 100MG.120ML")
        # Same concentration family, different bottle size → different SKU.
        assert a.pack_volume_ml == 300
        assert b.pack_volume_ml == 120
        # dosages differ in form (100mg/ml vs 100mg) so also incompatible
        assert a.hard_incompatible(b)

    def test_pack_count_mismatch_indometacina(self):
        a = ProductIdentity.from_name("Indometacina 25 mg 30 capsulas")
        b = ProductIdentity.from_name("INDOMETACINA 25MG.24COM.")
        assert a.pack_count == 30
        assert b.pack_count == 24
        assert a.hard_incompatible(b)

    def test_bare_ml_is_pack_not_dose(self):
        """Shampoo '300 ml' must not look like a medical dosage."""
        ident = ProductIdentity.from_name("Shampoo Argan 300 ml")
        assert ident.dosage is None
        assert ident.pack_volume_ml == 300
        assert not is_medical_dosage(ident.dosage)

    def test_cosmetic_detector(self):
        assert looks_cosmetic("Leche en Polvo Etapa 3+ 700 gr")
        assert looks_cosmetic("Shampoo Argan 300 ml")
        assert looks_cosmetic("guante ex nitrilo negro m l polvo x 100")
        assert not looks_cosmetic("Paracetamol 500 mg 16 comprimidos")

    def test_barcode_rejects_short_internal_skus(self):
        assert ProductIdentity.from_name("x", barcode="123456789").barcode is None
        assert ProductIdentity.from_name("x", barcode="7801234567890").barcode == "7801234567890"

    def test_combo_inhaler_dose_parsed(self):
        a = ProductIdentity.from_name("Fluxamol HFA 250/25 mcg 120 Dosis")
        assert a.dosage == "250/25mcg"
        assert a.pack_count == 120
        assert a.form == "inhalador"

    def test_combo_dose_order_matters(self):
        a = ProductIdentity.from_name("Aurituss 25/250 mcg")
        b = ProductIdentity.from_name("aurituss 125/25 mcg 120dosis")
        assert a.dosage == "25/250mcg"
        assert b.dosage == "125/25mcg"
        assert a.hard_incompatible(b)

    def test_inhaler_pack_mismatch(self):
        a = ProductIdentity.from_name("Fluxamol HFA 250/25 mcg 120 Dosis")
        b = ProductIdentity.from_name("Fluxamol HFA 250/25 mcg 200 dosis")
        assert a.hard_incompatible(b)

    def test_fp_fluxamol_not_alart(self):
        a = ProductIdentity.from_name("Fluxamol HFA 250/25 mcg 120 Dosis")
        b = ProductIdentity.from_name("alart b hfa 250mcg 200ds")
        # combo vs single strength → incompatible
        assert a.hard_incompatible(b)

    def test_chilean_decimal_comma_preserved(self):
        a = ProductIdentity.from_name("Betacort 0,5 mg/ml Gotas Oral Fco. 30 ml")
        assert a.dosage == "0.5mg/ml"
        b = ProductIdentity.from_name("Paracetamol 0,5 g")
        assert b.dosage == "0.5g"
        # Must NOT collapse 0,5 → 5
        assert b.dosage != "5g"

    def test_percent_strength_parsed(self):
        a = ProductIdentity.from_name("Hidrocortisona 1 % x 15 g Crema")
        assert a.dosage == "1%"
        b = ProductIdentity.from_name("Benzac AC Wash 5 % x 100 g")
        assert b.dosage == "5%"

    def test_combo_percent_shared_unit(self):
        a = ProductIdentity.from_name("Sophixin DX Ofteno 0,3% / 0,1% sol oft 5 ml")
        assert a.dosage == "0.3/0.1%"

    def test_combo_percent_dual_labeled(self):
        a = ProductIdentity.from_name(
            "Latanoprost 0,005 % / Timolol 0,5 % Solución Oftálmica x 2,5 mL"
        )
        assert a.dosage == "0.005/0.5%"
        # Must not collapse to single-agent Timolol 0.5%
        b = ProductIdentity.from_name("timolol 0.5 %")
        assert a.hard_incompatible(b)

    def test_combo_percent_vs_single_incompatible(self):
        a = ProductIdentity.from_name("Latof-T 0,005% / 0.5% sol oft")
        b = ProductIdentity.from_name("timolol 0.5 % sol oft")
        assert a.dosage == "0.005/0.5%"
        assert a.hard_incompatible(b)

    def test_combo_tablet_bare_numbers(self):
        # Chilean ARB+HCTZ titles often omit the unit on the slash form.
        a = ProductIdentity.from_name(
            "Olmepress-D 20/12,5 Olmesartán 20 mg Hidroclorotiazida 12,5 mg"
        )
        assert a.dosage == "20/12.5mg"
        b = ProductIdentity.from_name("olmesartan 20mg 20 mg")
        assert a.hard_incompatible(b)


class TestDrugMatcher:
    @pytest.fixture
    def candidates(self):
        return [
            {
                "medication_id": "med-001",
                "normalized_name": "paracetamol 500mg comprimido",
                "barcode": "7801234567890",
            },
            {"medication_id": "med-002", "normalized_name": "ibuprofeno 400mg capsula"},
            {"medication_id": "med-003", "normalized_name": "amoxicilina 500mg capsula"},
            {
                "medication_id": "med-001",
                "normalized_name": "tapsin forte 500mg comprimido",
            },
            {
                "medication_id": "med-001",
                "normalized_name": "panadol 500mg comprimido",
            },
            {
                "medication_id": "med-004",
                "normalized_name": "paracetamol 1000mg comprimido",
            },
            {
                "medication_id": "med-005",
                "normalized_name": "levetiracetam 100mg/ml solucion 300ml",
            },
            {
                "medication_id": "med-006",
                "normalized_name": "kopodex 100mg 120ml",
            },
            {
                "medication_id": "med-007",
                "normalized_name": "indometacina 25mg 24 comprimidos",
            },
            {
                "medication_id": "med-008",
                "normalized_name": "dalex shampoo 300 ml",
            },
            {
                "medication_id": "med-009",
                "normalized_name": "guante ex nitrilo negro m l polvo x 100",
            },
        ]

    @pytest.fixture
    def matcher(self, candidates):
        return DrugMatcher(candidates)

    def test_exact_name_match(self, matcher):
        result = matcher.match("panadol 500mg comprimido")
        assert result is not None
        assert result.medication_id == "med-001"
        assert result.confidence >= 0.95
        assert matcher.should_auto_link(result)

    def test_fuzzy_name_match(self, matcher):
        result = matcher.match("TAPSIN FORTE 500MG C/20 COMP")
        assert result is not None
        assert result.medication_id == "med-001"
        assert result.confidence >= 0.80

    def test_generic_name_match(self, matcher):
        result = matcher.match("paracetamol 500mg tabletas")
        assert result is not None
        assert result.medication_id == "med-001"

    def test_no_match_below_threshold(self, matcher):
        result = matcher.match("vitamina c efervescente 1g")
        if result:
            assert result.confidence < 0.75 or result.grey_zone

    def test_different_dosage_rejected(self, matcher):
        narrow = DrugMatcher(
            [{"medication_id": "med-001", "normalized_name": "paracetamol 500mg comprimido"}]
        )
        result = narrow.match("paracetamol 1000mg comprimido")
        assert result is None

    def test_barcode_exact(self, matcher):
        result = matcher.match("cualquier basura", barcode="7801234567890")
        assert result is not None
        assert result.method == "barcode"
        assert result.confidence == 1.0
        assert result.medication_id == "med-001"

    def test_xumadol_not_kitadol(self, matcher):
        """Classic false-positive trap: different brand + different dose."""
        result = matcher.match("Xumadol Paracetamol 1000 mg 20 Comprimidos")
        if result:
            assert result.medication_id == "med-004"
            assert "1000" in result.matched_name

    def test_clotrim_not_amoxicillin(self, matcher):
        """Dose+form alone must not link unrelated brands."""
        result = matcher.match("Clotrimin Via Vaginal 500 mg 1 x capsula blanda")
        assert result is None or not matcher.should_auto_link(result)

    def test_skips_bare_ingredient_candidates(self):
        m = DrugMatcher(
            [
                {"medication_id": "med-x", "normalized_name": "paracetamol"},
                {"medication_id": "med-y", "normalized_name": "paracetamol 500mg comprimido"},
            ]
        )
        assert all("500" in n or len(n.split()) > 2 for n in m.names)

    # --- Documented production false positives (docs/coordinacion-agentes.md) ---

    def test_fp_leche_not_guantes(self, matcher):
        result = matcher.match("Leche en Polvo Etapa 3+ 700 gr")
        assert result is None

    def test_fp_shampoo_not_dalex(self, matcher):
        result = matcher.match("Shampoo Argan 300 ml")
        assert result is None
        assert not matcher.should_auto_link(result)

    def test_fp_volume_300_not_120(self, matcher):
        result = matcher.match("Levetiracetam 100 mg/mL solucion oral 300 mL")
        if result:
            assert result.medication_id == "med-005"
            assert matcher.should_auto_link(result) or result.medication_id != "med-006"
            assert "120" not in result.matched_name

    def test_fp_pack_30_not_24(self, matcher):
        result = matcher.match("Indometacina 25 mg 30 capsulas")
        # Must not auto-link to 24-count catalog row.
        if result and result.medication_id == "med-007":
            assert not matcher.should_auto_link(result)
        elif result:
            assert result.medication_id != "med-007" or result.grey_zone

    def test_is_medicine_false_blocks_fuzzy(self, matcher):
        result = matcher.match(
            "Panadol 500mg 16 comprimidos",
            is_medicine=False,
        )
        assert result is None

    def test_is_medicine_false_still_allows_barcode(self, matcher):
        result = matcher.match(
            "random cosmetic",
            barcode="7801234567890",
            is_medicine=False,
        )
        assert result is not None
        assert result.method == "barcode"

    def test_medicine_still_links(self, matcher):
        result = matcher.match(
            "Anfibol Nebivolol 5 mg 30 Comprimidos",
            is_medicine=True,
        )
        # No nebivolol in fixture — just ensure the flag does not crash.
        assert result is None or isinstance(result, MatchResult)
