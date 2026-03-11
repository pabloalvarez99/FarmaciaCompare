import re
from unidecode import unidecode

FORM_MAP = [
    (r"\bcomp(rimidos?)?\b", "comprimido"),
    (r"\bcápsulas?\b|\bcapsulas?\b|\bcaps?\b", "capsula"),
    (r"\bjarabe\b|\bjbe\b", "jarabe"),
    (r"\bsoluci[oó]n\b|\bsol\b", "solucion"),
    (r"\binyectable\b|\biny\b|\bampolla[s]?\b", "inyectable"),
    (r"\bcrema\b", "crema"),
    (r"\bgel\b", "gel"),
    (r"\bcolirio\b", "colirio"),
    (r"\bsupositorio\b", "supositorio"),
    (r"\bparche\b", "parche"),
    (r"\bpolvo\b", "polvo"),
    (r"\bsuspensi[oó]n\b|\bsusp\b", "suspension"),
    (r"\baerosol\b|\bespray\b", "spray"),
]

DOSAGE_PATTERN = re.compile(
    r"(\d+(?:[.,]\d+)?)(?:\s*)(mcg|µg|mg|g|ml|%|ui|iu)",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, remove trademark symbols, collapse spaces."""
    name = name.strip()
    name = re.sub(r"[®™©]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.lower()


def normalize_ingredient_name(name: str) -> str:
    """For fuzzy matching — also remove accents via unidecode."""
    return unidecode(normalize_name(name))


def extract_dosage(text: str) -> str | None:
    """Extract first dosage from medication name. Returns '500mg', '1g', '1%', etc."""
    match = DOSAGE_PATTERN.search(text)
    if not match:
        return None
    number = match.group(1).replace(",", ".")
    unit = match.group(2).lower()
    return f"{number}{unit}"


def extract_pharmaceutical_form(text: str) -> str:
    """Detect pharmaceutical form from product name text."""
    lower = text.lower()
    for pattern, form in FORM_MAP:
        if re.search(pattern, lower):
            return form
    return "otro"
