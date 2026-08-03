"""Tests for the category classifier.

Every case here is a label that exists in production, quoted as the chain
publishes it. The ones marked REGRESIÓN are errors a hand-read sample caught in
the first draft; they are the reason the ladder is ordered the way it is.
"""
from __future__ import annotations

import pytest

from src.classify_categories import (
    BEBE,
    COSMETICA,
    DERMOCOSMETICA,
    DISPOSITIVO,
    HIGIENE,
    MEDICAMENTO,
    ORDER,
    SUPLEMENTO,
    classify,
    declared_sources,
    fold,
    match_ladder,
    mercadofarma_medicine,
    stratified,
    truthy,
)


# --------------------------------------------------------------------------
# fold
# --------------------------------------------------------------------------
def test_fold_strips_accents_and_pads():
    assert fold("Dermocosmética") == " dermocosmetica "


def test_fold_splits_cruz_verde_slugs_into_words():
    assert fold("capilar-mascarillas-tratamientos") == " capilar mascarillas tratamientos "


def test_fold_turns_enie_into_n():
    assert fold("Pañales") == " panales "


def test_fold_of_nothing_is_empty_not_two_spaces():
    assert fold(None) == ""
    assert fold("  ") == ""


def test_padding_stops_a_match_inside_a_longer_word():
    # " sin medicamento " must not be reachable by a \bmedicamento\b rule when
    # the medicine rules are switched off.
    assert match_ladder(fold("sin medicamento"), allow_medicine=False) is None


# --------------------------------------------------------------------------
# MercadoFarma: the negative contains the positive
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    ["sin medicamento", "Sin medicamento", "sin medicamentos",
     "sin medicaento", "sin medicamnto"],
)
def test_mercadofarma_negative_wins_over_the_positive_inside_it(value):
    assert mercadofarma_medicine(value) is False


@pytest.mark.parametrize(
    "value", ["medicamento", "Medicamento", "medicamentos",
              "medicamaento", "Medicinas y medicamentos"],
)
def test_mercadofarma_positive(value):
    assert mercadofarma_medicine(value) is True


@pytest.mark.parametrize(
    "value", ["no aplica", ", no aplica", "NO DISPONIBLE", "fnl", None, ""],
)
def test_mercadofarma_no_signal_is_none_not_false(value):
    assert mercadofarma_medicine(value) is None


def test_mercadofarma_negative_listing_is_not_a_medicine():
    category, reason = classify(
        "mercadofarma", {"category": "sin medicamento", "tags": ["Vitaminas"]}
    )
    assert category == SUPLEMENTO
    assert reason.startswith("regla:suplemento")


def test_mercadofarma_positive_listing_short_circuits_on_the_store_flag():
    assert classify("mercadofarma", {"category": "medicamento"}) == (
        MEDICAMENTO,
        "flag-tienda",
    )


# --------------------------------------------------------------------------
# REGRESIÓN: the ladder order carries the mapping
# --------------------------------------------------------------------------
def test_hair_mask_is_not_a_surgical_mask():
    """56 Cruz Verde hair masks used to come back `dispositivo`."""
    category, _ = classify(
        "cruz_verde",
        {"category": "capilar-mascarillas-tratamientos", "isMedicine": False},
    )
    assert category == COSMETICA


def test_surgical_masks_still_reach_dispositivo():
    category, _ = classify(
        "salcobrand", {"category": "Cuidado Personal > Primeros Auxilios > Mascarillas"}
    )
    assert category == DISPOSITIVO


def test_farmex_gloves_and_masks_tag_is_a_device():
    category, _ = classify(
        "farmex", {"tags": ["guantes y mascarillas", "insumos medicos"]}
    )
    assert category == DISPOSITIVO


def test_weight_loss_drugs_filed_under_medicamentos_stay_medicine():
    """Farmaloop's "Medicamentos > Control de Peso" is Ozempic and phentermine."""
    category, _ = classify(
        "farmaloop", {"category": "Medicamentos", "subCategory": "Control de Peso"}
    )
    assert category == MEDICAMENTO


