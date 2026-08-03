import asyncio
from pathlib import Path

import click
from loguru import logger

from .db import AsyncSessionLocal
from .db_writer import DatabaseWriter
from .isp_importer import ISPImporter
from .official_sources import DATA_DIR, OFFICIAL_SOURCES, fetch_all


@click.group()
def main():
    """FarmaciaCompare data ingestion CLI (ISP + free government open data)."""
    pass


@main.command("list-sources")
def list_sources():
    """Show free official government datasets we know about."""
    for s in OFFICIAL_SOURCES:
        click.echo(f"{s.key:<18} {s.kind:<14} {s.title}")
        click.echo(f"  {s.url}")
        click.echo(f"  {s.notes}")


@main.command("fetch-official")
@click.option("--force", is_flag=True, help="Re-download even if cache is fresh")
def fetch_official(force: bool):
    """Download free ISP dumps from datos.gob.cl into data/official/."""
    paths = fetch_all(force=force)
    if not paths:
        raise SystemExit("No sources downloaded")
    for key, path in paths.items():
        click.echo(f"{key:<18} {path} ({path.stat().st_size} bytes)")


@main.command("import-official")
@click.option("--force-fetch", is_flag=True, help="Refresh downloads before import")
@click.option("--dry-run", is_flag=True, help="Parse only, do not write to database")
@click.option(
    "--also-sample",
    is_flag=True,
    help="Also merge local data/isp_sample.csv brand aliases",
)
def import_official(force_fetch: bool, dry_run: bool, also_sample: bool):
    """Fetch (if needed) and import all free government medication dumps."""
    asyncio.run(_import_official(force_fetch, dry_run, also_sample))


async def _import_official(force_fetch: bool, dry_run: bool, also_sample: bool):
    paths = fetch_all(force=force_fetch)
    if not paths:
        raise SystemExit("No official files available — check network / datos.gob.cl")

    importer = ISPImporter()
    records = importer.load_official_dir(DATA_DIR)

    if also_sample:
        sample = Path(__file__).resolve().parent.parent / "data" / "isp_sample.csv"
        if sample.exists():
            for rec in importer.load_csv(str(sample), source="isp_sample"):
                # Sample uses synthetic F-20xxx codes — always add by registration
                records.append(rec)

    # Dedupe again after sample merge
    by_reg: dict[str, object] = {}
    for rec in records:
        key = rec.isp_registration.upper()
        prev = by_reg.get(key)
        if prev is None or (not prev.active_ingredient and rec.active_ingredient):
            by_reg[key] = rec
    records = list(by_reg.values())

    logger.info(f"Total records ready for import: {len(records)}")
    if dry_run:
        for r in records[:15]:
            click.echo(
                f"  {r.isp_registration}: {r.product_name[:55]} | "
                f"{r.active_ingredient or '-'} | {r.dosage or '-'} | {r.pharmaceutical_form}"
            )
        click.echo(f"... ({len(records)} total, dry-run)")
        return

    async with AsyncSessionLocal() as session:
        writer = DatabaseWriter(session)
        stats = await writer.import_records(records)

    click.echo("\nImport complete (official free sources):")
    click.echo(f"  Created:  {stats['created']}")
    click.echo(f"  Skipped:  {stats['skipped']}")
    click.echo(f"  Errors:   {stats['errors']}")


@main.command("import-isp")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--format", "file_format", type=click.Choice(["csv", "excel"]), default="csv")
@click.option("--dry-run", is_flag=True, help="Parse only, do not write to database")
def import_isp(filepath: str, file_format: str, dry_run: bool):
    """Import a single ISP medication CSV/Excel file."""
    asyncio.run(_import_isp(filepath, file_format, dry_run))


async def _import_isp(filepath: str, file_format: str, dry_run: bool):
    importer = ISPImporter()

    if file_format == "csv":
        records = importer.load_csv(filepath)
    else:
        records = importer.load_excel(filepath)

    logger.info(f"Parsed {len(records)} records from {filepath}")

    if dry_run:
        logger.info("Dry run — not writing to database")
        for r in records[:10]:
            click.echo(
                f"  {r.isp_registration}: {r.product_name[:50]} | "
                f"{r.active_ingredient} | {r.dosage} | {r.pharmaceutical_form}"
            )
        return

    async with AsyncSessionLocal() as session:
        writer = DatabaseWriter(session)
        stats = await writer.import_records(records)

    click.echo("\nImport complete:")
    click.echo(f"  Created:  {stats['created']}")
    click.echo(f"  Skipped:  {stats['skipped']}")
    click.echo(f"  Errors:   {stats['errors']}")


@main.command()
@click.argument("query")
def lookup(query: str):
    """Fuzzy lookup a medication by name."""
    asyncio.run(_lookup(query))


async def _lookup(query: str):
    from rapidfuzz import fuzz, process
    from sqlalchemy import select

    from .models import MedicationName

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MedicationName.normalized_name, MedicationName.medication_id)
        )
        all_names = [(row[0], str(row[1])) for row in result.fetchall()]

    if not all_names:
        click.echo("Database is empty. Run import-official first.")
        return

    names_only = [n[0] for n in all_names]
    matches = process.extract(query.lower(), names_only, scorer=fuzz.WRatio, limit=5)

    click.echo(f"\nTop matches for '{query}':")
    for name, score, idx in matches:
        medication_id = all_names[idx][1]
        click.echo(f"  [{score:3.0f}%] {name} (medication_id: {medication_id})")


if __name__ == "__main__":
    main()
