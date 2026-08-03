"""Merge `medications` rows that are the same product under different brands.

The catalog was built from two sources — the tu-farmacia inventory and the ISP
sanitary registry — and the ISP issues **one registration per commercial
brand**. Sildenafil 50 mg comprimido is therefore 18 rows (ALFIN, DIRTOP,
DISILDEN, ENHORA…), clobetasol 0,05 % is 25, and every one of those rows
carries the same generic alias in `medication_names`. A key shared by more than
one medication is ambiguous *by construction*, and `matcher.py` refuses to
auto-link an ambiguous key because choosing among N equals is a lottery. There
are 3.328 such keys, and the refusal is what dropped Salcobrand from 134 linked
products to 58.

The fix is not to loosen the gate. It is for the catalog to stop holding N rows
for one product.

    python -m src.dedupe_catalog --dry-run     # count and sample, write nothing
    python -m src.dedupe_catalog

## What counts as the same product

Two rows are merged **only** when they agree on every one of:

  - **the active substance**, taken from the ISP registry export rather than
    from `medications.active_ingredient_id` — the registry lists the complete
    composition, the column holds only the first substance;
  - **the strength** (`medications.dosage`), which has to be a real medical
    dose (mg / mcg / g / UI / % / per-mL). A row whose dose could not be parsed
    is never merged: `amlodipino` with no strength names 80 medications, 5 mg
    and 10 mg alike;
  - **the pharmaceutical form**;
  - **the route of administration** named in the product name. `extract_form`
    reads "SOLUCIÓN OFTÁLMICA" and "SOLUCIÓN INYECTABLE" both as "Solución", so
    without this an eye drop would merge with an ampoule;
  - **the release/preparation modifiers** named in the product name
    (prolongada, entérico, efervescente, liofilizado, masticable…). All of them
    collapse to the same `pharmaceutical_form` and none of them is the same
    product: a modified-release tablet is not an immediate-release one.
    Both vocabularies are read in the singular and in the plural, because the
    registry writes "COMPRIMIDOS SUBLINGUALES", not "SUBLINGUAL";
  - **the pack count and pack volume** declared in the name, when declared.

Different brand with all of that equal means bioequivalent, and for comparing
prices those are one product.

## What is refused, and why

Merging too much is worse than not merging. A row is excluded when:

  - **its composition is unknown** — no registry entry, or the export gives
    that registration two different compositions. No evidence, no merge;
  - **it has more than one active substance.** `medications.dosage` keeps only
    one of a combination's strengths, so two combinations with the same actives
    and different ratios look identical here. Refusing them outright is
    cheaper than getting the ratio right, and it is the rule
    "un combo no colapsa sobre un componente" applied at the catalog level;
  - **its substance is a family name rather than a molecule.** `INSULINA` is
    the recorded ingredient of Actrapid (regular), Insulatard (NPH), Humalog
    (lispro) and Tresiba (degludec): same string, same 100 UI/mL, same form,
    pharmacologically different drugs. This already caused a production false
    positive. A substance is treated as a family when the registry also lists a
    longer substance that starts with it plus a qualifier that is not a salt or
    hydrate — `INSULINA ASPARTA` makes `INSULINA` a family, while
    `LOSARTÁN POTÁSICO` leaves `LOSARTÁN` alone;
  - **its name shows a combination signal** — two words joined by a slash
    ("Brimonidina / Timolol") or a dose ratio ("50/500 mg").

The composition check is not decoration: it is what keeps BERODUAL
(ipratropio + fenoterol) out of ATROVENT, the brimonidine+timolol eye drop out
of plain brimonidine, and the lidocaine-solvent ACANTEX out of plain
ceftriaxone. Those groups pass every name-based test.

## How the merge is done

`pharmacy_products.medication_id` is `ON DELETE SET NULL` and
`price_alerts.medication_id` is `ON DELETE CASCADE`, so deleting a loser before
repointing it does not raise — it silently drops ~500 links and any alert. The
order is therefore fixed: move the names, repoint every referencing table,
verify nothing still points at a loser, and only then delete.

`medication_names` has a unique index on `(medication_id, normalized_name)`.
A loser alias whose key the survivor already holds is left where it is and dies
with its row; forcing it in would add no matching power.

The survivor is the row with a real ISP registration, and among those the one
the most `pharmacy_products` already point at — that minimises both the number
of writes and the number of links whose displayed name changes. Barcodes are
unioned onto it, because an EAN that stops resolving is a link lost, and
`prescription_required` is OR-ed, which is the safe direction. That tie-break
reads a live count, so a run started while the scrapers are linking can pick a
different survivor for the same group; the membership of a group does not move.

## What the dry-run reports

`claves_ambiguas_antes` → `claves_ambiguas_despues` is the number the whole
exercise exists to move: how many `normalized_name` keys more than one
medication answers to, and which `matcher.py` therefore refuses to auto-link.
Group and row counts say how much was merged; only this one says whether the
matcher got anything back.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from loguru import logger

from .db import AsyncSessionLocal  # type: ignore[attr-defined]
from .isp_registry_importer import DEFAULT_EXPORT, REGISTRATION_RE, parse_registry

BATCH = 500

# Routes of administration. They are not identity — but a disagreement is proof
# of a different product, and `pharmaceutical_form` cannot see it: "SOLUCIÓN
# OFTÁLMICA", "SOLUCIÓN INYECTABLE" and "SOLUCIÓN ORAL" are all "Solución".
ROUTE_MARKERS = frozenset(
    {
        "oftalmica", "oftalmico", "otica", "otico", "nasal", "vaginal", "rectal",
        "topica", "topico", "oral", "inyectable", "intramuscular", "intravenosa",
        "subcutanea", "dermica", "dermico", "bucal", "sublingual", "inhalatoria",
        "inhalacion", "transdermica", "uretral", "ocular", "auricular", "capilar",
        "dental", "otologica", "peridural", "intratecal", "epidural", "irrigacion",
        "infusion", "nebulizacion",
    }
)

# Release kinetics and preparation. Every one of these collapses into the same
# `pharmaceutical_form`, and none of them is the same sellable product: a
# modified-release metformin is not an immediate-release one and does not cost
# the same.
MODIFIER_MARKERS = frozenset(
    {
        "prolongada", "prolongado", "prolongados", "sostenida", "controlada",
        "retardada", "retard", "modificada", "enterico", "entericos", "enterica",
        "entericas", "gastrorresistente", "gastrorresistentes", "efervescente",
        "efervescentes", "masticable", "masticables", "dispersable", "dispersables",
        "bucodispersable", "orodispersable", "liofilizado", "liofilizada", "polvo",
        "concentrado", "concentrada", "pediatrico", "pediatrica", "infantil",
        "lactantes", "forte", "monodosis", "unidosis", "premezcla", "granulado",
        "granulados", "implante", "autoinyector", "depot", "flexpen", "penfill",
    }
)

# Qualifiers that turn a substance into a salt, ester or hydrate of *itself*.
# `LOSARTÁN POTÁSICO` is still losartan, so `LOSARTÁN` is not a family name.
# `INSULINA ASPARTA` is a different molecule, so `INSULINA` is one.
SALT_QUALIFIERS = frozenset(
    {
        "clorhidrato", "diclorhidrato", "hidrocloruro", "sodico", "sodica",
        "disodico", "disodica", "potasico", "potasica", "monopotasico", "calcico",
        "calcica", "magnesico", "sulfato", "maleato", "tartrato", "bitartrato",
        "hemitartrato", "fumarato", "hemifumarato", "mesilato", "besilato",
        "acetato", "citrato", "nitrato", "fosfato", "difosfato", "trifosfato",
        "succinato", "valerato", "propionato", "dipropionato", "palmitato",
        "estolato", "bromhidrato", "bromuro", "cloruro", "yoduro", "monohidrato",
        "dihidrato", "trihidrato", "pentahidrato", "hexahidrato", "hemipentahidratado",
        "monohidratada", "hidratado", "hidratada", "anhidro", "anhidra", "base",
        "micronizado", "micronizada", "lactato", "gluconato", "estearato", "pamoato",
        "embonato", "napsilato", "tosilato", "oxalato", "malato", "aspartato",
        "glutamato", "benzoato", "salicilato", "undecilato", "undecanoato",
        "enantato", "cipionato", "hemihidrato", "sesquihidrato", "carbonato",
        "bicarbonato", "edisilato", "xinafoato", "furoato", "aceponato", "butirato",
        "caproato", "decanoato", "fenilpropionato", "isopropionato", "trometamol",
        "trometamina", "arginina", "meglumina", "colina", "olamina", "dietilamina",
        "dietilmina", "epolamina", "colestiramina", "bisulfato", "medoxomilo",
        "sintetica", "sintetico", "recombinante", "purificada", "purificado",
        "refinado", "refinada", "activado", "activada",
        # Prepositional salts: "ROSUVASTATINA DE CALCIO".
        "de", "y", "con", "sodio", "potasio", "calcio", "magnesio", "zinc",
    }
)

# Substances that name a therapeutic class, not a molecule, and that the
# prefix rule above cannot see because the registry never spells out a longer
# form of them. Each one is a documented interchangeability hazard.
FAMILY_DENYLIST = frozenset(
    {
        "INSULINA", "VACUNA", "TOXOIDE", "INMUNOGLOBULINA", "SUERO ANTIOFIDICO",
        "TOXINA BOTULINICA", "TOXINA BOTULINICA TIPO A", "ALERGENOS",
        "EXTRACTO ALERGENICO", "PLASMA HUMANO", "FACTOR VIII", "FACTOR IX",
        "HEPARINA", "INTERFERON", "GONADOTROFINA", "GONADOTROPINA",
    }
)

# A real medical strength. A row whose `dosage` is a bare volume ("3 ml") has
# no strength at all and must not be merged on the strength of its name.
MEDICAL_UNIT_RE = re.compile(r"(mg|mcg|ui\b|u\.i|g\b|%|/\s*ml)", re.IGNORECASE)

# Two substances joined by a slash: "Brimonidina / Timolol". Letters on both
# sides, so "mg/mL" and "50/12,5" are not read as a combination here.
COMBINATION_WORDS_RE = re.compile(
    r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}\s*/\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}"
)
# A dose ratio: "50/500 mg", "20 mcg/50 mcg". Two combinations of the same
# actives can differ only here, and `medications.dosage` keeps one side only.
COMBINATION_RATIO_RE = re.compile(r"\d\s*/\s*\d")
# A strength followed by "+": "XCOPRI COMPRIMIDOS RECUBIERTOS 50 mg + 100 mg +
# 200 mg" is a titration pack holding three strengths, and its `dosage` column
# keeps only the first — so it grouped with the plain 50 mg pack, a different
# product at a different price. The same shape also names a combination the
# slash rule cannot see ("PARACETAMOL 500 mg + CAFEÍNA 65 mg"). Either way the
# row states more than one strength and must not be merged on one of them.
COMBINATION_PLUS_RE = re.compile(
    r"\d\s*(?:mg|mcg|ug|g|ui|iu|%)\s*\+", re.IGNORECASE
)

_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")
_PACK_COUNT_RE = re.compile(
    r"(?:^|[^\d])(?:x|c/)\s*(\d{1,4})\b"
    r"|\b(\d{1,4})\s*(?:comp|comprimidos|caps|capsulas|tabs?|tabletas|"
    r"unidades|und|com|dosis)\b",
    re.IGNORECASE,
)
# A concentration denominator, so its "mL" is not read as a bottle size. The
# denominator amount is optional because the ISP writes both "100 mg/mL" and
# "250 mg/5 mL": without it the second form left "5 mL" behind and every
# suspension that does not also name its bottle was keyed as a 5 mL pack.
_CONCENTRATION_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mcg|ug|mg|g|ui|iu|u)\s*/\s*"
    r"(?:\d+(?:[.,]\d+)?\s*)?(?:ml|g)\b",
    re.IGNORECASE,
)
_VOLUME_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*ml\b", re.IGNORECASE)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalize_substance(name: str) -> str:
    """Fold a substance name to one comparable form: no accents, one case."""
    return " ".join(strip_accents(name).upper().split())


@lru_cache(maxsize=None)
def _inflections(vocabulary: frozenset[str]) -> dict[str, str]:
    """Every spelling that names a vocabulary word, mapped back to that word.

    The registry writes the presentation in the plural — "COMPRIMIDOS
    BUCODISPERSABLES", "COMPRIMIDOS SUBLINGUALES", "CÁPSULAS ORALES" — and a
    whole-word test against a singular vocabulary sees none of them. That is
    not a cosmetic miss: it put ZYPREXA ZYDIS (orodispersible) in the same
    group as ZYPREXA (film-coated), BURTEN SL (sublingual ketorolac) with
    swallowed ketorolac, and 20 more like them. Spanish forms the plural with
    "s" after a vowel and "es" after a consonant, so both are registered; the
    nonsense form ("sublinguals") simply never matches a real name.

    Words already in the vocabulary always map to themselves, and the rest are
    added in sorted order, so a vocabulary holding both "prolongado" and
    "prolongados" resolves the same way on every run.
    """
    forms = {word: word for word in vocabulary}
    for word in sorted(vocabulary):
        for plural in (word + "s", word + "es"):
            forms.setdefault(plural, word)
    return forms


def markers(name: str, vocabulary: frozenset[str]) -> frozenset[str]:
    """The vocabulary words present in `name`, matched whole after folding.

    Singular and plural fold to the vocabulary's own spelling, so the result is
    a key on which "SUBLINGUAL" and "SUBLINGUALES" agree — and on which a
    sublingual tablet and a swallowed one still disagree.
    """
    forms = _inflections(vocabulary)
    words = _WORD_SPLIT_RE.split(strip_accents(name).lower())
    return frozenset(forms[w] for w in words if w in forms)


def looks_like_combination(name: str) -> bool:
    return bool(
        COMBINATION_WORDS_RE.search(name or "")
        or COMBINATION_RATIO_RE.search(name or "")
        or COMBINATION_PLUS_RE.search(name or "")
    )


def is_medical_dosage(dosage: str | None) -> bool:
    return bool(dosage) and bool(MEDICAL_UNIT_RE.search(dosage))


def pack_count(name: str) -> int | None:
    match = _PACK_COUNT_RE.search(name or "")
    if not match:
        return None
    value = int(match.group(1) or match.group(2))
    return value if 1 <= value <= 5000 else None


def pack_volume_ml(name: str) -> int | None:
    """Bottle size declared in the name, ignoring concentration denominators."""
    stripped = _CONCENTRATION_RE.sub(" ", name or "")
    volumes = []
    for match in _VOLUME_RE.finditer(stripped):
        amount = float(match.group(1).replace(",", "."))
        if amount == int(amount) and 1 <= amount <= 5000:
            volumes.append(int(amount))
    return max(volumes) if volumes else None


def family_substances(substances: set[str]) -> set[str]:
    """Substance names that stand for a family of molecules, not for one.

    `X` is a family when the same universe also holds `X <qualifier> …` and the
    qualifier is not a salt, hydrate or presentation word. `INSULINA` qualifies
    because `INSULINA ASPARTA` exists; `VANCOMICINA` does not, because the only
    longer form is `VANCOMICINA CLORHIDRATO`, the same molecule as a salt.

    Derived from the data rather than from a hand-written list of drug classes,
    so a family that appears in a future registry export is caught without a
    code change. `FAMILY_DENYLIST` covers the ones the data cannot reveal.
    """
    families = {normalize_substance(name) for name in FAMILY_DENYLIST}
    by_first_word: dict[str, list[str]] = defaultdict(list)
    for name in substances:
        head = name.split(" ", 1)[0]
        by_first_word[head].append(name)

    for name in substances:
        prefix = name + " "
        for other in by_first_word[name.split(" ", 1)[0]]:
            if other == name or not other.startswith(prefix):
                continue
            qualifier = strip_accents(other[len(prefix):]).lower().split()[0]
            qualifier = qualifier.strip("(),.-")
            if not qualifier or not qualifier.isalpha() or len(qualifier) < 3:
                continue
            if qualifier in SALT_QUALIFIERS:
                continue
            families.add(name)
            break
    return families


@dataclass(frozen=True)
class MedicationRow:
    """One `medications` row with the counts needed to pick a survivor."""

    id: str
    name: str
    dosage: str
    form: str
    registration: str | None
    barcodes: tuple[str, ...]
    prescription_required: bool
    product_count: int
    name_count: int


@dataclass
class MergeGroup:
    key: tuple
    survivor: MedicationRow
    losers: list[MedicationRow]

    @property
    def substance(self) -> str:
        return self.key[0]

    @property
    def enriches_survivor(self) -> bool:
        """Whether folding the group in actually changes the survivor's row.

        On today's data it almost never does: every row the merge is allowed to
        touch comes from the ISP registry, and those rows carry no barcode, so
        the union is the survivor's own list 970 times out of 972. Writing them
        anyway would be 970 UPDATEs and 970 `updated_at` bumps against a
        db-f1-micro shared with the scrapers, for no change.
        """
        return (
            self.barcodes != list(self.survivor.barcodes)
            or self.prescription_required != self.survivor.prescription_required
        )

    @property
    def product_count(self) -> int:
        return sum(row.product_count for row in self.losers)

    @property
    def barcodes(self) -> list[str]:
        merged = list(self.survivor.barcodes)
        for row in self.losers:
            for code in row.barcodes:
                if code not in merged:
                    merged.append(code)
        return merged

    @property
    def prescription_required(self) -> bool:
        return self.survivor.prescription_required or any(
            row.prescription_required for row in self.losers
        )


def load_compositions(path: str | Path) -> dict[str, frozenset[str]]:
    """`registration -> substances`, dropping registrations that disagree.

    The export is the only place the *complete* composition lives:
    `medications.active_ingredient_id` holds the first substance of a
    combination and nothing else. A registration listed twice with two
    different compositions is left out — an unresolved reading is not evidence.
    """
    seen: dict[str, set[frozenset[str]]] = defaultdict(set)
    for product in parse_registry(path):
        substances = frozenset(normalize_substance(i) for i in product.ingredients)
        if substances:
            seen[product.registration.upper()].add(substances)

    compositions = {reg: next(iter(v)) for reg, v in seen.items() if len(v) == 1}
    logger.info(
        f"Composición ISP: {len(compositions)} registros con lectura única "
        f"({len(seen) - len(compositions)} descartados por lecturas distintas)"
    )
    return compositions


def choose_survivor(rows: list[MedicationRow]) -> MedicationRow:
    """The row the rest of the group folds into.

    A real sanitary registration first — it is the row the ISP vouches for.
    Then the one the most `pharmacy_products` already point at: every other
    choice means more UPDATEs and more live listings whose displayed name
    changes. Ties fall back to barcodes, aliases and finally the id, so two
    runs on the same data pick the same row.
    """
    return max(
        rows,
        key=lambda r: (
            bool(r.registration and REGISTRATION_RE.match(r.registration)),
            r.product_count,
            len(r.barcodes),
            r.name_count,
            r.id,
        ),
    )


def plan_merges(
    rows: list[MedicationRow],
    compositions: dict[str, frozenset[str]],
) -> tuple[list[MergeGroup], Counter]:
    """Group the catalog into merges, and count what was left out and why."""
    skipped: Counter = Counter()

    eligible: list[tuple[MedicationRow, str]] = []
    for row in rows:
        if not is_medical_dosage(row.dosage):
            skipped["sin dosis médica"] += 1
            continue
        if not row.form:
            skipped["sin forma farmacéutica"] += 1
            continue
        composition = compositions.get((row.registration or "").upper())
        if composition is None:
            skipped["sin composición en el registro ISP"] += 1
            continue
        if len(composition) > 1:
            skipped["combinación de varios principios"] += 1
            continue
        if looks_like_combination(row.name):
            skipped["nombre con señal de combinación"] += 1
            continue
        eligible.append((row, next(iter(composition))))

    families = family_substances({substance for _row, substance in eligible})
    logger.info(f"principios tratados como familia, no como molécula: {len(families)}")

    groups: dict[tuple, list[MedicationRow]] = defaultdict(list)
    for row, substance in eligible:
        if substance in families:
            skipped["principio es una familia de moléculas"] += 1
            continue
        key = (
            substance,
            row.dosage,
            row.form,
            markers(row.name, ROUTE_MARKERS),
            markers(row.name, MODIFIER_MARKERS),
            pack_count(row.name),
            pack_volume_ml(row.name),
        )
        groups[key].append(row)

    merges = []
    for key, members in groups.items():
        if len(members) < 2:
            continue
        survivor = choose_survivor(members)
        merges.append(
            MergeGroup(
                key=key,
                survivor=survivor,
                losers=[r for r in members if r.id != survivor.id],
            )
        )
    merges.sort(key=lambda g: (-len(g.losers), g.substance))
    return merges, skipped


def plan_name_moves(
    merges: list[MergeGroup],
    names_by_medication: dict[str, list[tuple[str, str]]],
) -> tuple[list[dict], int]:
    """Which `medication_names` rows can move to their survivor.

    `names_by_medication` maps a medication id to its `(id, normalized_name)`
    aliases. The unique index on `(medication_id, normalized_name)` means an
    alias the survivor already holds cannot move; it stays on the loser and is
    removed by the cascade when the loser goes. Duplicating a key would add no
    matching power — the survivor already answers to it.
    """
    moves: list[dict] = []
    collisions = 0
    for group in merges:
        held = {key for _id, key in names_by_medication.get(group.survivor.id, [])}
        for loser in group.losers:
            for name_id, key in names_by_medication.get(loser.id, []):
                if key in held:
                    collisions += 1
                    continue
                held.add(key)
                moves.append({"id": name_id, "survivor": group.survivor.id})
    return moves, collisions


def measure_ambiguity(
    name_rows: list[tuple], merges: list[MergeGroup]
) -> dict[str, int]:
    """Count the keys the matcher refuses to use, before and after the merge.

    This is the number the whole exercise exists to move. `matcher.py` will not
    auto-link a `normalized_name` that more than one medication answers to,
    because choosing among N equals is a lottery; a key stops being ambiguous
    exactly when every medication holding it has folded into one survivor.

    Counting it here — from the same `medication_names` snapshot the merge
    plans against — is what turns "972 groups" into evidence about the thing
    that was broken, and it costs no extra query.
    """
    remap = {loser.id: group.survivor.id for group in merges for loser in group.losers}
    holders: dict[str, set[str]] = defaultdict(set)
    for _name_id, medication_id, normalized in name_rows:
        holders[normalized].add(str(medication_id))

    before = after = 0
    for medication_ids in holders.values():
        if len(medication_ids) < 2:
            continue
        before += 1
        if len({remap.get(i, i) for i in medication_ids}) > 1:
            after += 1
    return {
        "claves_ambiguas_antes": before,
        "claves_ambiguas_despues": after,
        "claves_desambiguadas": before - after,
    }


MOVE_NAME = """
    UPDATE medication_names SET medication_id = :survivor WHERE id = :id