def test_weight_loss_outside_the_medicine_department_is_a_supplement():
    category, _ = classify(
        "cruz_verde",
        {"category": "vitaminas-y-suplementos-control-de-peso", "isMedicine": False},
    )
    assert category == SUPLEMENTO


def test_dermatological_drugs_are_medicine_not_skincare():
    """59 Ahumada antifungals used to come back `dermocosmetica`."""
    category, _ = classify(
        "ahumada",
        {"category": "Medicamentos > Dermatológicos",
         "categoryLeaf": "Antimicóticos"},
    )
    assert category == MEDICAMENTO


def test_mineral_sunscreen_is_not_a_mineral_supplement():
    """67 Salcobrand sunscreens used to come back `suplemento`."""
    category, _ = classify(
        "salcobrand",
        {"category": "Dermocoaching > Protección Solar > Rostro > "
                     "Pantallas Solares y Minerales"},
    )
    assert category == DERMOCOSMETICA


def test_mineral_supplements_are_still_supplements():
    category, _ = classify(
        "salcobrand",
        {"category": "Vitaminas y Suplementos > Vitaminas y Minerales > "
                     "Suplementos Minerales"},
    )
    assert category == SUPLEMENTO


def test_energy_drinks_in_the_supplement_aisle_are_out_of_scope():
    """Monster and chocolate peanuts hang off "vitaminas y suplementos"."""
    category, reason = classify(
        "cruz_verde",
        {"category": "vitaminas-y-suplementos-alimentos-y-bebidas-bebestibles",
         "isMedicine": False},
    )
    assert category is None
    assert reason.startswith("fuera-de-alcance:alimentos")


def test_toys_in_the_baby_aisle_are_out_of_scope():
    category, reason = classify(
        "salcobrand", {"category": "Infantil y Mamá > Accesorios > Juguetes"}
    )
    assert category is None
    assert reason.startswith("fuera-de-alcance:juguetes")


def test_cruz_verde_nappy_slug_spelling_is_read():
    """Cruz Verde writes `paniales`, which folding does not repair."""
    category, _ = classify(
        "cruz_verde",
        {"category": "paniales-y-wipes-paniales-extra-grande", "isMedicine": False},
    )
    assert category == BEBE


def test_promo_department_for_small_appliances_is_not_a_medical_device():
    """"dia-del-padre-electro" is a Father's Day aisle, not a monitor."""
    category, _ = classify(
        "cruz_verde", {"category": "dia-del-padre-electro", "isMedicine": False}
    )
    assert category is None


# --------------------------------------------------------------------------
# No category is invented
# --------------------------------------------------------------------------
def test_a_link_to_the_drug_catalog_is_not_evidence_of_anything():
    """The classifier must not read `medication_id`; only declared labels."""
    category, reason = classify("farmex", {"tags": ["persistente", "over-10000"]})
    assert category is None
    assert reason == "sin-regla"


def test_no_attributes_at_all_is_reported_as_sin_etiqueta():
    assert classify("farmex", None) == (None, "sin-etiqueta")
    assert classify("farmex", {}) == (None, "sin-etiqueta")


def test_merchandising_bucket_with_no_signal_stays_null():
    category, reason = classify(
        "cruz_verde", {"category": "productos-discontinuos", "isMedicine": False}
    )
    assert category is None
    assert reason == "sin-regla"


def test_perfume_is_out_of_scope_not_cosmetica():
    category, reason = classify(
        "salcobrand", {"category": "Belleza > Perfumes & Fragancias > Mujer"}
    )
    assert category is None
    assert reason.startswith("fuera-de-alcance:perfumeria")


def test_veterinary_is_out_of_scope_even_when_it_says_medicamento():
    category, reason = classify("curie", {"category": "Veterinarios",
                                          "tags": ["medicamento veterinario"]})
    assert category is None
    assert reason.startswith("fuera-de-alcance:veterinaria")


# --------------------------------------------------------------------------
# The first-party flag, and only the first-party flag, may veto
# --------------------------------------------------------------------------
def test_cruz_verde_store_flag_beats_the_merchandising_slug():
    assert classify(
        "cruz_verde", {"category": "belleza-maquillaje-labios", "isMedicine": True}
    ) == (MEDICAMENTO, "flag-tienda")


