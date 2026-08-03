import asyncio

import click
from loguru import logger

from .registry import CHAIN_NAMES, CHAINS, build_scraper


@click.group()
def main():
    """FarmaciaCompare price scraper CLI."""
    pass


@main.command(name="list-chains")
def list_chains():
    """Show every pharmacy chain the scraper knows about."""
    for spec in CHAINS.values():
        click.echo(f"{spec.chain:<12} {spec.platform:<14} every {spec.interval_hours:>2}h  {spec.website}")


@main.command()
@click.argument("chain", type=click.Choice(CHAIN_NAMES))
@click.option("--limit", default=0, help="Max products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Print products instead of writing to the database")
@click.option("--fast", is_flag=True, help="Use the chain's cheap price-refresh mode when it has one")
def scrape(chain: str, limit: int, dry_run: bool, fast: bool):
    """Run the scraper for a specific pharmacy chain."""
    asyncio.run(_scrape(chain, limit, dry_run, fast))


async def _scrape(chain: str, limit: int, dry_run: bool, fast: bool):
    if not dry_run:
        from .scheduler import run_scrape
        await run_scrape(chain, fast=fast)
        return

    scraper = build_scraper(chain, fast=fast)
    count = 0
    async for product in scraper.scrape_products():
        logger.info(
            f"{product.sku} | {product.name[:60]} | ${product.price:,} | {product.stock_status}"
        )
        count += 1
        if limit and count >= limit:
            break
    logger.info(f"[{chain}] dry run finished: {count} products")


@main.command(name="scrape-all")
@click.option("--fast", is_flag=True, help="Use cheap price-refresh modes where available")
def scrape_all(fast: bool):
    """Run every registered chain sequentially."""
    asyncio.run(_scrape_all(fast))


async def _scrape_all(fast: bool):
    from .scheduler import run_scrape, sync_pharmacies

    await sync_pharmacies()
    summary = {}
    for chain in CHAIN_NAMES:
        try:
            summary[chain] = await run_scrape(chain, fast=fast)
        except Exception as exc:
            logger.error(f"[{chain}] run failed: {exc}")
            summary[chain] = {"written": 0, "errors": -1}
    for chain, stats in summary.items():
        logger.info(f"{chain:<12} written={stats['written']} errors={stats['errors']}")


@main.command(name="sync-pharmacies")
def sync_pharmacies_cmd():
    """Create the canonical online pharmacy row for every registered chain."""
    from .scheduler import sync_pharmacies
    ids = asyncio.run(sync_pharmacies())
    for chain, pharmacy_id in ids.items():
        click.echo(f"{chain:<12} {pharmacy_id}")


@main.command(name="start-scheduler")
def start_scheduler():
    """Start the price collection scheduler (runs continuously)."""
    from .scheduler import main as scheduler_main
    asyncio.run(scheduler_main())


@main.command(name="relink")
@click.option("--limit", default=0, help="Max unlinked products to process (0 = all)")
@click.option("--dry-run", is_flag=True, help="Show matches without writing")
@click.option(
    "--only-medicine",
    is_flag=True,
    help="Only rows with attributes.isMedicine true (excludes Farmaloop/beauty/null attrs)",
)
@click.option(
    "--chain",
    "chain_filter",
    default=None,
    type=click.Choice(CHAIN_NAMES),
    help="Limit to one online chain",
)
def relink(limit: int, dry_run: bool, only_medicine: bool, chain_filter: str | None):
    """Re-run identity matching on pharmacy_products without medication_id."""
    asyncio.run(_relink(limit, dry_run, only_medicine, chain_filter))