"""
# Prisma applies @updatedAt in the client, so a raw UPDATE has to set it here.
REPOINT_PRODUCTS = """
    UPDATE pharmacy_products
    SET medication_id = :survivor, updated_at = NOW()
    WHERE medication_id = :loser
"""
REPOINT_ORDER_ITEMS = """
    UPDATE order_items SET medication_id = :survivor WHERE medication_id = :loser
"""
REPOINT_PRICE_ALERTS = """
    UPDATE price_alerts SET medication_id = :survivor WHERE medication_id = :loser
"""
ENRICH_SURVIVOR = """
    UPDATE medications
    SET barcodes = CAST(:barcodes AS text[]),
        prescription_required = :prescription,
        updated_at = NOW()
    WHERE id = :id
"""
DELETE_MEDICATION = "DELETE FROM medications WHERE id = :id"

SELECT_MEDICATIONS = """
    SELECT m.id, m.name, m.dosage, m.pharmaceutical_form, m.isp_registration,
           m.barcodes, m.prescription_required,
           COALESCE(p.n, 0) AS product_count,
           COALESCE(n.n, 0) AS name_count
    FROM medications m
    LEFT JOIN (
        SELECT medication_id, COUNT(*) AS n FROM pharmacy_products
        WHERE medication_id IS NOT NULL GROUP BY medication_id
    ) p ON p.medication_id = m.id
    LEFT JOIN (
        SELECT medication_id, COUNT(*) AS n FROM medication_names GROUP BY medication_id
    ) n ON n.medication_id = m.id
