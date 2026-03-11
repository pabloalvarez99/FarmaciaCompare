import asyncio
import click
from loguru import logger
from .isp_importer import ISPImporter
from .db_writer import DatabaseWriter
from .db import AsyncSessionLocal


@click.group()
def main():
    """FarmaciaCompare data ingestion CLI."""
    pass


@main.command("import-isp")
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--format", "file_format", type=click.Choice(["csv", "excel"]), default="csv")
@click.option("--dry-run", is_flag=True, help="Parse only, do not write to database")
def import_isp(filepath: str, file_format: str, dry_run: bool):
    """Import ISP medication dataset from CSV or Excel file."""
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

    click.echo(f"\nImport complete:")
    click.echo(f"  Created:  {stats['created']}")
    click.echo(f"  Skipped:  {stats['skipped']}")
    click.echo(f"  Errors:   {stats['errors']}")


@main.command()
@click.argument("query")
def lookup(query: str):
    """Fuzzy lookup a medication by name."""
    asyncio.run(_lookup(query))


async def _lookup(query: str):
    from rapidfuzz import process, fuzz
    from sqlalchemy import select, text
    from .models import MedicationName

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MedicationName.normalized_name, MedicationName.medication_id)
        )
        all_names = [(row[0], str(row[1])) for row in result.fetchall()]

    if not all_names:
        click.echo("Database is empty. Run import-isp first.")
        return

    names_only = [n[0] for n in all_names]
    matches = process.extract(query.lower(), names_only, scorer=fuzz.WRatio, limit=5)

    click.echo(f"\nTop matches for '{query}':")
    for name, score, idx in matches:
        medication_id = all_names[idx][1]
        click.echo(f"  [{score:3.0f}%] {name} (medication_id: {medication_id})")


if __name__ == "__main__":
    main()
