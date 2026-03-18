import pytest
from src.matcher import DrugMatcher, MatchResult


class TestDrugMatcher:
    @pytest.fixture
    def candidates(self):
        return [
            {"medication_id": "med-001", "normalized_name": "paracetamol 500mg comprimido"},
            {"medication_id": "med-002", "normalized_name": "ibuprofeno 400mg capsula"},
            {"medication_id": "med-003", "normalized_name": "amoxicilina 500mg capsula"},
            {"medication_id": "med-001", "normalized_name": "tapsin forte 500mg comprimido"},
            {"medication_id": "med-001", "normalized_name": "panadol 500mg comprimido"},
        ]

    @pytest.fixture
    def matcher(self, candidates):
        return DrugMatcher(candidates)

    def test_exact_name_match(self, matcher):
        result = matcher.match("panadol 500mg comprimido")
        assert result is not None
        assert result.medication_id == "med-001"
        assert result.confidence >= 0.95

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
            assert result.confidence < 0.75

    def test_different_dosage_low_confidence(self, matcher):
        result = matcher.match("paracetamol 1000mg comprimido")
        if result:
            assert result.confidence < 0.95
