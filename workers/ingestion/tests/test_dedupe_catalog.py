"""Tests for the medication catalog deduplicator.

Everything here is a pure function fed with hand-built rows; no database is
touched. `dedupe` itself is deliberately untested — it needs a live session.

The tests are written from the direction that matters: merging too much is
worse than not merging, so most of them assert a **refusal**. Each refusal
names the production incident it protects, because the day someone loosens one
of these gates to raise the linked count, the test is the only thing left that
remembers why the gate exists.
"""
import pytest

from src.dedupe_catalog import (
    MODIFIER_MARKERS,
    ROUTE_MARKERS,
    MedicationRow,
    MergeGroup,
    choose_survivor,
    family_substances,
    is_medical_dosage,
    looks_like_combination,
    markers,
    measure_ambiguity,
    normalize_substance,
    pack_count,
    pack_volume_ml,
    plan_merges,
    plan_name_moves,
)

# One composition per registration, the shape `load_compositions` returns.
SILDENAFILO = frozenset({"SILDENAFILO"})
AMLODIPINO = frozenset({"AMLODIPINO"})
NISTATINA = frozenset({"NISTATINA"})
METFORMINA = frozenset({"METFORMINA"})
KETOROLACO = frozenset({"KETOROLACO TROMETAMOL"})
INSULINA = frozenset({"INSULINA"})
BISOPROLOL_AMLODIPINO = frozenset({"BISOPROLOL", "AMLODIPINO"})


def row(
    id: str,
    name: str,
    dosage: str = "50 mg",
    form: str = "Comprimido",
    registration: str | None = None,
    barcodes: tuple[str, ...] = (),
    prescription_required: bool = False,
    product_count: int = 0,
    name_count: int = 0,
) -> MedicationRow:
    return MedicationRow(
        id=id,
        name=name,
        dosage=dosage,
        form=form,
        registration=registration if registration is not None else f"F-{id}/23",
        barcodes=barcodes,
        prescription_required=prescription_required,
        product_count=product_count,
        name_count=name_count,
    )


def keys_of(merges):
    return {(g.substance, g.key[1], g.key[2]) for g in merges}


def members_of(group: MergeGroup) -> set[str]:
    return {group.survivor.id} | {loser.id for loser in group.losers}


# --------------------------------------------------------------------------
# Strength parsing: a row with no readable strength is never merged
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dosage",
    ["50 mg", "100 mcg", "0,05 %", "100 ui", "15 mg/ml", "200 mg/5 ml", "1 g"],
)
def test_real_strengths_are_accepted(dosage):
    assert is_medical_dosage(dosage)


@pytest.mark.parametrize("dosage", ["", None, "25 ml", "120 unidades", "3 comprimidos"])
def test_a_bare_quantity_is_not_a_strength(dosage):
    """`amlodipino` with no strength names 80 medications, 5 mg and 10 mg alike.

    Grouping on a row whose dose could not be parsed would put those 80 in one
    bucket, which is the 10x-potency error the project already paid for once.
    """
    assert not is_medical_dosage(dosage)


# --------------------------------------------------------------------------
# Pack size
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("PARACETAMOL COMPRIMIDOS 500 mg X 20", 20),
        ("IBUPROFENO 400 mg 30 COMPRIMIDOS", 30),
        ("SILDENAFIL COMPRIMIDOS RECUBIERTOS 50 mg", None),
    ],
)
def test_pack_count(name, expected):
    assert pack_count(name) == expected


def test_pack_volume_ignores_the_concentration_denominator():
    """"100 mg/mL" is a strength, not a 1 mL bottle.

    Reading the denominator as a pack size would give two bottles of the same
    syrup different keys and stop them merging — and worse, could make a
    120 mL and a 300 mL bottle agree because both had been read as "1 mL".
    """
    assert pack_volume_ml("PARACETAMOL SOLUCIÓN ORAL 100 mg/mL FRASCO 120 mL") == 120
    assert pack_volume_ml("AMOXICILINA SUSPENSIÓN 250 mg/5 mL") is None