def test_cruz_verde_store_flag_vetoes_a_promo_slug_that_says_medicamentos():
    category, _ = classify(
        "cruz_verde",
        {"category": "ofertas-imperdibles-medicamentos-cardiometabolico",
         "isMedicine": False},
    )
    assert category is None


def test_derived_flag_never_vetoes_a_salcobrand_drug():
    """Salcobrand files real antihypertensives under "Cuidado de la Salud"."""
    category, _ = classify(
        "salcobrand",
        {"category": "Cuidado de la Salud > Salud Adulto Mayor > Antihipertensivos",
         "isMedicine": False},
    )
    assert category == MEDICAMENTO


def test_derived_flag_is_the_last_resort_for_unknown_therapeutic_classes():
    category, reason = classify(
        "farmex", {"category": "Antivertiginosos Anticinetósicos", "isMedicine": True}
    )
    assert (category, reason) == (MEDICAMENTO, "flag-derivado")


# --------------------------------------------------------------------------
# declared_sources: strong field first, weak field second
# --------------------------------------------------------------------------
def test_curie_product_type_is_read_before_its_tags():
    """216 Curie listings carry the tag "dermocosmetica" and type "Medicamentos"."""
    assert declared_sources("curie", {"category": "Medicamentos",
                                      "tags": ["dermocosmetica"]}) == [
        " medicamentos ",
        " dermocosmetica ",
    ]
    category, reason = classify(
        "curie", {"category": "Medicamentos", "tags": ["dermocosmetica"]}
    )
    assert category == MEDICAMENTO
    assert reason == "regla:medicamento"


def test_preunic_merchandising_leaf_falls_through_to_its_path():
    category, reason = classify(
        "preunic",
        {"category": "pack y estuches",
         "categoryPath": ["pack y estuches", "mi bebe"], "isMedicine": False},
    )
    assert category == BEBE
    assert reason.endswith("+1")


def test_farmaloop_joins_category_and_subcategory_into_one_label():
    assert declared_sources(
        "farmaloop", {"category": "Cuidado y Belleza", "subCategory": "Dental"}
    ) == [" cuidado y belleza dental "]


def test_ahumada_joins_breadcrumb_and_leaf():
    assert declared_sources(
        "ahumada", {"category": "Belleza > Cuidado Capilar", "categoryLeaf": "Shampoo"}
    ) == [" belleza cuidado capilar shampoo "]


def test_non_string_attribute_values_do_not_crash():
    assert declared_sources("curie", {"category": 7, "tags": [None, 3, "vitaminas"]}) == [
        " vitaminas "
    ]


# --------------------------------------------------------------------------
# Ordinary mappings, one per category
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "chain,attributes,expected",
    [
        ("salcobrand",
         {"category": "Medicamentos > Sistema Nervioso > Antidepresivos"},
         MEDICAMENTO),
        ("farmex", {"category": "Antihipertensivos", "isMedicine": True},
         MEDICAMENTO),
        ("farmaloop",
         {"category": "Suplementos y Vitaminas", "subCategory": "Probióticos"},
         SUPLEMENTO),
        ("knop", {"category": "Multivitamínicos"}, SUPLEMENTO),
        ("ahumada",
         {"category": "Dermocosmética > Rostro", "categoryLeaf": "Hidratación"},
         DERMOCOSMETICA),
        ("dr_simi", {"category": "Cuidado Personal > Protección Solar"},
         DERMOCOSMETICA),
        ("preunic",
         {"category": "maquillaje labios",
          "categoryPath": ["maquillaje labios", "maquillaje", "labiales"]},
         COSMETICA),
        ("salcobrand", {"category": "Cuidado Personal > Cuidado Capilar > Shampoo"},
         COSMETICA),
        ("ahumada",
         {"category": "Higiene y Cuidado Personal > Cuidado Bucal",
          "categoryLeaf": "Pastas Dentales"},
         HIGIENE),
        ("preunic",
         {"category": "desodorantes hombre",
          "categoryPath": ["desodorantes hombre", "cuidado personal"]},
         HIGIENE),
        ("cruz_verde",
         {"category": "alimentacion-y-lactancia-formulas-infantiles",
          "isMedicine": False},
         BEBE),
        ("farmaloop",
         {"category": "Dispositivos Médicos", "subCategory": "Otros"},
         DISPOSITIVO),
        ("curie", {"category": "Insumos y dispositivos médicos"}, DISPOSITIVO),
    ],
)
def test_representative_labels(chain, attributes, expected):
    assert classify(chain, attributes)[0] == expected


