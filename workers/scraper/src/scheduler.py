from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
import asyncio


async def run_vtex_scrape(chain: str):
    from .connectors.vtex_connector import VtexConnector, VTEX_CONFIGS
    from .db import AsyncSessionLocal
    from .price_writer import PriceWriter
    from .matcher import DrugMatcher
    from sqlalchemy import text

    config = VTEX_CONFIGS.get(chain)
    if not config:
        logger.error(f"Unknown VTEX chain: {chain}")
        return

    logger.info(f"Starting VTEX scrape for {chain}")
    connector = VtexConnector(config)

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT medication_id, normalized_name FROM medication_names"))
        candidates = [{"medication_id": str(r[0]), "normalized_name": r[1]} for r in result]
        matcher = DrugMatcher(candidates)

        pharmacy_result = await session.execute(
            text("SELECT id FROM pharmacies WHERE chain = :chain LIMIT 1"), {"chain": chain}
        )
        pharmacy_row = pharmacy_result.fetchone()
        if not pharmacy_row:
            logger.warning(f"No pharmacy found for chain {chain}")
            return

        pharmacy_id = str(pharmacy_row[0])
        writer = PriceWriter(session, pharmacy_id, matcher)
        products = []
        async for product in connector.scrape_products():
            products.append(product)
            if len(products) >= 500:
                stats = await writer.write_batch(products)
                logger.info(f"[{chain}] Batch written: {stats}")
                products = []
        if products:
            stats = await writer.write_batch(products)
            logger.info(f"[{chain}] Final batch: {stats}")
    logger.info(f"Scrape complete for {chain}")


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    for chain in ["cruz_verde", "salcobrand", "ahumada"]:
        scheduler.add_job(run_vtex_scrape, "interval", hours=4, args=[chain],
                          id=f"vtex_{chain}", name=f"VTEX scrape: {chain}", replace_existing=True)
    return scheduler


async def main():
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scraper scheduler started")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
