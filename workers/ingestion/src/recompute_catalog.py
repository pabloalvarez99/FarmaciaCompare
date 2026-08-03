"""Recompute derived catalog fields in place.

`dosage`, `pharmaceutical_form` and `medication_names.normalized_name` are all
derived from the product name by functions that had four bugs when the catalog
was first imported:

  - `extract_form` matched keywords as bare substrings, so CAPTOPRIL became a
    "Cápsula" and ANGELIQ a "Gel".
  - `extract_dosage` dropped a denominator with no digits, turning the
    concentration "15 mg/ml" into the absolute dose "15 mg".
  - `normalize_name` left "400mg" glued, so it never keyed the same as "400 MG"
    and half the brand ↔ generic matches could not happen.
  - `normalize_name` swept away the decimal separator and the `%` sign, so
    "clobetasol 0,05%" keyed as "clobetasol 0 05" — a strength no dosage parser
    can read, which made every fractional-strength row unable to agree on dose
    with a scraped title.

Re-importing would duplicate rows and orphan the `medication_id` links already
written onto scraped products, so the fields are recomputed in place instead.

    python -m src.recompute_catalog --dry-run   # count what would change
    python -m src.recompute_catalog

Only rows whose value actually changes are written: the fixes touch a small
slice of the catalog, and the database is a db-f1-micro shared with the
scrapers. Writes go out in batches through one executemany per batch rather
than one round trip per row.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from loguru import logger
from sqlalchemy.exc import IntegrityError

from .db import AsyncSessionLocal  # type: ignore[attr-defined]
from .tufarmacia_importer import extract_dosage, extract_form, normalize_name

BATCH = 500

# `medications.id` and `medication_names.id` are text columns holding a uuid
# string, so the parameter is bound as-is with no cast.
UPDATE_MEDICATION = """
    UPDATE medications
    SET dosage = :dosage, pharmaceutical_form = :form, updated_at = NOW()
    WHERE id = :id
"""

UPDATE_NAME = """
    UPDATE medication_names
    SET normalized_name = :value
    WHERE id = :id
"""


def plan_name_updates(
    rows: list[tuple[str, str, str, str]],
) -> tuple[list[dict], list[str]]:
    """Decide which `medication_names` rows can safely take their new key.

    `rows` are `(id, medication_id, name, normalized_name)`.

    A unique index covers (medication_id, normalized_name), so two aliases of
    the same medication cannot converge on one key — and the fixes do make them
    converge, because "clobetasol 0,05 %" and "clobetasol 0.05 %" used to
    differ and no longer do. Such a row is dropped from the plan and keeps its
    old key: a duplicate key would add no matching power, and deleting rows
    from a live catalog to make room for one is not worth it.

    Rows can also want to swap keys with each other. The plan is replayed until
    it stops making progress so a swap resolves in the following pass; a true
    cycle is left alone.
    """
    by_medication: dict[str, list[tuple[str, str, str]]] = {}
    for name_id, medication_id, raw_name, normalized in rows:
        by_medication.setdefault(medication_id, []).append(
            (name_id, raw_name or "", normalized or "")
        )

    updates: list[dict] = []
    skipped: list[str] = []
    for group in by_medication.values():
        held = {current: name_id for name_id, _raw, current in group}
        pending = [
            (name_id, normalize_name(raw), current)
            for name_id, raw, current in group
            if normalize_name(raw) != current
        ]
        while pending:
            progressed = []
            for name_id, target, current in pending:
                owner = held.get(target)
                if owner is not None and owner != name_id:
                    progressed.append((name_id, target, current))
                    continue
                held.pop(current, None)
                held[target] = name_id
                updates.append({"id": name_id, "value": target})
            if len(progressed) == len(pending):
                skipped.extend(name_id for name_id, _t, _c in progressed)
                break
            pending = progressed
    return updates, skipped


async def _write(session, statement: str, rows: list[dict], label: str) -> None:
    """Apply `rows` in batches, degrading to row-by-row only where needed.

    `plan_name_updates` already removes the collisions it can see, but a unique
    index is checked as each row is written rather than at end of statement, so
    a batch can still trip over an intermediate state the final state does not
    have. Such a batch is retried row by row and the offending rows are left as
    they are.
    """
    from sqlalchemy import text

    stmt = text(statement)
    written = skipped = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start : start + BATCH]
        try:
            await session.execute(stmt, chunk)
            await session.commit()
            written += len(chunk)
        except IntegrityError:
            await session.rollback()
            for row in chunk:
                try:
                    await session.execute(stmt, row)
                    await session.commit()
                    written += 1
                except IntegrityError:
                    await session.rollback()
                    skipped += 1
                    logger.warning(f"{label}: colisión, fila sin tocar: {row['id']}")
        logger.info(f"  {label}: {written}/{len(rows)}")
    if skipped:
        logger.warning(f"{label}: {skipped} filas sin tocar por colisión")


async def recompute(dry_run: bool = False) -> dict[str, int]:
    from sqlalchemy import text

    stats = {
        "medications_scanned": 0,
        "medications_changed": 0,
        "names_scanned": 0,
        "names_changed": 0,
        "names_skipped": 0,
    }

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text("SELECT id, name, dosage, pharmaceutical_form FROM medications")
            )
        ).fetchall()
        stats["medications_scanned"] = len(rows)

        med_updates = []
        for medication_id, name, dosage, form in rows:
            new_dosage = extract_dosage(name or "")
            new_form = extract_form(name or "", None)
            if new_dosage == (dosage or "") and new_form == (form or ""):
                continue
            med_updates.append(
                {"id": str(medication_id), "dosage": new_dosage, "form": new_form}
            )
        stats["medications_changed"] = len(med_updates)
        logger.info(
            f"medications: {len(med_updates)} de {len(rows)} cambian "
            f"(dosage / pharmaceutical_form)"
        )

        names = (
            await session.execute(
                text(
                    "SELECT id, medication_id, name, normalized_name FROM medication_names"
                )
            )
        ).fetchall()
        stats["names_scanned"] = len(names)

        name_updates, collisions = plan_name_updates(
            [(str(r[0]), str(r[1]), r[2], r[3]) for r in names]
        )
        stats["names_changed"] = len(name_updates)
        stats["names_skipped"] = len(collisions)
        logger.info(
            f"medication_names: {len(name_updates)} de {len(names)} cambian "
            f"(normalized_name), {len(collisions)} chocan con un alias hermano "
            f"y quedan como están"
        )

        if dry_run:
            logger.info("dry-run: no se escribió nada")
            return stats

        if med_updates:
            await _write(session, UPDATE_MEDICATION, med_updates, "medications")
        if name_updates:
            await _write(session, UPDATE_NAME, name_updates, "medication_names")

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute derived catalog fields")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count the rows that would change without writing",
    )
    args = parser.parse_args()
    logger.info(f"Listo: {asyncio.run(recompute(dry_run=args.dry_run))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