async def _relink(
    limit: int,
    dry_run: bool,
    only_medicine: bool = False,
    chain_filter: str | None = None,
):
    from sqlalchemy import text

    from .db import AsyncSessionLocal
    from .matcher import DrugMatcher

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            # `m.name` rides along so the matcher can close its gates against the
            # real product name; the alias alone has no form, pack or volume.
            text("""
                SELECT mn.medication_id, mn.normalized_name, m.name
                FROM medication_names mn
                JOIN medications m ON m.id = mn.medication_id
            """)
        )
        candidates = [
            {"medication_id": str(r[0]), "normalized_name": r[1], "full_name": r[2]}
            for r in result
        ]
        if not candidates:
            click.echo("No medication_names rows — import ISP catalog first.")
            return

        # Same vocabulary the scheduler loads, so a dry-run here predicts what
        # a real scrape would write.
        ingredients = [
            r[0]
            for r in await session.execute(text("SELECT name FROM active_ingredients"))
        ]
        matcher = DrugMatcher(candidates, ingredients)
        # Join pharmacies when chain-filtered so we can scope online chains.
        if chain_filter:
            q = """
                SELECT pp.id, pp.raw_name, pp.brand, pp.barcode, pp.attributes
                FROM pharmacy_products pp
                JOIN pharmacies ph ON ph.id = pp.pharmacy_id
                WHERE pp.medication_id IS NULL AND pp.is_active = true
                  AND ph.chain = :chain
            """
            params: dict = {"chain": chain_filter}
        else:
            q = """
                SELECT id, raw_name, brand, barcode, attributes
                FROM pharmacy_products
                WHERE medication_id IS NULL AND is_active = true
            """
            params = {}

        attr_col = "pp.attributes" if chain_filter else "attributes"
        if only_medicine:
            # jsonb bool true OR string "true" from older scrapes
            q += f"""
                  AND (
                    {attr_col}->>'isMedicine' IN ('true', 'True', '1')
                    OR ({attr_col}->'isMedicine') = 'true'::jsonb
                  )
            """

        q += " ORDER BY pp.updated_at DESC" if chain_filter else " ORDER BY updated_at DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        rows = (await session.execute(text(q), params)).fetchall()

        linked = grey = none = 0
        for row in rows:
            pid, raw_name, brand, barcode, attributes = (
                str(row[0]),
                row[1],
                row[2],
                row[3],
                row[4],
            )
            is_med = None
            if isinstance(attributes, dict):
                raw_flag = attributes.get("isMedicine", attributes.get("is_medicine"))
                if isinstance(raw_flag, bool):
                    is_med = raw_flag
                elif isinstance(raw_flag, str):
                    is_med = raw_flag.strip().lower() in (
                        "1",
                        "true",
                        "yes",
                        "si",
                        "sí",
                    )
            match = matcher.match(
                raw_name,
                barcode=barcode,
                brand=brand,
                is_medicine=is_med,
            )
            if matcher.should_auto_link(match):
                linked += 1
                if dry_run:
                    click.echo(
                        f"LINK  {match.confidence:.2f} {raw_name[:50]!r} → {match.matched_name}"
                    )
                else:
                    await session.execute(
                        text(
                            "UPDATE pharmacy_products SET medication_id = :mid, updated_at = NOW() WHERE id = :id"
                        ),
                        {"mid": match.medication_id, "id": pid},
                    )
            elif match and match.grey_zone:
                grey += 1
                if dry_run:
                    click.echo(
                        f"GREY  {match.confidence:.2f} {raw_name[:50]!r} → {match.matched_name}"
                    )
            else:
                none += 1

        if not dry_run:
            await session.commit()

        scope = []
        if only_medicine:
            scope.append("only-medicine")
        if chain_filter:
            scope.append(f"chain={chain_filter}")
        scope_s = f" ({', '.join(scope)})" if scope else ""
        click.echo(
            f"relink done{scope_s}: linked={linked} grey={grey} none={none} scanned={len(rows)}"
        )


# Orphan job reaper: same intent as scripts/reap_stale_jobs.py, as a scraper CLI command.
# Schema uses `errors` (jsonb), not a separate error_message column.
ORPHAN_ERROR_REASON = "orphaned: exceeded max runtime"
DEFAULT_CLEANUP_HOURS = 2


@main.command(name="discover-places")
@click.option(
    "--region",
    default="coquimbo",
    show_default=True,
    type=click.Choice(
        ["coquimbo", "metropolitana", "valparaiso", "biobio", "maule", "araucania"]
    ),
    help="Region to discover",
)
@click.option(
    "--out",
    "out_path",
    default="",
    help="JSON output path (default: data/<region>-places.json)",
)
@click.option("--no-details", is_flag=True, help="Skip Place Details (cheaper, less phone/web)")
@click.option(
    "--city",
    multiple=True,
    help="Limit to one or more cities (repeatable). Default: full city set for the region.",
)
@click.option(
    "--limit-cities",
    type=int,
    default=0,
    help="Only the first N cities of the region (cost control / test runs).",
)
def discover_places(
    region: str, out_path: str, no_details: bool, city: tuple[str, ...], limit_cities: int
):
    """Discover physical pharmacies via Google Places (needs GOOGLE_MAPS_API_KEY).

    Load the key from gcloud (tablero-iner-maps server key), never commit it:

      $env:GOOGLE_MAPS_API_KEY = (gcloud services api-keys get-key-string `
        projects/707448781980/locations/global/keys/e7a2adb4-dd06-4fbc-99d7-345377eea53a `
        --project=tablero-iner-maps --format="value(keyString)")
    """
    from pathlib import Path

    from .places_discovery import (
        REGIONS,
        REQUEST_COUNTS,
        discover_region,
        reset_request_counts,
        save_json,
    )

    spec = REGIONS.get(region)
    if spec is None:
        raise click.UsageError(f"unsupported region {region}")
    cities = list(city) if city else list(spec.cities)
    if limit_cities > 0:
        cities = cities[:limit_cities]
    click.echo(f"region={spec.name} cities={len(cities)}: {', '.join(cities)}")

    reset_request_counts()
    results = discover_region(
        cities,
        with_details=not no_details,
        region=spec.name,
        query_hint=spec.query_hint,
    )
    path = Path(out_path or f"data/{region}-places.json")
    if not path.is_absolute():
        path = Path.cwd() / path
    save_json(results, path, region=spec.name)
    chains: dict[str, int] = {}
    for p in results:
        key = p.chain or "(independent)"
        chains[key] = chains.get(key, 0) + 1
    click.echo(f"discovered {len(results)} pharmacies → {path}")
    for k, n in sorted(chains.items(), key=lambda x: -x[1]):
        click.echo(f"  {k:<22} {n}")
    click.echo(
        f"API requests: text_search={REQUEST_COUNTS['text_search']} "
        f"place_details={REQUEST_COUNTS['place_details']} "
        f"total={REQUEST_COUNTS['text_search'] + REQUEST_COUNTS['place_details']}"
    )