def test_every_rule_points_at_a_real_category_or_the_sentinel():
    from src.classify_categories import LADDER, OUT_OF_SCOPE

    for rule in LADDER:
        assert rule.category in set(ORDER) | {OUT_OF_SCOPE}, rule.name


def test_classify_only_ever_returns_a_seeded_slug_or_none():
    for chain, attributes in [
        ("salcobrand", {"category": "Belleza > Make-Up > Labios"}),
        ("farmex", {"tags": ["persistente"]}),
        ("knop", {"category": "Té e Infusiones"}),
    ]:
        category, _ = classify(chain, attributes)
        assert category is None or category in ORDER


# --------------------------------------------------------------------------
# truthy
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value,expected",
    [(True, True), (False, False), ("true", True), ("False", False),
     ("1", True), ("0", False), (None, None), ("maybe", None), (1, None)],
)
def test_truthy(value, expected):
    assert truthy(value) is expected


# --------------------------------------------------------------------------
# The sample must not be all one chain
# --------------------------------------------------------------------------
def test_stratified_sample_spreads_across_chains():
    per_chain = {
        "farmex": [(f"f{i}", "r") for i in range(100)],
        "knop": [("k0", "r"), ("k1", "r")],
        "curie": [("c0", "r")],
    }
    picked = stratified(per_chain, 6)
    assert len(picked) == 6
    assert {c for c, _n, _r in picked} == {"farmex", "knop", "curie"}


def test_stratified_sample_falls_back_when_only_one_chain_has_rows():
    picked = stratified({"farmex": [(f"f{i}", "r") for i in range(4)]}, 10)
    assert len(picked) == 4


# --------------------------------------------------------------------------
# A vague first label must not pre-empt a precise second one
# --------------------------------------------------------------------------
def test_precise_tag_beats_broad_department_on_the_first_field():
    """Farmex files Colgate toothpaste under the department "COSMETICO"."""
    category, reason = classify(
        "farmex",
        {"category": "COSMETICO", "tags": ["cuidado bucal", "HIGIENE DENTAL"]},
    )
    assert category == HIGIENE
    assert reason == "regla:higiene+1"


def test_precise_tag_beats_broad_cuidado_personal():
    """Curie files a Dove conditioner under "Cuidado personal"."""
    category, reason = classify(
        "curie", {"category": "Cuidado personal", "tags": ["acondicionador"]}
    )
    assert category == COSMETICA
    assert reason == "regla:cosmetica-capilar+1"


def test_broad_rule_still_answers_when_nothing_precise_matches():
    category, reason = classify("farmex", {"category": "COSMETICO", "tags": ["delete"]})
    assert category == COSMETICA
    assert reason == "regla:belleza-generico"


def test_match_ladder_can_be_asked_without_the_broad_rules():
    assert match_ladder(fold("belleza"), allow_broad=False) is None
    assert match_ladder(fold("belleza"), allow_broad=True) == (COSMETICA, "belleza-generico")


def test_curacion_tag_alone_is_not_a_device():
    """Vaseline and baking soda carry it; real dressings say more than that."""
    assert classify("farmex", {"category": "Crema", "tags": ["curacion"]})[0] != DISPOSITIVO


def test_curie_device_department_survives_dropping_the_curacion_tag():
    category, _ = classify(
        "curie", {"category": "Insumos y dispositivos médicos", "tags": ["curaciones"]}
    )
    assert category == DISPOSITIVO