# --------------------------------------------------------------------------
# Route and modifier markers, and the plural the ISP actually writes
# --------------------------------------------------------------------------


def test_plural_markers_fold_onto_the_singular():
    """The registry writes "COMPRIMIDOS SUBLINGUALES", never "SUBLINGUAL".

    Matching whole words against a singular vocabulary saw none of them, and
    that put BURTEN SL (sublingual ketorolac) in the same group as swallowed
    ketorolac. Both spellings have to produce the same marker, or the key is
    blind to the route in one row and split by it in the next.
    """
    assert markers("COMPRIMIDOS SUBLINGUALES 10 mg", ROUTE_MARKERS) == {"sublingual"}
    assert markers("COMPRIMIDO SUBLINGUAL 10 mg", ROUTE_MARKERS) == {"sublingual"}
    assert markers("CÁPSULAS ORALES", ROUTE_MARKERS) == {"oral"}
    assert markers("ÓVULOS VAGINALES", ROUTE_MARKERS) == {"vaginal"}
    assert markers("COMPRIMIDOS BUCODISPERSABLES 8 mg", MODIFIER_MARKERS) == {
        "bucodispersable"
    }


def test_markers_match_whole_words_only():
    """A substring test made CAPTOPRIL a capsule; the same trap applies here."""
    assert markers("CAPTOPRIL COMPRIMIDOS 25 mg", ROUTE_MARKERS) == frozenset()
    assert markers("MORAL", ROUTE_MARKERS) == frozenset()
    assert markers("FLORALES", ROUTE_MARKERS) == frozenset()


def test_a_word_already_in_the_vocabulary_maps_to_itself():
    """`MODIFIER_MARKERS` holds "prolongado" and "prolongados" both.

    The plural expansion must not make the result depend on set iteration
    order, or two runs over the same catalog would produce different keys.
    """
    vocabulary = frozenset({"prolongado", "prolongados"})
    assert markers("COMPRIMIDOS PROLONGADOS", vocabulary) == {"prolongados"}
    assert markers("COMPRIMIDO PROLONGADO", vocabulary) == {"prolongado"}


def test_accents_do_not_hide_a_marker():
    assert markers("SOLUCIÓN OFTÁLMICA", ROUTE_MARKERS) == {"oftalmica"}


# --------------------------------------------------------------------------
# Combination signals
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "BRIMONIDINA / TIMOLOL SOLUCIÓN OFTÁLMICA",
        "COMPRIMIDOS RECUBIERTOS 50/500 mg",
        "INHALADOR 160/4,5 mcg",
    ],
)
def test_combination_signals_in_the_name(name):
    assert looks_like_combination(name)


def test_a_ratio_that_repeats_the_unit_is_not_caught_by_name():
    """Known limit, on purpose: "20 mcg/50 mcg" reads like "250 mg/5 mL".

    Widening the ratio pattern to see the unit on both sides would also see
    every syrup's concentration and refuse the whole class. The composition
    gate is what catches these — the registry lists two substances — so the
    name test stays narrow and the refusal happens one check earlier.
    """
    assert not looks_like_combination("SOLUCIÓN 20 mcg/50 mcg")

    rows = [
        row("1", "SYMBICORT SOLUCIÓN 20 mcg/50 mcg", dosage="20 mcg", form="Solución"),
        row("2", "NEUMOTEROL SOLUCIÓN 20 mcg/50 mcg", dosage="20 mcg", form="Solución"),
    ]
    composition = frozenset({"BUDESONIDA", "FORMOTEROL"})
    merges, skipped = plan_merges(rows, {r.registration: composition for r in rows})
    assert merges == []
    assert skipped["combinación de varios principios"] == 2


@pytest.mark.parametrize(
    "name",
    [
        "PARACETAMOL SOLUCIÓN ORAL 100 mg/mL",
        "AMOXICILINA SUSPENSIÓN 250 mg/5 mL",
        "RIVASTIGMINA PARCHE 4,6 mg/24 h",
    ],
)
def test_a_concentration_is_not_a_combination(name):
    """"mg/mL" and "mg/24 h" are one substance measured, not two substances."""
    assert not looks_like_combination(name)


