"""Import the medication catalog from the tu-farmacia pharmacy system.

tu-farmacia is a pharmacy management system (POS + stock) whose `products`
table is a curated Chilean medication catalog: commercial name, active
ingredient, laboratory, therapeutic action and prescription type, plus ~39k
barcodes in `product_barcodes`.

FarmaciaCompare needs exactly that. Without a catalog, scraped products cannot
be grouped across chains, and the three chains that publish no barcode
(Cruz Verde, Salcobrand, Dr. Simi) cannot be matched at all.

Input is a `pg_dump` produced by `gcloud sql export sql`, so the live database
is never touched. Usage:

    python -m src.tufarmacia_importer /path/to/dump.sql
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from dataclasses import dataclass, field

from loguru import logger

# `\N` is how pg_dump writes NULL inside COPY blocks.
NULL = r"\N"

COPY_RE_TEMPLATE = r"COPY public\.{table} \(([^)]*)\) FROM stdin;\n(.*?)\n\\\.\n"

# "PARACETAMOL 500 MG", "AMOXICILINA 500MG/5ML", "ELITIRAN 15MG/ML"
# The denominator amount is optional: "15 mg/ml" is a concentration, and dropping
# the "/ml" would turn it into an absolute dose — a different drug strength.
DOSAGE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(mg|mcg|g|ml|ui|%)"
    r"(?:\s*/\s*(\d+(?:[.,]\d+)?)?\s*(mg|ml|g))?",
    re.IGNORECASE,
)

# Keys are matched as whole words after normalisation (see extract_form), so the
# real abbreviations the catalog uses have to be listed explicitly: the dump
# writes "500MG.16COM.", "30CAP.", "SUSP.P/GOTAS", "OFT".
FORM_KEYWORDS = {
    "comprimido": "Comprimido",
    "comprimidos": "Comprimido",
    "comp": "Comprimido",
    "com": "Comprimido",
    "capsula": "Cápsula",
    "capsulas": "Cápsula",
    "caps": "Cápsula",
    "cap": "Cápsula",
    "jarabe": "Jarabe",
    "jbe": "Jarabe",
    "suspension": "Suspensión",
    "susp": "Suspensión",
    "solucion": "Solución",
    "sol": "Solución",
    "gotas": "Gotas",
    "crema": "Crema",
    "unguento": "Ungüento",
    "gel": "Gel",
    "inyect": "Inyectable",
    "ampolla": "Ampolla",
    "spray": "Spray",
    "aerosol": "Aerosol",
    "polvo": "Polvo",
    "ovulo": "Óvulo",
    "supositorio": "Supositorio",
    "parche": "Parche",
    "oft": "Solución oftálmica",
    "shampoo": "Shampoo",
}


@dataclass
class CatalogProduct:
    external_id: str
    name: str
    active_ingredient: str | None
    laboratory: str | None
    therapeutic_action: str | None
    prescription_required: bool
    presentation: str | None
    barcodes: list[str] = field(default_factory=list)


def parse_copy_block(dump: str, table: str) -> tuple[list[str], list[list[str]]]:
    """Return (columns, rows) for one COPY block of a pg_dump."""
    match = re.search(COPY_RE_TEMPLATE.format(table=table), dump, re.S)
    if not match:
        return [], []
    columns = [c.strip() for c in match.group(1).split(",")]
    body = match.group(2)
    rows = [line.split("\t") for line in body.split("\n") if line]
    return columns, rows


def clean(value: str | None) -> str | None:
    if value is None or value == NULL:
        return None
    value = value.strip()
    return value or None


# A decimal separator between two digits: Chilean names use the comma
# ("0,05 %"), the dump also carries dots ("0.5%"). Both are folded to a dot and
# kept, so the number survives as one token.
_DECIMAL_SEP_RE = re.compile(r"(?<=\d)[.,](?=\d)")
# "50/12,5" (losartán + hidroclorotiazida) is one combo strength, not two
# numbers. Only a slash flanked by digits qualifies: in "SUSP.P/GOTAS" the
# slash is ordinary punctuation and has to keep collapsing to a space, or the
# form keyword "gotas" stops being a word.
_COMBO_SLASH_RE = re.compile(r"(?<=\d)\s*/\s*(?=\d)")

# Parked out of reach of the punctuation sweep, then restored.
_DOT, _PCT, _SLASH = "\x00", "\x01", "\x02"
_SWEEP_RE = re.compile(f"[^a-z0-9{_DOT}{_PCT}{_SLASH}]+")
# Split digits from the letters that follow, and the same after a percent sign
# so "1%CR" becomes "1% cr" and the strength is still readable.
_SPLIT_RE = re.compile(f"(?<=[0-9{_PCT}])(?=[a-z])")


def normalize_name(name: str) -> str:
    """Lowercase, strip accents and collapse punctuation for matching.

    Digits are split from trailing letters so that "400mg" and "400 mg" produce
    the same key — chains write dosages both ways, and without this the two
    spellings never match each other.

    Three characters survive the punctuation sweep because they are part of a
    number rather than separators around it: the decimal point, the `%` sign,
    and a slash between two digits. Collapsing them shattered every fractional
    strength — "clobetasol 0,05%" keyed as "clobetasol 0 05", where no dosage
    parser can see a strength any more, so the row could never agree on dose
    with a scraped title. This mirrors what `scraper/src/product_identity.py`
    already keeps on the pharmacy side; the two normalisers have to agree on
    what counts as a number or the keys never meet.

    A Chilean thousands separator ("100.000 UI") is therefore read as a decimal
    and both sides end up calling it 100 ui. That is deliberate: the scraper
    already does exactly this to the pharmacy title, so the two keys still meet
    and "NISTATINA 100.000 UI" links to "Nistatina 100.000UI". Splitting it
    instead ("100 000") is what the old key did, and it matched nothing at all.
    """
    import unicodedata

    decomposed = unicodedata.normalize("NFD", name.lower())
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")

    parked = _DECIMAL_SEP_RE.sub(_DOT, stripped)
    parked = _COMBO_SLASH_RE.sub(_SLASH, parked)
    parked = parked.replace("%", _PCT)

    swept = _SWEEP_RE.sub(" ", _SPLIT_RE.sub(" ", parked))
    restored = swept.replace(_DOT, ".").replace(_SLASH, "/").replace(_PCT, "%")
    return restored.strip()


def extract_dosage(name: str) -> str:
    match = DOSAGE_RE.search(name)
    if not match:
        return ""
    amount, unit = match.group(1), match.group(2).lower()
    denominator_amount, denominator_unit = match.group(3), match.group(4)
    if not denominator_unit:
        return f"{amount} {unit}"
    # "15 mg/ml" (no denominator amount) is still a concentration, and dropping
    # the "/ml" would read as an absolute dose — a different strength entirely.
    if denominator_amount:
        return f"{amount} {unit}/{denominator_amount} {denominator_unit.lower()}"
    return f"{amount} {unit}/{denominator_unit.lower()}"


def extract_form(name: str, presentation: str | None) -> str:
    """Match form keywords on word boundaries.

    A bare substring test mislabels brand names: "cap" matches inside CAPTOPRIL
    (→ "Cápsula") and "gel" inside ANGELIQ (→ "Gel"). Keywords are matched as
    word prefixes instead, so "comp" still catches "comprimidos" but "cap" no
    longer fires inside "captopril".
    """
    haystack = normalize_name(f"{name} {presentation or ''}")
    words = set(haystack.split())
    for keyword, label in FORM_KEYWORDS.items():
        needle = normalize_name(keyword)
        if not needle:
            continue
        if needle in words:
            return label
        # Prefixes are only safe for long keywords: "comprimido" must still catch
        # "comprimidos", but a 3-letter prefix like "cap" would fire inside
        # "captopril" and "gel" inside "angeliq".
        if len(needle) >= 5 and any(word.startswith(needle) for word in words):
            return label
    return presentation or ""


def load_catalog(dump_path: str) -> list[CatalogProduct]:
    dump = open(dump_path, encoding="utf-8", errors="replace").read()

    product_cols, product_rows = parse_copy_block(dump, "products")
    if not product_rows:
        raise SystemExit("No `products` COPY block found — is this the right dump?")

    idx = {name: i for i, name in enumerate(product_cols)}
    products: dict[str, CatalogProduct] = {}

    for row in product_rows:
        if len(row) < len(product_cols):
            continue
        # `active` means "the pharmacy currently stocks it", not "the drug
        # exists". Only 1.550 of 34.166 rows are active, but every row is a
        # valid identity record: name, ingredient and barcode stay useful for
        # matching a listing scraped from any other chain.
        name = clean(row[idx["name"]])
        if not name:
            continue
        prescription = clean(row[idx["prescription_type"]]) or "direct"
        products[row[idx["id"]]] = CatalogProduct(
            external_id=clean(row[idx["external_id"]]) or row[idx["id"]],
            name=name,
            active_ingredient=clean(row[idx["active_ingredient"]]),
            laboratory=clean(row[idx["laboratory"]]),
            therapeutic_action=clean(row[idx["therapeutic_action"]]),
            prescription_required=prescription != "direct",
            presentation=clean(row[idx["presentation"]]),
        )

    barcode_cols, barcode_rows = parse_copy_block(dump, "product_barcodes")
    if barcode_rows:
        b_idx = {name: i for i, name in enumerate(barcode_cols)}
        for row in barcode_rows:
            if len(row) < len(barcode_cols):
                continue
            product = products.get(row[b_idx["product_id"]])
            barcode = clean(row[b_idx["barcode"]])
            if product and barcode and barcode not in product.barcodes:
                product.barcodes.append(barcode)

    logger.info(
        f"Catálogo leído: {len(products)} productos, "
        f"{sum(len(p.barcodes) for p in products.values())} códigos de barras"
    )
    return list(products.values())


def split_ingredients(raw: str | None) -> list[str]:
    """'DORZOLAMIDA  , TIMOLOL' -> ['DORZOLAMIDA', 'TIMOLOL']"""
    if not raw:
        return []
    parts = re.split(r"[,+/]| Y ", raw, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


async def import_catalog(products: list[CatalogProduct], dry_run: bool = False) -> dict:
    from sqlalchemy import text

    from .db import AsyncSessionLocal  # type: ignore[attr-defined]

    stats = {"ingredients": 0, "medications": 0, "names": 0, "skipped": 0}

    async with AsyncSessionLocal() as session:
        existing = await session.execute(text("SELECT name, id FROM active_ingredients"))
        ingredient_ids: dict[str, str] = {n: str(i) for n, i in existing}

        for product in products:
            ingredients = split_ingredients(product.active_ingredient)
            primary = ingredients[0] if ingredients else None

            ingredient_id = None
            if primary:
                ingredient_id = ingredient_ids.get(primary)
                if not ingredient_id:
                    ingredient_id = str(uuid.uuid4())
                    ingredient_ids[primary] = ingredient_id
                    if not dry_run:
                        await session.execute(
                            text("""
                                INSERT INTO active_ingredients (id, name, created_at)
                                VALUES (:id, :name, NOW())
                                ON CONFLICT (name) DO NOTHING
                            """),
                            {"id": ingredient_id, "name": primary},
                        )
                    stats["ingredients"] += 1

            medication_id = str(uuid.uuid4())
            normalized = normalize_name(product.name)
            if not normalized:
                stats["skipped"] += 1
                continue

            if dry_run:
                stats["medications"] += 1
                continue

            await session.execute(
                text("""
                    INSERT INTO medications (
                        id, name, active_ingredient_id, dosage, pharmaceutical_form,
                        prescription_required, isp_registration, barcodes,
                        therapeutic_action, laboratory, created_at, updated_at
                    )
                    VALUES (
                        :id, :name, :ingredient_id, :dosage, :form,
                        :prescription, :external_id, :barcodes,
                        :therapeutic_action, :laboratory, NOW(), NOW()
                    )
                """),
                {
                    "id": medication_id,
                    "name": product.name,
                    "ingredient_id": ingredient_id,
                    "dosage": extract_dosage(product.name),
                    "form": extract_form(product.name, product.presentation),
                    "prescription": product.prescription_required,
                    "external_id": product.external_id,
                    "barcodes": product.barcodes,
                    "therapeutic_action": product.therapeutic_action,
                    "laboratory": product.laboratory,
                },
            )
            stats["medications"] += 1

            # The commercial name is what the matcher compares against.
            await session.execute(
                text("""
                    INSERT INTO medication_names (
                        id, medication_id, name, name_type, laboratory,
                        normalized_name, created_at
                    )
                    VALUES (:id, :mid, :name, 'commercial', :lab, :normalized, NOW())
                    ON CONFLICT (medication_id, normalized_name) DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "mid": medication_id,
                    "name": product.name,
                    "lab": product.laboratory,
                    "normalized": normalized,
                },
            )
            stats["names"] += 1

            # A generic alias ("paracetamol 500 mg") lets branded listings from
            # one chain match unbranded listings from another.
            if primary:
                generic = normalize_name(f"{primary} {extract_dosage(product.name)}")
                if generic and generic != normalized:
                    await session.execute(
                        text("""
                            INSERT INTO medication_names (
                                id, medication_id, name, name_type, laboratory,
                                normalized_name, created_at
                            )
                            VALUES (:id, :mid, :name, 'generic', NULL, :normalized, NOW())
                            ON CONFLICT (medication_id, normalized_name) DO NOTHING
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "mid": medication_id,
                            "name": f"{primary} {extract_dosage(product.name)}".strip(),
                            "normalized": generic,
                        },
                    )
                    stats["names"] += 1

            if stats["medications"] % 2000 == 0:
                await session.commit()
                logger.info(f"Importados {stats['medications']} medicamentos…")

        if not dry_run:
            await session.commit()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", help="Path to the tu-farmacia pg_dump .sql file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    products = load_catalog(args.dump)
    stats = asyncio.run(import_catalog(products, dry_run=args.dry_run))
    logger.info(f"Import terminado: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
