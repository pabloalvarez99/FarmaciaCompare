"""Remove the product↔catalog links that the audit finds wrong.

`audit_links` measures the damage; this undoes it. Same classifier, so a link is
only cut for a reason that was observed in production — a different strength, a
different pack size, a different route, a combination priced as one of its
components.

**Why cutting is safe.** `medication_id` is derived, not source data: the scrape
is the source of truth and it is untouched. A product with no link is still
scraped, still searchable, still priced — it just is not grouped with others.
That is the correct default state, and `relink` can restore the link later once
the matcher earns it.

**Why cutting is right.** The project's own rule: a wrong link is worse than no
link. It shows someone the price of a medicine that is not theirs. If this tool
cuts a link that was actually fine, the cost is one missing comparison. If it
leaves a wrong one, the cost is a wrong price on a health decision. The risks are
not symmetric.

Links backed by an exact shared EAN are never touched: that is identity, not
heuristic.

    python -m src.clean_bad_links --dry-run    # count and sample, writes nothing
    python -m src.clean_bad_links              # cut them
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter

from loguru import logger

from .audit_links import classify

BATCH = 500


async def clean(dry_run: bool = True, show: int = 12) -> dict:
    from sqlalchemy import text

    from .db import AsyncSessionLocal

    stats: Counter = Counter()
    doomed: list[str] = []
    samples: list[str] = []

    async with AsyncSessionLocal() as session:
        ambiguous = {
            row[0]
            for row in (
                await session.execute(
                    text("""
                        SELECT normalized_name
                        FROM medication_names
                        GROUP BY normalized_name
                        HAVING COUNT(DISTINCT medication_id) > 1
                    """)
                )
            ).fetchall()
        }
        logger.info(f"claves ambiguas en el catálogo: {len(ambiguous)}")

        rows = (
            await session.execute(
                text("""
                    SELECT pp.id, pp.raw_name, m.name, pp.brand, pp.category_id
                    FROM pharmacy_products pp
                    JOIN medications m ON m.id = pp.medication_id
                    WHERE pp.is_active = true
                      -- An exact shared barcode is identity. Never second-guess it.
                      AND NOT (
                        pp.barcode IS NOT NULL
                        AND pp.barcode <> ''
                        AND pp.barcode = ANY(m.barcodes)
                      )
                """)
            )
        ).fetchall()
        logger.info(f"vínculos difusos a revisar: {len(rows)}")

        for product_id, product_name, catalog_name, brand, category_id in rows:
            stats["revisados"] += 1
            finding = classify(product_name, catalog_name, ambiguous, brand, category_id)
            if not finding:
                continue
            stats["cortados"] += 1
            stats[finding.category] += 1
            doomed.append(str(product_id))
            if len(samples) < show:
                samples.append(
                    f"  [{finding.category}] {finding.detail}\n"
                    f"    {finding.product_name[:66]}\n"
                    f"    → {finding.catalog_name[:66]}"
                )

        if not dry_run and doomed:
            for start in range(0, len(doomed), BATCH):
                chunk = doomed[start : start + BATCH]
                await session.execute(
                    text("""
                        UPDATE pharmacy_products
                        SET medication_id = NULL, updated_at = NOW()
                        WHERE id = ANY(:ids)
                    """),
                    {"ids": chunk},
                )
                await session.commit()
                logger.info(f"  cortados {min(start + BATCH, len(doomed))}/{len(doomed)}")

    stats["_samples"] = samples  # type: ignore[assignment]
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Count only, write nothing")
    parser.add_argument("--show", type=int, default=12)
    args = parser.parse_args()

    stats = asyncio.run(clean(args.dry_run, args.show))
    samples = stats.pop("_samples", [])

    revisados = stats.pop("revisados", 0)
    cortados = stats.pop("cortados", 0)
    print(f"\nvínculos difusos revisados {revisados}")
    print(f"{'se cortarían' if args.dry_run else 'cortados'}              {cortados}")
    if revisados:
        print(f"tasa de error              {cortados / revisados * 100:.2f}%")

    if stats:
        print("\npor categoría:")
        for name, count in sorted(stats.items(), key=lambda kv: -kv[1]):
            print(f"  {name:<22} {count}")

    if samples:
        print("\nmuestra:")
        print("\n".join(samples))

    if args.dry_run:
        print("\n(dry-run — no se escribió nada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
