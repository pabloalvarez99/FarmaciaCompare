"""Multi-signal medication identity matching.

False positives are worse than misses: a wrong link shows the user a price
for a product they will not receive at the pharmacy counter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .product_identity import (
    ProductIdentity,
    _doses_compatible,
    is_medical_dosage,
    looks_cosmetic,
)

_NOISE = frozenset(
    {
        "mg",
        "ml",
        "mcg",
        "g",
        "ui",
        "x",
        "de",
        "con",
        "para",
        "via",
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "b",
        "r",
        "comprimido",
        "comprimidos",
        "capsula",
        "capsulas",
        "tableta",
        "tabletas",
        "jarabe",
        "crema",
        "gel",
        "solucion",
        "suspension",
        "inyectable",
        "sobre",
        "gotas",
        "spray",
        "aerosol",
        "recubiertos",
        "recubierto",
        "blanda",
        "blandas",
        "vaginal",
        "vaginales",
        "oral",
        "unidad",
        "unidades",
        "dosis",
        "topica",
        "topico",
        "topicas",
        "topicos",
        "dermico",
        "dermica",
        "dermatologico",
        "dermatologica",
        "masticables",
        "masticable",
        "liberacion",
        "prolongada",
        "frasco",
        "gramos",
        "gramo",
        "polvo",
        "liquida",
        "liquido",
        "microencapsulada",
        # Routes of administration and dosage forms. These describe HOW a drug
        # is given, never WHICH drug it is, so they must not count as the shared
        # brand/ingredient token the hard gate looks for. Leaving them out let
        # any two ophthalmic solutions of the same strength auto-link at 1.00:
        # "Oftol Loteprednol 0,5% Solución Oftálmica" (a steroid) matched
        # "kaph solucion oftalmica 0.5%" (a lubricant) on the word "oftalmica"
        # alone. Same trap for the other routes.
        "oftalmica",
        "oftalmico",
        "oftalmicas",
        "oftalmicos",
        "otica",
        "otico",
        "oticas",
        "oticos",
        "nasal",
        "nasales",
        "ocular",
        "oculares",
        "unguento",
        "pomada",
        "emulsion",
        "nebulizacion",
        "inhalacion",
        "inhalador",
        "supositorio",
        "supositorios",
        "ovulo",
        "ovulos",
        "parche",
        "parches",
        "ampolla",
        "ampollas",
        "shampoo",
        "champu",
        "locion",
        "pote",
        "sachet",
        "sobres",
    }
)
_HAS_DIGIT = re.compile(r"\d")

# Two ingredient words joined by a slash: "Sacubitrilo / Valsartán",
# "Dexametasona / Tobramicina". Requires letters on both sides so a dose ratio
# ("50/12,5") and a unit ("mg/mL") are not mistaken for a combination.
_COMBINATION_RE = re.compile(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}\s*/\s*[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}")


def _ingredient_vocabulary(names: list[str]) -> frozenset[str]:
    """First word of each ingredient name, long enough to be distinctive.

    `active_ingredients` holds rows like `AMLODIPINO  5mg` and `AMLODIPINO`, so
    only the leading word is kept. Short entries are discarded: `A`, `DHA`,
    `IODO` and `SOJA` are real rows, and matching them as plain words would
    label a large share of the catalogue a combination.
    """
    vocabulary: set[str] = set()
    for name in names:
        words = ProductIdentity.from_name(name).normalized.split()
        if words and len(words[0]) >= 6:
            vocabulary.add(words[0])
    return frozenset(vocabulary)


def _is_combination(text: str | None, known_ingredients: frozenset[str] | None = None) -> bool:
    """True when the title names two or more active ingredients.

    The slash form is the easy half. The hard half is a combination written
    without any punctuation at all — `Micardis Amlo Telmisartan 80 mg` is
    telmisartán *and* amlodipino, `Dutamsuvitae Dutasterida 0,5 mg Tamsulosina
    0,4 mg` is two drugs in one capsule. Both used to read as single-ingredient
    products and could link onto one of their components, pricing a two-drug
    box as if it were the cheaper single.

    Punctuation cannot decide this: in this catalogue `+` is overwhelmingly a
    bundle (`SET ESPEJO + PINZA`, `50ML + BODY LOTION`), not a formulation. So
    when the caller supplies the ingredient vocabulary, the test becomes
    "does this title name two different molecules", which is the actual
    question.
    """
    if not text:
        return False
    if _COMBINATION_RE.search(text):
        return True
    if not known_ingredients:
        return False

    tokens = set(ProductIdentity.from_name(text).normalized.split())
    hits = {name for name in known_ingredients if name in tokens}
    if len(hits) < 2:
        return False
    # `dutasterida` and `dutasterida sal` would count twice for one molecule;
    # a shared prefix means one drug written two ways, not two drugs.
    ordered = sorted(hits)
    return any(
        not (a.startswith(b) or b.startswith(a))
        for i, a in enumerate(ordered)
        for b in ordered[i + 1 :]
    )


def _content_tokens(text: str) -> set[str]:
    return {
        t
        for t in text.split()
        if t not in _NOISE and not _HAS_DIGIT.search(t) and len(t) > 2
    }


@dataclass(frozen=True)
class MatchResult:
    medication_id: str
    matched_name: str
    confidence: float
    method: str  # barcode | structured | fuzzy
    grey_zone: bool = False


class DrugMatcher:
    """Match scraped titles against known medication name rows.

    Auto-link requires barcode **or** (medical dose match + shared brand/
    ingredient token + compatible pack + high fuzzy score). Cosmetics and
    non-medicine catalog rows never auto-link by name.
    """

    AUTO_LINK = 0.90
    GREY_LOW = 0.78
    FUZZY_FLOOR = 78.0

    def __init__(
        self,
        candidates: list[dict],
        ingredients: list[str] | None = None,
    ):
        self.candidates: list[dict] = []
        self._by_barcode: dict[str, dict] = {}
        self.names: list[str] = []
        self._identities: list[ProductIdentity] = []
        # Active-ingredient vocabulary, used to spot a combination that carries
        # no punctuation at all ("Micardis Amlo Telmisartan"). Optional so every
        # existing caller and test keeps working: without it the combination
        # gate falls back to the slash form alone, which is what it did before.
        # Short names are dropped — `A`, `IODO` and `SOJA` are real rows in
        # `active_ingredients`, and matching them as words would call half the
        # catalogue a combination.
        self._ingredients: frozenset[str] = _ingredient_vocabulary(ingredients or [])
        # Names shared by more than one medication. Matching one of these is
        # ambiguous *by construction*: the key cannot say which medication it
        # meant, so the link would be an arbitrary pick among equals.
        #
        # This is not hypothetical. `insulina 100 ui ml` is the generic alias of
        # Actrapid, Apidra, Insulatard, Humalog and Tresiba — regular, glulisine,
        # NPH, lispro and degludec insulin. Showing a diabetic the price of a
        # rapid-acting insulin as if it were their basal is not a cosmetic bug.
        # `amlodipino` with no strength at all covers 80 medications, 5 mg and
        # 10 mg alike, which are different products at different prices.
        self._ambiguous: set[str] = set()
        seen_by_name: dict[str, str] = {}
        for c in candidates:
            key = c.get("normalized_name") or c.get("name") or ""
            medication_id = str(c.get("medication_id"))
            first = seen_by_name.setdefault(key, medication_id)
            if first != medication_id:
                self._ambiguous.add(key)

        for c in candidates:
            row = dict(c)
            name = row.get("normalized_name") or row.get("name") or ""
            identity = ProductIdentity.from_name(
                name,
                barcode=row.get("barcode"),
                brand=row.get("brand") or row.get("laboratory"),
            )
            if row.get("dosage") or row.get("pack_count") or row.get("pack_volume_ml"):
                identity = ProductIdentity(
                    raw_name=identity.raw_name,
                    normalized=identity.normalized,
                    dosage=row.get("dosage") or identity.dosage,
                    form=row.get("form") or identity.form,
                    pack_count=row.get("pack_count") or identity.pack_count,
                    pack_volume_ml=row.get("pack_volume_ml") or identity.pack_volume_ml,
                    barcode=identity.barcode,
                    brand=identity.brand,
                )
            # Gates need the real product name, not the alias that matched.
            #
            # A candidate is a row of `medication_names`, and many of those are
            # synthesized generic aliases — "levetiracetam 100 mg" for a product
            # actually called "KOPODEX 100MG.120ML". The alias is what makes a
            # brand find its generic, so matching must keep using it; but it has
            # been stripped of form, pack size and volume, which leaves those
            # fields None and makes every gate that reads them short-circuit.
            # The 300 mL bottle linked to the 120 mL one passed for exactly this
            # reason: `cand.pack_volume_ml` was None, so `query and cand` was
            # False and the volume gate never ran. Match on the alias, judge on
            # the real name.
            full_name = row.get("full_name")
            if full_name:
                real = ProductIdentity.from_name(full_name)
                identity = ProductIdentity(
                    raw_name=identity.raw_name,
                    normalized=identity.normalized,
                    dosage=identity.dosage or real.dosage,
                    form=identity.form or real.form,
                    pack_count=identity.pack_count or real.pack_count,
                    pack_volume_ml=identity.pack_volume_ml or real.pack_volume_ml,
                    barcode=identity.barcode,
                    brand=identity.brand,
                )

            tokens = identity.normalized.split()
            if not identity.dosage and len(tokens) <= 2:
                continue

            row["_identity"] = identity
            self.candidates.append(row)
            self.names.append(identity.normalized)
            self._identities.append(identity)
            if identity.barcode:
                self._by_barcode[identity.barcode] = row

    def match(
        self,
        raw_name: str,
        *,
        barcode: str | None = None,
        brand: str | None = None,
        is_medicine: bool | None = None,
    ) -> MatchResult | None:
        if not raw_name:
            return None

        # Explicit non-medicine from the chain (Shopify product_type, OCAPI
        # c_isMedProduct, etc.) — never fuzzy-link cosmetics into the catalog.
        if is_medicine is False:
            query = ProductIdentity.from_name(raw_name, barcode=barcode, brand=brand)
            if query.barcode and query.barcode in self._by_barcode:
                row = self._by_barcode[query.barcode]
                return MatchResult(
                    medication_id=str(row["medication_id"]),
                    matched_name=row["_identity"].normalized,
                    confidence=1.0,
                    method="barcode",
                )
            return None

        query = ProductIdentity.from_name(raw_name, barcode=barcode, brand=brand)

        if query.barcode and query.barcode in self._by_barcode:
            row = self._by_barcode[query.barcode]
            return MatchResult(
                medication_id=str(row["medication_id"]),
                matched_name=row["_identity"].normalized,
                confidence=1.0,
                method="barcode",
            )

        if not self.names:
            return None

        # Cosmetic / care products without a medical dose: refuse fuzzy path.
        # Almost every documented false positive lived here (leche↔guantes, shampoo).
        if looks_cosmetic(query.normalized) and not is_medical_dosage(query.dosage):
            return None
        if is_medicine is None and not is_medical_dosage(query.dosage):
            # No strength declared → do not invent a catalog link from name alone.
            # Grey-zone review can still be added later with an explicit opt-in.
            if looks_cosmetic(query.normalized) or not query.form:
                return None

        q_content = _content_tokens(query.normalized)
        if brand:
            q_content |= _content_tokens(ProductIdentity.from_name(brand).normalized)

        hits_a = process.extract(
            query.normalized, self.names, scorer=fuzz.token_set_ratio, limit=10
        )
        hits_b = process.extract(
            query.normalized, self.names, scorer=fuzz.WRatio, limit=10
        )
        best_by_idx: dict[int, float] = {}
        for _name, score, idx in hits_a + hits_b:
            best_by_idx[idx] = max(best_by_idx.get(idx, 0.0), float(score))

        best: MatchResult | None = None
        for idx, score in sorted(best_by_idx.items(), key=lambda x: -x[1]):
            if score < self.FUZZY_FLOOR:
                continue
            name = self.names[idx]
            cand = self._identities[idx]

            if query.hard_incompatible(cand):
                continue

            c_content = _content_tokens(cand.normalized)
            shared = q_content & c_content
            # Prefix brand overlap: "panadol" in "panadol advance…"
            if not shared:
                for qt in q_content:
                    for ct in c_content:
                        if qt.startswith(ct) or ct.startswith(qt):
                            if min(len(qt), len(ct)) >= 4:
                                shared = {qt if len(qt) <= len(ct) else ct}
                                break

            # Hard gate: without shared brand/ingredient token, never auto-link.
            if not shared and score < 96:
                continue

            dose_ok = True
            q_med = is_medical_dosage(query.dosage)
            c_med = is_medical_dosage(cand.dosage)
            if q_med:
                if not c_med or not _doses_compatible(query.dosage, cand.dosage):
                    dose_ok = False
                    if score < 96:
                        continue
            elif c_med:
                # Candidate has a medical dose, query does not — refuse.
                dose_ok = False
                if score < 96:
                    continue

            conf = score / 100.0
            if dose_ok and q_med and c_med:
                conf = min(1.0, conf + 0.05)
            if query.form and cand.form and query.form == cand.form:
                conf = min(1.0, conf + 0.03)
            elif query.form and cand.form and query.form != cand.form:
                conf -= 0.12
            if (
                query.pack_count
                and cand.pack_count
                and query.pack_count == cand.pack_count
            ):
                conf = min(1.0, conf + 0.03)
            if (
                query.pack_volume_ml
                and cand.pack_volume_ml
                and query.pack_volume_ml == cand.pack_volume_ml
            ):
                conf = min(1.0, conf + 0.03)
            if shared:
                conf = min(1.0, conf + 0.03 * min(len(shared), 2))
            else:
                conf -= 0.20

            if not dose_ok:
                conf = min(conf, self.AUTO_LINK - 0.06)

            method = (
                "structured"
                if q_med and c_med and dose_ok and shared
                else "fuzzy"
            )
            # Auto-link only when medical dose agrees (or barcode path above).
            grey = (
                conf < self.AUTO_LINK
                or not dose_ok
                or not shared
                or not q_med
            )
            if "cafeina" in query.normalized and "cafeina" not in cand.normalized:
                grey = True
            # An ambiguous key names several medications at once, so no amount
            # of confidence makes the choice between them correct.
            if name in self._ambiguous:
                grey = True
            # A combination drug must not collapse onto one of its components.
            # "Concor AM Bisoprolol Fumarato 5 mg" carries amlodipine as well,
            # and linking it to plain "bisoprolol fumarato 5 mg" would price a
            # two-drug product as if it were the single-ingredient one.
            if _is_combination(query.raw_name, self._ingredients) and not _is_combination(
                cand.raw_name, self._ingredients
            ):
                grey = True
            # Pack size and volume: matching them earns a bonus above, but a
            # *mismatch* used to earn nothing at all — a candidate could win on
            # name similarity while selling a different quantity. That single
            # omission was the largest source of wrong links in production
            # (1.181 of 2.372 audited errors): a 112-nappy pack priced as the
            # 32-nappy one, a 300 mL bottle priced as the 120 mL one. When both
            # sides state a quantity and the quantities differ, it is a
            # different product — no confidence score should override that.
            if (
                query.pack_count
                and cand.pack_count
                and query.pack_count != cand.pack_count
            ):
                grey = True
            if (
                query.pack_volume_ml
                and cand.pack_volume_ml
                and query.pack_volume_ml != cand.pack_volume_ml
            ):
                grey = True
            # Pharmaceutical form is route-adjacent: drops are not effervescent
            # tablets, a lotion is not a gel. Both stated and different means a
            # different product.
            if query.form and cand.form and query.form != cand.form:
                grey = True

            candidate = MatchResult(
                medication_id=str(self.candidates[idx]["medication_id"]),
                matched_name=name,
                confidence=round(max(0.0, conf), 4),
                method=method,
                grey_zone=grey,
            )
            if best is None or candidate.confidence > best.confidence:
                best = candidate

        if best is None or best.confidence < self.GREY_LOW:
            return None
        return best

    def should_auto_link(self, result: MatchResult | None) -> bool:
        if not result or result.grey_zone:
            return False
        return result.confidence >= self.AUTO_LINK

    def match_all(self, raw_names: list[str]) -> dict[str, MatchResult | None]:
        return {name: self.match(name) for name in raw_names}
