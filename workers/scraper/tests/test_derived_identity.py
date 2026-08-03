"""Cases lifted from real production listings, not invented ones.

Every grouping test below is a pair the probe actually found across two chains,
and every separation test is a collapse the first draft of the key produced.
"""
import pytest

from src.derived_identity import (
    DerivedIdentity,
    distinctive_words,
    fold,
    normalise_size,
)


def key_of(name: str, brand: str) -> str:
    return DerivedIdentity.from_listing(name, brand).key


class TestNormaliseSize:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("Shampoo Pantene Molecular Bond Repair 1L", "1000ml"),
            ("Shampoo Pantene Molecular Bond Repair 1000ml", "1000ml"),
            ("Acondicionador Dove Nutricion 370ml", "370ml"),
            ("Crema Corporal 1,5 kg", "1500g"),
            ("Jabon Liquido 250 gr", "250g"),
            ("Panales Babysec XG 40 unidades", "40un"),
        ],
    )
    def test_folds_units_to_one_scale(self, title, expected):
        assert normalise_size(title) == expected

    def test_missing_size_is_empty_not_guessed(self):
        assert normalise_size("Shampoo Dove Reparacion") == ""

    def test_zero_and_junk_are_rejected(self):
        assert normalise_size("Producto 0 ml") == ""
        assert normalise_size(None) == ""


class TestDistinctiveWords:
    def test_brand_words_are_dropped(self):
        # The brand is already a field of the key; repeating it inside the word
        # set would make "Dove Shampoo" and "Shampoo" (brand=Dove) disagree.
        assert "dove" not in distinctive_words("Dove Shampoo Reparacion", "Dove")

    def test_offer_words_are_dropped(self):
        words = distinctive_words("Pack Oferta Shampoo Reparacion 400ml", "Dove")
        assert "pack" not in words and "oferta" not in words
        assert "shampoo" in words and "reparacion" in words

    def test_shade_codes_survive(self):
        # `310f` is the shade. Dropping it merges different products.
        assert "310f" in distinctive_words("Corrector Mate Natural 310F Desierto", "Vogue")

    def test_word_order_does_not_matter(self):
        a = distinctive_words("Shampoo Dove Nutricion Oleos", "Dove")
        b = distinctive_words("Dove Nutricion Oleos Shampoo", "Dove")
        assert a == b


class TestGroupsRealListings:
    """Titles two chains actually used for the same product."""

    def test_accents_and_hyphens_do_not_split(self):
        preunic = key_of("Acondicionador Dove Nutrición + Tri-Oleos 370ml", "Dove")
        salco = key_of("Dove Acondicionador Nutrición + Tri-óleos 370ml", "Dove")
        curie = key_of("Dove Acondicionador Nutrición + Tri-oleos - 370ml", "Dove")
        assert preunic == salco == curie

    def test_litre_written_two_ways_groups(self):
        assert key_of("Shampoo Pantene Molecular Bond Repair 1L", "Pantene") == key_of(
            "Shampoo Pantene Molecular Bond Repair 1000ml", "Pantene"
        )

    def test_same_shade_across_chains_groups(self):
        assert key_of(
            "Corrector Líquido Vogue Mate Natural 310F Desierto 5Ml", "Vogue"
        ) == key_of("Vogue Corrector Líquido Mate Natural 310F Desierto 5ml", "Vogue")


class TestNeverMergesDifferentProducts:
    """Collapses the first draft produced. Each one would price A as B."""

    def test_different_shades_stay_apart(self):
        jaguar = key_of("Vogue Esmalte Efecto Gel Jaguar 14ml", "Vogue")
        flamingo = key_of("Vogue Esmalte Efecto Gel Flamingo 14ml", "Vogue")
        assert jaguar != flamingo

    def test_different_sizes_stay_apart(self):
        assert key_of("Shampoo Aminexil Anticaída 370 ml", "Elvive") != key_of(
            "Shampoo Aminexil Anticaída 680 ml", "Elvive"
        )

    def test_different_brands_stay_apart(self):
        assert key_of("Agua Termal 150 ml", "La Roche Posay") != key_of(
            "Agua Termal 150 ml", "Vichy"
        )

    def test_different_variant_stays_apart(self):
        assert key_of("Dove Shampoo Nutricion Oleos 400ml", "Dove") != key_of(
            "Dove Shampoo Reparacion Intensa 400ml", "Dove"
        )


class TestGroupableGate:
    def test_brand_and_size_alone_are_not_identity(self):
        # "Dove 400ml" covers dozens of products; grouping on it would merge
        # every Dove bottle of that size into one price comparison.
        assert not DerivedIdentity.from_listing("Dove 400ml", "Dove").is_groupable

    def test_missing_size_is_not_groupable(self):
        assert not DerivedIdentity.from_listing("Dove Shampoo Reparacion", "Dove").is_groupable

    def test_missing_brand_is_not_groupable(self):
        assert not DerivedIdentity.from_listing("Shampoo Reparacion 400ml", "").is_groupable

    def test_full_evidence_is_groupable(self):
        assert DerivedIdentity.from_listing(
            "Dove Shampoo Nutricion Oleos 400ml", "Dove"
        ).is_groupable


def test_fold_handles_none():
    assert fold(None) == ""
