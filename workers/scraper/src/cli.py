import asyncio
import click
from loguru import logger


@click.group()
def main():
    """FarmaciaCompare price scraper CLI."""
    pass


@main.command()
@click.argument("chain", type=click.Choice(["cruz_verde", "salcobrand", "ahumada", "dr_simi"]))
@click.option("--limit", default=0, help="Max products to scrape (0 = all)")
@click.option("--dry-run", is_flag=True)
def scrape(chain: str, limit: int, dry_run: bool):
    """Run scraper for a specific pharmacy chain."""
    asyncio.run(_scrape(chain, limit, dry_run))


async def _scrape(chain: str, limit: int, dry_run: bool):
    from .scheduler import run_vtex_scrape
    vtex_chains = ["cruz_verde", "salcobrand", "ahumada"]
    if chain in vtex_chains:
        if dry_run:
            from .connectors.vtex_connector import VtexConnector, VTEX_CONFIGS
            connector = VtexConnector(VTEX_CONFIGS[chain])
            count = 0
            async for product in connector.scrape_products():
                logger.info(f"{product.sku} | {product.name[:50]} | ${product.price:,}")
                count += 1
                if limit and count >= limit:
                    break
        else:
            await run_vtex_scrape(chain)
    elif chain == "dr_simi":
        from .pharmacies.dr_simi import DrSimiScraper
        scraper = DrSimiScraper()
        count = 0
        async for product in scraper.scrape_products():
            if dry_run:
                logger.info(f"{product.sku} | {product.name[:50]} | ${product.price:,}")
            count += 1
            if limit and count >= limit:
                break


@main.command()
def start_scheduler():
    """Start the price collection scheduler (runs continuously)."""
    from .scheduler import main as scheduler_main
    asyncio.run(scheduler_main())


if __name__ == "__main__":
    main()