@pytest.mark.parametrize(
    "name",
    [
        "XCOPRI COMPRIMIDOS RECUBIERTOS 50 mg + 100 mg",
        "XCOPRI COMPRIMIDOS RECUBIERTOS 50 mg + 100 mg + 200 mg",
        "PARACETAMOL 500 mg + CAFEÍNA 65 mg COMPRIMIDOS",
        "SOLUCIÓN 20 mcg + 50 mcg",
    ],
)
def test_a_second_strength_after_a_plus_is_refused(name):
    """A row that states two strengths must not merge on the first one.

    `medications.dosage` keeps one strength, so the XCOPRI titration pack —
    one box holding 50 mg, 100 mg and 200 mg tablets — carried `dosage =
    '50 mg'` and grouped with the plain 50 mg pack: same substance, same form,
    same key, a different product at a different price. The slash rules never
    saw it because the pack writes "+", not "/". The same shape names a
    combination whose registry composition is missing.
    """
    assert looks_like_combination(name)


def test_a_titration_pack_does_not_merge_with_a_single_strength_pack():
    CENOBAMATO = frozenset({"CENOBAMATO"})
    rows = [
        row("1", "XCOPRI COMPRIMIDOS RECUBIERTOS 50 mg", dosage="50 mg",
            form="Comprimido"),
        row("2", "XCOPRI COMPRIMIDOS RECUBIERTOS 50 mg + 100 mg", dosage="50 mg",
            form="Comprimido"),
    ]
    merges, skipped = plan_merges(rows, {r.registration: CENOBAMATO for r in rows})
    assert merges == []
    assert skipped["nombre con señal de combinación"] == 1


# --------------------------------------------------------------------------
# Family names: the insulin incident
# --------------------------------------------------------------------------


def test_insulin_is_a_family_even_with_no_longer_form_in_the_data():
    """Actrapid, Insulatard, Humalog and Tresiba are all "INSULINA 100 UI/mL".

    They are regular, NPH, lispro and degludec — different molecules with
    different onset. This exact collapse already reached production.
    """
    assert "INSULINA" in family_substances({"INSULINA"})


def test_a_longer_form_with_a_real_qualifier_makes_a_family():
    assert "TOXINA" in family_substances({"TOXINA", "TOXINA DIFTERICA"})


def test_a_salt_does_not_make_its_base_a_family():
    """`LOSARTÁN POTÁSICO` is still losartan; refusing it would merge nothing."""
    families = family_substances({"LOSARTAN", "LOSARTAN POTASICO"})
    assert "LOSARTAN" not in families
    families = family_substances({"BETAMETASONA", "BETAMETASONA ACETATO"})
    assert "BETAMETASONA" not in families


def test_normalize_substance_folds_accents_and_case():
    assert normalize_substance("Rivaroxabán") == "RIVAROXABAN"
    assert normalize_substance("  ácido   valproico ") == "ACIDO VALPROICO"


# --------------------------------------------------------------------------
# Survivor choice
# --------------------------------------------------------------------------


def test_a_real_registration_wins_over_a_bigger_link_count():
    """The ISP row is the one the registry vouches for."""
    registered = row("a", "VIAGRA", registration="F-806/23", product_count=1)
    orphan = row("b", "SILDENAFIL GENÉRICO", registration="sin-registro", product_count=99)
    assert choose_survivor([orphan, registered]) is registered


def test_among_registered_rows_the_most_linked_one_wins():
    """Every other choice is more UPDATEs and more listings that change name."""
    few = row("a", "ALFIN", product_count=1)
    many = row("b", "SILDENAFIL", product_count=14)
    assert choose_survivor([few, many]) is many


def test_the_choice_is_deterministic_when_everything_ties():
    first = row("aaa", "UNO")
    second = row("bbb", "DOS")
    assert choose_survivor([first, second]) is choose_survivor([second, first])