"""


async def _write(session, statement: str, rows: list[dict], label: str) -> None:
    """Apply `rows` in batches through one `executemany` per batch."""
    from sqlalchemy import text

    if not rows:
        return
    stmt = text(statement)
    for start in range(0, len(rows), BATCH):
        await session.execute(stmt, rows[start : start + BATCH])
        await session.commit()
        logger.info(f"  {label}: {min(start + BATCH, len(rows))}/{len(rows)}")


def report(merges: list[MergeGroup], skipped: Counter, show: int) -> dict[str, int]:
    stats = {
        "grupos": len(merges),
        "filas_fusionadas": sum(len(g.losers) for g in merges),
        "productos_repuntados": sum(g.product_count for g in merges),
        "codigos_de_barra_unidos": sum(
            len(g.barcodes) - len(g.survivor.barcodes) for g in merges
        ),
        "supervivientes_a_enriquecer": sum(1 for g in merges if g.enriches_survivor),
    }
    logger.info(
        f"grupos duplicados: {stats['grupos']} — "
        f"{stats['filas_fusionadas']} filas se fusionan en su superviviente, "
        f"{stats['productos_repuntados']} pharmacy_products se repuntan"
    )
    for reason, count in skipped.most_common():
        logger.info(f"  no elegible — {reason}: {count}")

    for group in merges[:show]:
        substance, dosage, form, routes, modifiers, count, volume = group.key
        detail = f"{substance} | {dosage} | {form}"
        if routes:
            detail += f" | vía {'+'.join(sorted(routes))}"
        if modifiers:
            detail += f" | {'+'.join(sorted(modifiers))}"
        if count:
            detail += f" | {count} u"
        if volume:
            detail += f" | {volume} mL"
        print(f"\n  {len(group.losers) + 1} filas → 1   {detail}")
        print(f"    ✔ {group.survivor.name[:74]}  ({group.survivor.product_count} prod.)")
        for loser in group.losers:
            print(f"      {loser.name[:74]}  ({loser.product_count} prod.)")
    return stats


async def dedupe(
    dry_run: bool = False,
    registry: str | Path = DEFAULT_EXPORT,
    show: int = 20,
) -> dict[str, int]:
    from sqlalchemy import text

    registry = Path(registry)
    if not registry.exists():
        raise SystemExit(
            f"No está el export del ISP en {registry}. Sin la composición completa "
            f"no hay con qué distinguir un combinado de un producto simple, así que "
            f"no se fusiona nada. Descargalo con: python -m src.isp_registry_importer --fetch"
        )
    compositions = load_compositions(registry)

    async with AsyncSessionLocal() as session:
        rows = [
            MedicationRow(
                id=str(r[0]),
                name=r[1] or "",
                dosage=r[2] or "",
                form=r[3] or "",
                registration=r[4],
                barcodes=tuple(r[5] or ()),
                prescription_required=bool(r[6]),
                product_count=int(r[7]),
                name_count=int(r[8]),
            )
            for r in (await session.execute(text(SELECT_MEDICATIONS))).fetchall()
        ]
        logger.info(f"medications: {len(rows)} filas")

        merges, skipped = plan_merges(rows, compositions)
        stats = report(merges, skipped, show)
        if not merges:
            return stats

        loser_ids = {loser.id for group in merges for loser in group.losers}
        name_rows = (
            await session.execute(
                text(
                    "SELECT id, medication_id, normalized_name FROM medication_names"
                )
            )
        ).fetchall()
        names_by_medication: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for name_id, medication_id, normalized in name_rows:
            names_by_medication[str(medication_id)].append((str(name_id), normalized))

        moves, collisions = plan_name_moves(merges, names_by_medication)
        stats["nombres_movidos"] = len(moves)
        stats["nombres_en_colision"] = collisions
        logger.info(
            f"medication_names: {len(moves)} se mueven al superviviente, "
            f"{collisions} chocan con un alias que el superviviente ya tiene "
            f"y se van con su fila"
        )

        stats.update(measure_ambiguity(name_rows, merges))
        logger.info(
            f"claves ambiguas (las que el matcher se niega a usar): "
            f"{stats['claves_ambiguas_antes']} → {stats['claves_ambiguas_despues']} "
            f"({stats['claves_desambiguadas']} dejan de serlo)"
        )

        if dry_run:
            logger.info("dry-run: no se escribió nada")
            return stats

        pairs = [
            {"survivor": group.survivor.id, "loser": loser.id}
            for group in merges
            for loser in group.losers
        ]

        # Order is load-bearing. `pharmacy_products.medication_id` is ON DELETE
        # SET NULL and `price_alerts.medication_id` is ON DELETE CASCADE, so a
        # delete that runs first destroys links and alerts without raising.
        await _write(session, MOVE_NAME, moves, "medication_names")
        await _write(session, REPOINT_PRODUCTS, pairs, "pharmacy_products")
        await _write(session, REPOINT_ORDER_ITEMS, pairs, "order_items")
        await _write(session, REPOINT_PRICE_ALERTS, pairs, "price_alerts")

        # Only the survivors the merge actually changes. The house rule is to
        # write what changes and nothing else; here that is the difference
        # between 2 UPDATEs and 972 on a database the scrapers are using.
        await _write(
            session,
            ENRICH_SURVIVOR,
            [
                {
                    "id": group.survivor.id,
                    "barcodes": group.barcodes,
                    "prescription": group.prescription_required,
                }
                for group in merges
                if group.enriches_survivor
            ],
            "medications (barcodes / receta)",
        )

        # Belt and braces before an irreversible delete: prove that nothing
        # still references a loser, rather than trusting that it does not.
        stragglers = (
            await session.execute(
                text("""
                    SELECT COUNT(*) FROM pharmacy_products
                    WHERE medication_id IN (
                        SELECT unnest(CAST(:ids AS text[]))
                    )
                """),
                {"ids": list(loser_ids)},
            )
        ).scalar()
        if stragglers:
            raise SystemExit(
                f"{stragglers} pharmacy_products siguen apuntando a una fila a borrar. "
                f"No se borra nada."
            )

        await _write(
            session,
            DELETE_MEDICATION,
            [{"id": loser_id} for loser_id in sorted(loser_ids)],
            "medications (borradas)",
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate the medication catalog")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count and sample the merges without writing",
    )
    parser.add_argument(
        "--registry",
        default=str(DEFAULT_EXPORT),
        help="ISP registry export used for the complete composition",
    )
    parser.add_argument(
        "--show", type=int, default=20, help="How many groups to print as a sample"
    )
    args = parser.parse_args()

    stats = asyncio.run(
        dedupe(dry_run=args.dry_run, registry=args.registry, show=args.show)
    )
    logger.info(f"Listo: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
