"""Fill `pharmacy_products.image_url` for rows scraped before the column existed.

Why a dedicated script instead of just re-running the scrapers
-------------------------------------------------------------
The image URL cannot be derived from anything already in the database. Every
chain hashes or IDs its CDN path independently of the SKU we store:

    cruz_verde   .../default/dwca2664bc/images/large/266145-xumadol.jpg
    salcobrand   .../spree/products/169994/small/430924.jpg
    ahumada      .../default/dwc6eb09fb/images/products/6/6.jpg?sw=1050
    dr_simi      .../arquivos/ids/160249-500-500/BE0089-1.jpg
    farmaloop    .../products-image/97877.jpg

None of those are a function of `sku`, so a purely in-place UPDATE (the shape
`recompute_catalog.py` uses) is impossible — the data has to come off the
storefront again.

That leaves two options, and this is the cheaper one:

  * `scraper scrape <chain>` walks the same pages but also runs the matcher for
    every product, reads the last price, evaluates the anomaly gate and writes
    a `prices` row. On ~75k products that is tens of thousands of extra DB
    round-trips and a price-history entry per product, for data we already have.
  * This script walks the same pages and issues one narrow UPDATE per product,
    keyed on (pharmacy_id, sku), touching only `image_url`. No price rows, no
    matcher, no anomaly gate, no `scraping_jobs` bookkeeping — so it also cannot
    corrupt price history if a storefront is having a bad day.

Network cost is identical (the storefront has to be read either way); DB cost
and blast radius are far smaller. It is idempotent and safe to re-run.

    python -m src.backfill_images --chain salcobrand
    python -m src.backfill_images --chain cruz_verde --limit 500
    python -m src.backfill_images --all --dry-run

`--only-missing` (default) skips products that already carry an image, so a
second pass only pays for what is still empty.
"""
from __future__ import annotations

import argparse
import asyncio

from loguru import logger
from sqlalchemy import text

from .db import AsyncSessionLocal
from .registry import CHAIN_NAMES, build_scraper

# Commit often. A full-catalog crawl takes ~an hour, and anything that stops it
# (a kill, a dropped DB session) throws away every update still pending, so a
# large batch buys nothing and risks losing the whole run's work.
BATCH = 50


async def _resolve_pharmacy_id(session, chain: str) -> str | None:
    """Same resolution the scheduler uses, so we write to the same pharmacy row."""
    row = (
        await session.execute(
            text("""
                SELECT id FROM pharmacies
                WHERE chain = :chain
                ORDER BY (type = 'online') DESC, created_at ASC
                LIMIT 1
            """),
            {"chain": chain},
        )
    ).fetchone()
    return str(row[0]) if row else None


async def _existing_skus(session, pharmacy_id: str, only_missing: bool) -> set[str] | None:
    """SKUs that still need an image, or None when every row is a candidate.

    Loading the SKU set once costs one query and lets the loop skip the UPDATE
    entirely for products that are already done — on a re-run that is most of
    them.
    """
    if not only_missing:
        return None
    rows = await session.execute(
        text("""
            SELECT sku FROM pharmacy_products
            WHERE pharmacy_id = :pid AND image_url IS NULL
        """),
        {"pid": pharmacy_id},
    )
    return {r[0] for r in rows}


async def backfill_chain(
    chain: str,
    *,
    limit: int = 0,
    only_missing: bool = True,
    dry_run: bool = False,
    fast: bool = False,
) -> dict[str, int]:
    # `skipped`   = already had an image, not revisited (--only-missing)
    # `unchanged` = UPDATE matched no row: either the value was already correct
    #               (`IS DISTINCT FROM` made it a no-op) or the SKU is not in our
    #               table yet. Both are fine; only `updated` means we wrote.
    stats = {"scraped": 0, "with_image": 0, "updated": 0, "skipped": 0, "unchanged": 0}

    async with AsyncSessionLocal() as session:
        pharmacy_id = await _resolve_pharmacy_id(session, chain)
        if not pharmacy_id:
            logger.error(f"[{chain}] no pharmacy row — run `scraper sync-pharmacies` first")
            return stats

        wanted = await _existing_skus(session, pharmacy_id, only_missing)
        if wanted is not None:
            logger.info(f"[{chain}] {len(wanted)} products still without an image")
            if not wanted:
                return stats

        scraper = build_scraper(chain, fast=fast)
        pending = 0

        # A connector that can address a product by id lets us ask for exactly
        # the rows that are missing instead of re-walking the whole catalog.
        # Repairing 339 Cruz Verde products costs 339 requests this way and
        # ~10,300 through the sitemap — the difference between 3 minutes and an
        # hour, and an hour-long job is one that gets killed before it commits.
        if wanted and hasattr(scraper, "fetch_by_skus"):
            source = scraper.fetch_by_skus(sorted(wanted))
            logger.info(f"[{chain}] targeted fetch of {len(wanted)} missing products")
        else:
            source = scraper.scrape_products()

        async for product in source:
            stats["scraped"] += 1
            if not product.image_url:
                continue
            stats["with_image"] += 1

            if wanted is not None and product.sku not in wanted:
                stats["skipped"] += 1
                continue

            if dry_run:
                stats["updated"] += 1
            else:
                # `IS DISTINCT FROM` keeps the write a no-op when the value is
                # already correct, so re-running does not bump updated_at on
                # every row and churn the table.
                result = await session.execute(
                    text("""
                        UPDATE pharmacy_products
                        SET image_url = :image_url, updated_at = NOW()
                        WHERE pharmacy_id = :pid
                          AND sku = :sku
                          AND image_url IS DISTINCT FROM :image_url
                    """),
                    {"image_url": product.image_url, "pid": pharmacy_id, "sku": product.sku},
                )
                if result.rowcount:
                    stats["updated"] += 1
                else:
                    stats["unchanged"] += 1
                pending += 1
                if pending >= BATCH:
                    await session.commit()
                    pending = 0
                    logger.info(f"[{chain}] {stats}")

            if limit and stats["updated"] >= limit:
                break

        if not dry_run:
            await session.commit()

    logger.info(f"[{chain}] backfill done: {stats}")
    return stats


async def _run(chains: list[str], **kwargs) -> None:
    summary: dict[str, dict[str, int]] = {}
    for chain in chains:
        try:
            summary[chain] = await backfill_chain(chain, **kwargs)
        except Exception as exc:
            logger.exception(f"[{chain}] backfill failed: {exc}")
            summary[chain] = {"scraped": 0, "updated": -1}
    for chain, stats in summary.items():
        logger.info(f"{chain:<14} updated={stats.get('updated')} scraped={stats.get('scraped')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--chain", choices=CHAIN_NAMES, help="Backfill a single chain")
    group.add_argument("--all", action="store_true", help="Backfill every registered chain")
    parser.add_argument("--limit", type=int, default=0, help="Stop after N updates (0 = all)")
    parser.add_argument(
        "--all-rows",
        action="store_true",
        help="Also revisit products that already have an image (default: only empty ones)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Count without writing")
    parser.add_argument("--fast", action="store_true", help="Use the chain's cheap mode if it has one")
    args = parser.parse_args()

    chains = CHAIN_NAMES if args.all else [args.chain]
    asyncio.run(
        _run(
            chains,
            limit=args.limit,
            only_missing=not args.all_rows,
            dry_run=args.dry_run,
            fast=args.fast,
        )
    )


if __name__ == "__main__":
    main()