# --------------------------------------------------------------------------
# plan_merges — what is merged
# --------------------------------------------------------------------------


def test_bioequivalent_brands_merge():
    """Same substance, strength and form under three brands is one product."""
    rows = [
        row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", product_count=1),
        row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg", product_count=4),
        row("3", "SILDENAFIL COMPRIMIDOS RECUBIERTOS 50 mg", product_count=2),
    ]
    compositions = {r.registration: SILDENAFILO for r in rows}
    merges, skipped = plan_merges(rows, compositions)

    assert len(merges) == 1
    assert members_of(merges[0]) == {"1", "2", "3"}
    assert merges[0].survivor.id == "2"  # most pharmacy_products
    assert not skipped


def test_a_lone_row_is_not_a_group():
    rows = [row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg")]
    merges, _ = plan_merges(rows, {rows[0].registration: SILDENAFILO})
    assert merges == []


# --------------------------------------------------------------------------
# plan_merges — what is refused. Each one is a real failure mode.
# --------------------------------------------------------------------------


def test_a_different_strength_never_merges():
    rows = [
        row("1", "AMLODIPINO COMPRIMIDOS 5 mg", dosage="5 mg"),
        row("2", "AMLOVITAE COMPRIMIDOS 10 mg", dosage="10 mg"),
    ]
    merges, _ = plan_merges(rows, {r.registration: AMLODIPINO for r in rows})
    assert merges == []


def test_a_different_pharmaceutical_form_never_merges():
    rows = [
        row("1", "NISTATINA SUSPENSIÓN 100000 UI", dosage="100000 ui", form="Suspensión"),
        row("2", "NISTATINA ÓVULOS 100000 UI", dosage="100000 ui", form="Óvulo"),
    ]
    merges, _ = plan_merges(rows, {r.registration: NISTATINA for r in rows})
    assert merges == []


def test_a_different_route_never_merges():
    """Nystatin oral suspension was once linked to the vaginal ovule.

    `extract_form` reads both "SOLUCIÓN ORAL" and "SOLUCIÓN VAGINAL" as
    "Solución", so the form column cannot see this on its own.
    """
    rows = [
        row("1", "NISTATINA SOLUCIÓN ORAL 100000 UI", dosage="100000 ui", form="Solución"),
        row("2", "NISTATINA SOLUCIÓN VAGINAL 100000 UI", dosage="100000 ui", form="Solución"),
    ]
    merges, _ = plan_merges(rows, {r.registration: NISTATINA for r in rows})
    assert merges == []


def test_a_sublingual_tablet_does_not_merge_with_a_swallowed_one():
    """Regression: the plural "SUBLINGUALES" used to be invisible to the key."""
    rows = [
        row("1", "SYNDOL COMPRIMIDOS RECUBIERTOS 10 mg", dosage="10 mg"),
        row("2", "BURTEN SL COMPRIMIDOS SUBLINGUALES 10 mg", dosage="10 mg"),
    ]
    merges, _ = plan_merges(rows, {r.registration: KETOROLACO for r in rows})
    assert merges == []


def test_an_orodispersible_tablet_does_not_merge_with_a_film_coated_one():
    """Regression: "BUCODISPERSABLES" used to be invisible too.

    ZYPREXA ZYDIS is not ZYPREXA: different onset, different price.
    """
    rows = [
        row("1", "ZYPREXA COMPRIMIDOS RECUBIERTOS 5 mg", dosage="5 mg"),
        row("2", "ZYPREXA ZYDIS COMPRIMIDOS BUCODISPERSABLES 5 mg", dosage="5 mg"),
    ]
    merges, _ = plan_merges(rows, {r.registration: frozenset({"OLANZAPINA"}) for r in rows})
    assert merges == []


def test_modified_release_does_not_merge_with_immediate_release():
    rows = [
        row("1", "METFORMINA COMPRIMIDOS RECUBIERTOS 500 mg", dosage="500 mg"),
        row(
            "2",
            "GLIFORTEX XR COMPRIMIDOS DE LIBERACIÓN PROLONGADA 500 mg",
            dosage="500 mg",
        ),
    ]
    merges, _ = plan_merges(rows, {r.registration: METFORMINA for r in rows})
    assert merges == []


def test_a_different_pack_size_never_merges():
    rows = [
        row("1", "PARACETAMOL COMPRIMIDOS 500 mg X 16", dosage="500 mg"),
        row("2", "GENIOL COMPRIMIDOS 500 mg X 20", dosage="500 mg"),
    ]
    merges, _ = plan_merges(rows, {r.registration: frozenset({"PARACETAMOL"}) for r in rows})
    assert merges == []


def test_a_combination_is_never_merged():
    """`Concor AM` carries bisoprolol and amlodipino; `dosage` keeps one side.

    Two combinations of the same actives in different ratios are
    indistinguishable here, so the whole class is refused.
    """
    rows = [
        row("1", "CONCOR AM COMPRIMIDOS 5 mg", dosage="5 mg"),
        row("2", "BISOAMLO COMPRIMIDOS 5 mg", dosage="5 mg"),
    ]
    merges, skipped = plan_merges(rows, {r.registration: BISOPROLOL_AMLODIPINO for r in rows})
    assert merges == []
    assert skipped["combinación de varios principios"] == 2


def test_a_family_substance_is_never_merged():
    rows = [
        row("1", "ACTRAPID HM SOLUCIÓN INYECTABLE 100 UI/mL", dosage="100 ui/ml", form="Solución"),
        row("2", "HUMALOG SOLUCIÓN INYECTABLE 100 UI/mL", dosage="100 ui/ml", form="Solución"),
    ]
    merges, skipped = plan_merges(rows, {r.registration: INSULINA for r in rows})
    assert merges == []
    assert skipped["principio es una familia de moléculas"] == 2


def test_a_row_with_no_composition_is_never_merged():
    """No registry entry means no evidence, and no evidence means no merge."""
    rows = [
        row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg"),
        row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg"),
    ]
    merges, skipped = plan_merges(rows, {})
    assert merges == []
    assert skipped["sin composición en el registro ISP"] == 2


def test_a_row_with_no_readable_strength_is_never_merged():
    rows = [
        row("1", "AMLODIPINO COMPRIMIDOS", dosage=""),
        row("2", "AMLOVITAE COMPRIMIDOS", dosage=""),
    ]
    merges, skipped = plan_merges(rows, {r.registration: AMLODIPINO for r in rows})
    assert merges == []
    assert skipped["sin dosis médica"] == 2


def test_a_row_with_no_form_is_never_merged():
    rows = [
        row("1", "AMLODIPINO 5 mg", dosage="5 mg", form=""),
        row("2", "AMLOVITAE 5 mg", dosage="5 mg", form=""),
    ]
    merges, skipped = plan_merges(rows, {r.registration: AMLODIPINO for r in rows})
    assert merges == []
    assert skipped["sin forma farmacéutica"] == 2


def test_a_combination_signal_in_the_name_is_refused_even_with_one_substance():
    """The registry sometimes records only the first substance of a combo."""
    rows = [
        row("1", "BRIMONIDINA / TIMOLOL SOLUCIÓN 0,2 %", dosage="0,2 %", form="Solución"),
        row("2", "COMBIGAN SOLUCIÓN 0,2 %", dosage="0,2 %", form="Solución"),
    ]
    merges, skipped = plan_merges(rows, {r.registration: frozenset({"BRIMONIDINA"}) for r in rows})
    assert merges == []
    assert skipped["nombre con señal de combinación"] == 1


# --------------------------------------------------------------------------
# What the survivor inherits
# --------------------------------------------------------------------------


def test_barcodes_are_unioned_and_the_prescription_flag_is_or_ed():
    """An EAN that stops resolving is a link lost, so none may be dropped."""
    survivor = row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", barcodes=("111",), product_count=5)
    loser = row(
        "2",
        "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg",
        barcodes=("111", "222"),
        prescription_required=True,
    )
    merges, _ = plan_merges([survivor, loser], {r.registration: SILDENAFILO for r in (survivor, loser)})

    group = merges[0]
    assert group.survivor.id == "1"
    assert group.barcodes == ["111", "222"]
    assert group.prescription_required is True
    assert group.enriches_survivor


def test_a_group_that_changes_nothing_is_not_written():
    """970 of 972 survivors gain neither a barcode nor a flag.

    Writing them anyway would bump `updated_at` on every one of them against a
    db-f1-micro the scrapers are using, for no change at all.
    """
    rows = [
        row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", prescription_required=True, product_count=2),
        row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg", prescription_required=True),
    ]
    merges, _ = plan_merges(rows, {r.registration: SILDENAFILO for r in rows})
    assert not merges[0].enriches_survivor


# --------------------------------------------------------------------------
# Moving the aliases
# --------------------------------------------------------------------------


def test_an_alias_the_survivor_already_holds_stays_behind():
    """The unique index on (medication_id, normalized_name) forbids the move.

    Forcing it would add no matching power — the survivor already answers to
    that key — so the alias dies with its row instead.
    """
    survivor = row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", product_count=5)
    loser = row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg")
    merges, _ = plan_merges([survivor, loser], {r.registration: SILDENAFILO for r in (survivor, loser)})

    names = {
        "1": [("n1", "sildenafilo 50 mg")],
        "2": [("n2", "sildenafilo 50 mg"), ("n3", "alfin 50 mg")],
    }
    moves, collisions = plan_name_moves(merges, names)

    assert moves == [{"id": "n3", "survivor": "1"}]
    assert collisions == 1


def test_two_losers_carrying_the_same_alias_only_move_it_once():
    rows = [
        row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", product_count=5),
        row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg"),
        row("3", "RIPOL COMPRIMIDOS RECUBIERTOS 50 mg"),
    ]
    merges, _ = plan_merges(rows, {r.registration: SILDENAFILO for r in rows})
    names = {
        "1": [],
        "2": [("n2", "sildenafilo 50 mg")],
        "3": [("n3", "sildenafilo 50 mg")],
    }
    moves, collisions = plan_name_moves(merges, names)

    assert len(moves) == 1
    assert collisions == 1


# --------------------------------------------------------------------------
# The number the exercise exists to move
# --------------------------------------------------------------------------


def test_ambiguity_is_measured_against_the_survivors():
    """A key stops being ambiguous when every holder folds into one row.

    `matcher.py` refuses to auto-link a key held by more than one medication,
    so this count is the whole point of the merge.
    """
    rows = [
        row("1", "VIAGRA COMPRIMIDOS RECUBIERTOS 50 mg", product_count=5),
        row("2", "ALFIN COMPRIMIDOS RECUBIERTOS 50 mg"),
        row("3", "AMLODIPINO COMPRIMIDOS 5 mg", dosage="5 mg"),
        row("4", "AMLOVITAE COMPRIMIDOS 10 mg", dosage="10 mg"),
    ]
    compositions = {
        rows[0].registration: SILDENAFILO,
        rows[1].registration: SILDENAFILO,
        rows[2].registration: AMLODIPINO,
        rows[3].registration: AMLODIPINO,
    }
    merges, _ = plan_merges(rows, compositions)

    name_rows = [
        ("n1", "1", "sildenafilo 50 mg"),
        ("n2", "2", "sildenafilo 50 mg"),   # shared, and both sides merge
        ("n3", "3", "amlodipino"),
        ("n4", "4", "amlodipino"),          # shared, and the doses differ
        ("n5", "1", "viagra 50 mg"),        # held by one row only
    ]
    assert measure_ambiguity(name_rows, merges) == {
        "claves_ambiguas_antes": 2,
        "claves_ambiguas_despues": 1,
        "claves_desambiguadas": 1,
    }


def test_ambiguity_of_an_untouched_catalog_is_unchanged():
    stats = measure_ambiguity([("n1", "1", "k"), ("n2", "2", "k")], [])
    assert stats["claves_ambiguas_antes"] == 1
    assert stats["claves_desambiguadas"] == 0