@main.command(name="import-places")
@click.option(
    "--from-json",
    "from_json",
    default="data/coquimbo-places.json",
    show_default=True,
    help="JSON produced by discover-places",
)
@click.option("--dry-run", is_flag=True, help="Print counts without writing")
def import_places(from_json: str, dry_run: bool):
    """Upsert physical pharmacies from a Places discovery JSON into the DB."""
    from pathlib import Path

    from .places_discovery import load_json
    from .places_import import upsert_physical_pharmacies

    path = Path(from_json)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise click.ClickException(f"file not found: {path}")
    rows = load_json(path)
    click.echo(f"loaded {len(rows)} places from {path}")
    if dry_run:
        by_city: dict[str, int] = {}
        for r in rows:
            by_city[r.city or "?"] = by_city.get(r.city or "?", 0) + 1
        for city, n in sorted(by_city.items(), key=lambda x: -x[1]):
            click.echo(f"  {city:<20} {n}")
        return
    stats = asyncio.run(upsert_physical_pharmacies(rows))
    click.echo(f"import-places: {stats}")


@main.command(name="cleanup-jobs")
@click.option(
    "--hours",
    default=DEFAULT_CLEANUP_HOURS,
    show_default=True,
    type=int,
    help="Mark status=running jobs with started_at older than this many hours as failed",
)
@click.option("--dry-run", is_flag=True, help="Count orphans without writing")
def cleanup_jobs(hours: int, dry_run: bool):
    """Mark orphaned scraping_jobs (stuck in running) as failed."""
    if hours < 0:
        raise click.UsageError("--hours must be >= 0")
    asyncio.run(_cleanup_jobs(hours, dry_run))


async def _cleanup_jobs(hours: int, dry_run: bool):
    from sqlalchemy import text

    from .db import AsyncSessionLocal

    # Interval via cast — avoids SQLAlchemy/PG named-arg clash on make_interval(hours => …)
    preview_sql = text(
        """
        SELECT id::text, pharmacy_chain, started_at
        FROM scraping_jobs
        WHERE status = 'running'
          AND started_at < NOW() - (CAST(:hours AS int) * INTERVAL '1 hour')
        ORDER BY started_at
        """
    )
    update_sql = text(
        """
        UPDATE scraping_jobs
        SET status = 'failed',
            finished_at = NOW(),
            errors = jsonb_build_object(
                'reason', CAST(:reason AS text),
                'max_age_hours', CAST(:hours AS int),
                'reaped_by', 'cleanup-jobs'
            )
        WHERE status = 'running'
          AND started_at < NOW() - (CAST(:hours AS int) * INTERVAL '1 hour')
        """
    )

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(preview_sql, {"hours": hours})).fetchall()
        count = len(rows)
        for row in rows:
            click.echo(
                f"orphan  {row[1] or '-':<12} started_at={row[2]} id={row[0]}"
            )

        if dry_run:
            click.echo(
                f"cleanup-jobs dry-run: would mark {count} row(s) as failed "
                f"(running older than {hours}h)"
            )
            return

        if count == 0:
            click.echo(
                f"cleanup-jobs: no scraping_jobs stuck in running older than {hours}h"
            )
            return

        result = await session.execute(
            update_sql, {"hours": hours, "reason": ORPHAN_ERROR_REASON}
        )
        await session.commit()
        updated = result.rowcount if result.rowcount is not None else count
        click.echo(
            f"cleanup-jobs: marked {updated} row(s) as failed "
            f"(reason={ORPHAN_ERROR_REASON!r}, hours={hours})"
        )


if __name__ == "__main__":
    main()
