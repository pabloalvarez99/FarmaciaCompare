"""Parse structured identity signals from Chilean pharmacy product titles.

Used by DrugMatcher so dose/form/pack disagreements hard-reject fuzzy matches.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from unidecode import unidecode

FORM_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcomp(rimidos?)?\b|\btabletas?\b|\btabs?\b|\bgrageas?\b|\bcom\b", re.I), "comprimido"),
    (re.compile(r"\bc[aá]psulas?\b|\bcaps?\b|\bcap\b", re.I), "capsula"),
    (re.compile(r"\bjarabe\b|\bjbe\b", re.I), "jarabe"),
    # Injectable outranks the physical state on purpose. "SOLUCIÓN INYECTABLE"
    # and "Ampolla" are the same presentation, but with `solucion` matching first
    # they resolved to different forms and the gate cut the link — 124 of them.
    # The route is the identifying trait; solution/suspension is how it is
    # carried. Whatever else the label says, an injectable is an injectable.
    (re.compile(r"\binyectable\b|\biny\b|\bampolla[s]?\b", re.I), "inyectable"),
    (re.compile(r"\bsoluci[oó]n\b", re.I), "solucion"),
    (re.compile(r"\bcrema\b", re.I), "crema"),
    (re.compile(r"\bgel\b", re.I), "gel"),
    (re.compile(r"\bcolirio\b", re.I), "colirio"),
    (re.compile(r"\bsupositorio\b", re.I), "supositorio"),
    (re.compile(r"\bparche\b", re.I), "parche"),
    (re.compile(r"\bpolvo\b", re.I), "polvo"),
    (re.compile(r"\bsuspensi[oó]n\b|\bsusp\b", re.I), "suspension"),
    (re.compile(r"\baerosol\b|\bespray\b|\bspray\b", re.I), "spray"),
    (re.compile(r"\binhalador\b|\bhfa\b|\bmdi\b|\bdpi\b", re.I), "inhalador"),
    (re.compile(r"\bgotas?\b", re.I), "gotas"),
    (re.compile(r"\bsobres?\b", re.I), "sobre"),
    # Vaginal route. `ov` is how the catalog abbreviates it ("nistatina ov
    # 100000 ui"), and without this the oral suspension of the same drug at the
    # same strength matched the pessary: same molecule, same dose, different
    # route and different product.
    (re.compile(r"\b[oó]vulos?\b|\bov\b|\bpesarios?\b", re.I), "ovulo"),
    (re.compile(r"\bung[uü]ento\b|\bpomada\b|\bung\b", re.I), "unguento"),
    (re.compile(r"\bshampoo\b|\bchamp[uú]\b", re.I), "shampoo"),
    (re.compile(r"\bloci[oó]n\b", re.I), "locion"),
    (re.compile(r"\benjuague\b|\bcolutorio\b", re.I), "enjuague"),
]

# Unit boundary: do NOT use \b after `%` — `%` is non-word so `\b` never
# fires between `%` and space/end, and every percent strength would be lost.
_UNIT_END = r"(?!\w)"

# Concentration first: "100 mg/mL", "100mg/ml" — strength, not pack size.
CONC_RE = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|g|ui|iu)\s*/\s*(ml|g){_UNIT_END}",
    re.IGNORECASE,
)

# Combo strengths: "250/25 mcg", "25/250mcg", "0.3/0.1 %", and Chilean
# tablet combos without unit "20/12,5" (ARB+HCTZ etc.) — default unit mg.
# Must run before single DOSAGE_RE or only the second number is kept.
COMBO_DOSE_RE = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|%)?{_UNIT_END}",
    re.IGNORECASE,
)

# Dual-labeled combo: "0,005 % / Timolol 0,5 %" or "0.3% / 0.1%".
# Unit appears on both sides; optional brand/ingredient words between.
COMBO_LABELED_RE = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|%)\s*/\s*"
    rf"(?:[^\d%]{{0,40}}?)"
    rf"(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|%){_UNIT_END}",
    re.IGNORECASE,
)

# Solid dose units only. Bare "300 ml" is pack volume, never a medical dose.
DOSAGE_RE = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*(mcg|ug|µg|mg|g|%|ui|iu){_UNIT_END}",
    re.IGNORECASE,
)

# Chilean pharmacy titles use decimal comma: "0,5 mg", "0,005 %".
_DECIMAL_COMMA_RE = re.compile(r"(\d),(\d)")

# Compact catalog forms: 25MG.24COM. / 100MG.120ML / 500MG.16COM
COMPACT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mcg|mg|g|ui|ml)"
    r"(?:\.(\d+(?:[.,]\d+)?)\s*(com|comp|cap|caps|ml|un|und)?\.?)?",
    re.IGNORECASE,
)

# x20, x 20, c/20, c-20, 20 comprimidos, 20 comp, 120 dosis / 200ds (inhalers)
#
# The unit list has to cover how the *catalog* writes it, not just how the
# storefronts do. Catalog names are compact — "VITAMINA E 400UI.30 CAP.BLANDAS",
# "NEVINEX 150MG.30CAP." — and a unit that is missing here makes `pack_count`
# return None, which silently disables the pack-size gate in the matcher: the
# guard reads `query.pack_count and cand.pack_count`, so one None lets a 100-unit
# box link to a 30-unit one. Singular `cap`/`com` were the ones missing, and they
# are exactly the catalog's own abbreviations.
# The `x` multiplier must be a standalone token. `[^\d]` used to accept the tail
# of a brand name, so "Tradox 50 mg ... 30 Comprimidos" matched "ox 50" and
# reported a pack of 50 — the *strength*, not the count. Harmless while pack size
# only nudged the score; once it became a hard gate it started blocking correct
# links for every brand ending in x (Tradox, Nefrix, Bisolvax…).
PACK_COUNT_RE = re.compile(
    r"(?:^|[\s(\[,;:/-])(?:x|c/|c-)\s*(\d{1,4})\b"
    r"|\b(\d{1,4})\s*(?:comp|comprimidos|cap|caps|c[aá]psulas|tabs?|tabletas|"
    r"unidades?|und|un|com|dosis|ds|sobres?|ampollas?|[oó]vulos?|parches?|"
    r"grageas?|perlas?|pastillas?|gomitas?|sachets?|jeringas?|agujas?)\b",
    re.IGNORECASE,
)

# Total bottle volume when not part of a concentration numerator.
VOLUME_RE = re.compile(
    r"(?<!/)\b(\d+(?:[.,]\d+)?)\s*m[lL]\b|(?<=\.)(\d+(?:[.,]\d+)?)\s*ML\b",
    re.IGNORECASE,
)

# Non-medicine titles that must never auto-link by fuzzy name.
COSMETIC_RE = re.compile(
    r"\b("
    r"shampoo|acondicionador|desodorante|toalla|toallas|guante|guantes|"
    r"pa[nñ]al|pa[nñ]ales|protector\s+solar|bloqueador|crema\s+dental|"
    r"pasta\s+dental|jab[oó]n|jabon|leche\s+en\s+polvo|formula\s+infantil|"
    r"pañuelo|pañuelos|algod[oó]n|preservativo|condon|condones|"
    r"maquina\s+de\s+afeitar|afeitar|maquillaje|rimel|labial|"
    r"fragancia|perfume|colonia|suavizante|detergente"
    r")\b",
    re.IGNORECASE,
)

NOISE_RE = re.compile(r"[®™©]|[^\w\s/%.-]", re.UNICODE)
SPACE_RE = re.compile(r"\s+")
_MED_DOSE_UNIT = re.compile(r"(mg|mcg|ui|%|/\s*ml|/ml)", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = unidecode(text or "").lower().strip()
    # Preserve decimal commas as dots *before* noise strip, else "0,5 mg"
    # becomes "0 5 mg" and wrongly extracts 5mg.
    text = _DECIMAL_COMMA_RE.sub(r"\1.\2", text)
    text = NOISE_RE.sub(" ", text)
    text = SPACE_RE.sub(" ", text).strip()
    return text


def normalize_dosage(number: str, unit: str) -> str:
    n = float(number.replace(",", "."))
    u = unit.lower().replace("µg", "mcg").replace("ug", "mcg").replace("iu", "ui")
    if n == int(n):
        return f"{int(n)}{u}"
    return f"{n}{u}"


def extract_dosage(text: str) -> str | None:
    """Medical strength only.

    - Concentration ``100 mg/mL`` → ``100mg/ml``
    - Combo ``250/25 mcg`` → ``250/25mcg`` (inhalers / dual actives)
    - Dual-labeled combo ``0,005 % / Timolol 0,5 %`` → ``0.005/0.5%``
    - Solid dose ``500 mg`` → ``500mg``
    - Bare volume ``300 ml`` is **not** a dose (that is pack volume).
    """
    raw = text or ""
    m = CONC_RE.search(raw)
    if m:
        base = normalize_dosage(m.group(1), m.group(2))
        denom = m.group(3).lower()
        return f"{base}/{denom}"

    # Dual-labeled before shared-unit combo so "0.3% / 0.1%" is not partially
    # consumed as a single % dose.
    m = COMBO_LABELED_RE.search(raw)
    if m:
        labeled = _combo_labeled(m)
        if labeled:
            return labeled

    m = COMBO_DOSE_RE.search(raw)
    if m:
        # Keep declaration order: 250/25 ≠ 25/250 (ICS/LABA vs reverse).
        combo = _combo_dose(m)
        if combo:
            return combo

    m = DOSAGE_RE.search(raw)
    if m:
        return normalize_dosage(m.group(1), m.group(2))

    return None


def _norm_unit(unit: str) -> str:
    return unit.lower().replace("µg", "mcg").replace("ug", "mcg")


def _combo_nums(a_raw: str, b_raw: str, unit: str) -> str:
    a = float(a_raw.replace(",", "."))
    b = float(b_raw.replace(",", "."))
    a_s = str(int(a)) if a == int(a) else str(a)
    b_s = str(int(b)) if b == int(b) else str(b)
    return f"{a_s}/{b_s}{unit}"


def _combo_dose(m: re.Match[str]) -> str | None:
    """Normalize ``250/25 mcg`` → ``250/25mcg``; bare ``20/12.5`` → ``20/12.5mg``.

    Bare integer/integer without unit (``1/2``, ``2/3``) is ambiguous pack
    language — skip so DOSAGE_RE can run. Bare with a decimal (``20/12,5``)
    is the Chilean ARB+HCTZ convention and defaults to mg.
    """
    unit_raw = m.group(3)
    if unit_raw:
        unit = _norm_unit(unit_raw)
    else:
        g1, g2 = m.group(1), m.group(2)
        if not ("," in g1 or "." in g1 or "," in g2 or "." in g2):
            return None
        unit = "mg"
    return _combo_nums(m.group(1), m.group(2), unit)


def _combo_labeled(m: re.Match[str]) -> str | None:
    """Normalize ``0,005 % / Timolol 0,5 %`` → ``0.005/0.5%`` when units match."""
    u1 = _norm_unit(m.group(2))
    u2 = _norm_unit(m.group(4))
    if u1 != u2:
        return None
    return _combo_nums(m.group(1), m.group(3), u1)


# An ampoule is usually injectable, but not when the label says the contents are
# swallowed — vitamin D is sold in Chile as drinkable ampoules ("4 ampollas
# solución oral"). Reading those as injectable made them differ from the same
# product written as "solución oral", and the form gate cut a correct link.
_ORAL_AMPOULE_RE = re.compile(
    r"\bampollas?\b.*\b(oral(es)?|bebibles?|gotas?)\b"
    r"|\b(oral(es)?|bebibles?)\b.*\bampollas?\b",
    re.I,
)


def extract_form(text: str) -> str | None:
    raw = text or ""
    if _ORAL_AMPOULE_RE.search(raw):
        return "solucion"
    for pattern, form in FORM_MAP:
        if pattern.search(raw):
            return form
    return None


_COMPACT_SEGMENT_RE = re.compile(r"(?<=[a-zA-ZáéíóúñÁÉÍÓÚÑ])\.(?=\d)")


def _split_compact_segments(text: str) -> str:
    """Turn the catalog's ``400MG.5ML.30ML.`` into ``400MG 5ML 30ML.``.

    The catalog uses ``.`` to separate segments, but the number patterns accept
    it as a decimal point. In ``5ML.30ML`` the volume regex therefore captured
    ``5.30`` as one value, discarded it for not being whole, and fell back to the
    concentration denominator — a 30 mL bottle read as 5 mL. Only a dot sitting
    between a letter and a digit is a separator; ``0.05 %`` and ``2,5 mg`` are
    left alone.
    """
    return _COMPACT_SEGMENT_RE.sub(" ", text or "")


def extract_pack_count(text: str) -> int | None:
    raw = _split_compact_segments(text or "")
    m = PACK_COUNT_RE.search(raw)
    if m:
        val = m.group(1) or m.group(2)
        try:
            n = int(val)
        except (TypeError, ValueError):
            n = None
        if n is not None and 1 <= n <= 5000:
            return n

    # Compact catalog: 25MG.24COM. / 500MG.16COM
    m = re.search(
        r"(?:mg|mcg|g|ui)\.(\d{1,4})\s*(?:com|comp|cap|caps|un|und)\b",
        raw,
        re.IGNORECASE,
    )
    if m:
        n = int(m.group(1))
        if 1 <= n <= 5000:
            return n
    return None


def extract_pack_volume_ml(text: str) -> int | None:
    """Total liquid volume of the sellable unit (bottle), not concentration.

    ``100 mg/mL solucion 300 mL`` → 300
    ``KOPODEX 100MG.120ML`` → 120
    Concentration denominator alone is ignored.
    """
    raw = _split_compact_segments(text or "")
    # Strip concentration segments so their "ml" denominator is not taken as pack.
    stripped = CONC_RE.sub(" ", raw)

    candidates: list[int] = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*m[lL]\b", stripped):
        try:
            n = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if n == int(n) and 1 <= int(n) <= 5000:
            candidates.append(int(n))

    # Compact trailing .120ML after a dose
    m = re.search(r"(?:mg|mcg|g|ui)\.(\d{1,4})\s*ml\b", stripped, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 5000:
            candidates.append(n)

    if not candidates:
        return None
    # Prefer the largest declared volume (total bottle over tiny residual matches).
    return max(candidates)


def is_medical_dosage(dosage: str | None) -> bool:
    """True when dosage is a real drug strength (mg/mcg/ui/%/concentration)."""
    if not dosage:
        return False
    return bool(_MED_DOSE_UNIT.search(dosage))


def looks_cosmetic(text: str) -> bool:
    return bool(COSMETIC_RE.search(text or ""))


def normalize_barcode(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    # EAN-8 / UPC-A / EAN-13 / GTIN-14. Reject short internal SKUs (9 digits
    # that look like barcodes would cross-link unrelated chains).
    if len(digits) in (8, 12, 13, 14):
        return digits
    return None


@dataclass(frozen=True)
class ProductIdentity:
    """Structured view of a product title for matching."""

    raw_name: str
    normalized: str
    dosage: str | None
    form: str | None
    pack_count: int | None
    pack_volume_ml: int | None = None
    barcode: str | None = None
    brand: str | None = None

    @classmethod
    def from_name(
        cls,
        name: str,
        *,
        barcode: str | None = None,
        brand: str | None = None,
    ) -> ProductIdentity:
        normalized = normalize_text(name)
        return cls(
            raw_name=name,
            normalized=normalized,
            dosage=extract_dosage(normalized),
            form=extract_form(normalized),
            pack_count=extract_pack_count(name) or extract_pack_count(normalized),
            pack_volume_ml=extract_pack_volume_ml(name)
            or extract_pack_volume_ml(normalized),
            barcode=normalize_barcode(barcode),
            brand=normalize_text(brand) if brand else None,
        )

    def hard_incompatible(self, other: ProductIdentity) -> bool:
        """True when these cannot be the same sellable presentation."""
        if self.dosage and other.dosage and not _doses_compatible(self.dosage, other.dosage):
            return True
        if self.form and other.form and self.form != other.form:
            return True
        if (
            self.pack_count
            and other.pack_count
            and self.pack_count != other.pack_count
        ):
            # Same drug different pack sizes are different SKUs for price compare.
            return True
        if (
            self.pack_volume_ml
            and other.pack_volume_ml
            and self.pack_volume_ml != other.pack_volume_ml
        ):
            # 300 mL bottle ≠ 120 mL bottle even at same concentration.
            return True
        return False


def _dose_base(dosage: str) -> str:
    """Strip concentration denominator: ``100mg/ml`` → ``100mg``."""
    return dosage.split("/", 1)[0]


def _doses_compatible(a: str, b: str) -> bool:
    """Exact match, or solid dose vs same strength as concentration.

    Catalog rows often say ``100MG.120ML`` (parsed as ``100mg`` + vol 120)
    while pharmacy titles say ``100 mg/mL … 120 mL``. Those are the same
    strength; pack volume still has to agree separately.
    """
    if a == b:
        return True
    return _dose_base(a) == _dose_base(b)
