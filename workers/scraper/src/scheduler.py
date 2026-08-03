"""Scrape orchestration: jobs, health gates, registry-driven schedule."""
from __future__ import annotations

import asyncio
import json
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from sqlalchemy import text

from .registry import CHAINS, build_scraper

BATCH_SIZE = 500

# Soft catalog-size floors. Below 30% of this after a finished crawl → failed.
# Tuned low enough for first loads; raise after a few successful production runs.
MIN_EXPECTED: dict[str, int] = {
    "cruz_verde": 3000,
    "salcobrand": 5000,
    "ahumada": 2000,
    "dr_simi": 2000,
    "farmex": 500,
    "curie": 200,
    "farmaloop": 300,
    "mercadofarma": 1000,
    "knop": 500,
    "preunic": 2000,  # beauty catalog ~9k; floor stays soft via HEALTH_RATIO
}

HEALTH_RATIO = 0.30


async def sync_pharmacies() -> dict[str, str]:
    """Ensure one canonical online storefront row exists per registered chain."""
    from .db import AsyncSessionLocal

    ids: dict[str, str] = {}
    async with AsyncSessionLocal() as session:
        for spec in CHAINS.values():
            result = await session.execute(
                text(
                    "SELECT id FROM pharmacies WHERE chain = :chain AND type = 'online' LIMIT 1"
                ),
                {"chain": spec.chain},
            )
            row = result.fetchone()
            if row:
                ids[spec.chain] = str(row[0])
                continue

            pharmacy_id = str(uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO pharmacies (
                        id, name, chain, type, website, is_active, has_delivery, has_pickup,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :name, :chain, 'online', :website, true, true, true, NOW(), NOW()
                    )
                """),
                {
                    "id": pharmacy_id,
                    "name": f"{spec.name} (Online)",
                    "chain": spec.chain,
                    "website": spec.website,
                },
            )
            ids[spec.chain] = pharmacy_id
            logger.info(f"Created online pharmacy row for {spec.chain}")
        await session.commit()
    return ids


async def _resolve_pharmacy_id(session, chain: str) -> str | None:
    result = await session.execute(
        text("""
            SELECT id FROM pharmacies
            WHERE chain = :chain
            ORDER BY (type = 'online') DESC, created_at ASC
            LIMIT 1
        """),
        {"chain": chain},
    )
    row = result.fetchone()
    return str(row[0]) if row else None


def evaluate_health(chain: str, scraped: int, errors: int) -> tuple[str, list[str]]:
    """Return (status, reasons). status: success | empty | failed."""
    reasons: list[str] = []
    if scraped == 0:
        return "empty", ["zero_products"]

    floor = int(MIN_EXPECTED.get(chain, 100) * HEALTH_RATIO)
    if scraped < floor:
        reasons.append(f"below_floor:{scraped}<{floor}")

    total_ops = scraped + errors
    if errors and total_ops and errors / total_ops > 0.25:
        reasons.append(f"high_error_rate:{errors}/{total_ops}")

    if reasons:
        return "failed", reasons
    return "success", []


async def run_scrape(chain: str, fast: bool = False) -> dict:
    """Scrape one chain end to end and persist prices with health accounting."""
    from .db import AsyncSessionLocal
    from .matcher import DrugMatcher
    from .price_writer import PriceWriter

    if chain not in CHAINS:
        logger.error(f"Unknown chain: {chain}")
        return {"written": 0, "errors": 0, "status": "failed"}

    scraper = build_scraper(chain, fast=fast)
    logger.info(
        f"Starting scrape for {chain} "
        f"({CHAINS[chain].platform}{', fast mode' if fast else ''})"
    )

    totals = {
        "written": 0,
        "errors": 0,
        "price_rows": 0,
        "unchanged": 0,
        "quarantined": 0,
        "linked": 0,
        "unlinked": 0,
        "status": "running",
    }

    async with AsyncSessionLocal() as session:
        pharmacy_id = await _resolve_pharmacy_id(session, chain)
        if not pharmacy_id:
            logger.warning(
                f"No pharmacy row for chain {chain} — run `scraper sync-pharmacies` first"
            )
            totals["status"] = "failed"
            return totals

        # Close abandoned rows before opening a new one.
        #
        # The `running → success/failed` update at the end of this function only
        # runs when the function returns. A container killed outright — task
        # timeout, SIGTERM on revision replacement, OOM — leaves its row saying
        # `running` forever, and every later reader believes a scrape is in
        # flight when nothing is. That has already produced ghost rows three
        # times, and the cost is real: the concurrency check refuses to launch
        # work because of scrapes that died hours ago.
        #
        # The reaper belongs here rather than in a separate cron because a job
        # that is starting is the one moment we can be certain the ghosts are
        # not ours. The window is deliberately generous: a full Cruz Verde
        # sitemap crawl runs ~2h45m and must never be reaped while healthy.
        reaped = await session.execute(
            text("""
                UPDATE scraping_jobs
                SET status = 'failed',
                    finished_at = NOW(),
                    errors = CAST(:reason AS jsonb)
                WHERE status = 'running'
                  AND started_at < NOW() - INTERVAL '4 hours'
                RETURNING pharmacy_chain
            """),
            {"reason": json.dumps({"reasons": ["orphaned: container died before finalising"]})},
        )
        ghosts = [r[0] for r in reaped]
        if ghosts:
            logger.warning(f"reaped {len(ghosts)} stale running job(s): {ghosts}")

        job_id = str(uuid.uuid4())
        await session.execute(
            text("""
                INSERT INTO scraping_jobs (
                    id, pharmacy_id, pharmacy_chain, status, started_at, created_at
                )
                VALUES (:id, :pharmacy_id, :chain, 'running', NOW(), NOW())
            """),
            {"id": job_id, "pharmacy_id": pharmacy_id, "chain": chain},
        )
        await session.commit()

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
        # The ingredient vocabulary lets the combination gate catch a two-drug
        # product written without punctuation ("Dutasterida 0,5 mg Tamsulosina
        # 0,4 mg"), which would otherwise link onto one of its components and
        # price a combination as if it were the cheaper single ingredient.
        ingredients = [
            r[0]
            for r in await session.execute(text("SELECT name FROM active_ingredients"))
        ]
        matcher = DrugMatcher(candidates, ingredients)
        writer = PriceWriter(session, pharmacy_id, matcher)

        scraped = 0
        try:
            batch: list = []
            async for product in scraper.scrape_products():
                batch.append(product)
                scraped += 1
                if len(batch) >= BATCH_SIZE:
                    stats = await writer.write_batch(batch)
                    for k in (
                        "written",
                        "errors",
                        "price_rows",
                        "unchanged",
                        "quarantined",
                        "linked",
                        "unlinked",
                    ):
                        totals[k] += stats.get(k, 0)
                    logger.info(f"[{chain}] batch written: {stats}")
                    batch = []
            if batch:
                stats = await writer.write_batch(batch)
                for k in (
                    "written",
                    "errors",
                    "price_rows",
                    "unchanged",
                    "quarantined",
                    "linked",
                    "unlinked",
                ):
                    totals[k] += stats.get(k, 0)
                logger.info(f"[{chain}] final batch: {stats}")
        except Exception as exc:
            logger.exception(f"[{chain}] scrape crashed: {exc}")
            totals["errors"] += 1
            status, reasons = "failed", [f"exception:{type(exc).__name__}:{exc}"]
        else:
            status, reasons = evaluate_health(chain, scraped, totals["errors"])

        totals["status"] = status
        totals["scraped"] = scraped
        totals["health_reasons"] = reasons

        await session.execute(
            text("""
                UPDATE scraping_jobs
                SET status = :status,
                    finished_at = NOW(),
                    items_scraped = :scraped,
                    items_updated = :updated,
                    errors = CAST(:errors AS jsonb)
                WHERE id = :id
            """),
            {
                "id": job_id,
                "status": status,
                "scraped": scraped,
                "updated": totals["price_rows"],
                "errors": json.dumps(
                    {
                        "write_errors": totals["errors"],
                        "quarantined": totals["quarantined"],
                        "reasons": reasons,
                        "writer": {
                            "linked": totals["linked"],
                            "unlinked": totals["unlinked"],
                            "unchanged": totals["unchanged"],
                        },
                    }
                ),
            },
        )
        await session.commit()

    if status != "success":
        logger.error(f"[{chain}] scrape {status}: scraped={scraped} reasons={reasons}")
    else:
        logger.info(f"Scrape complete for {chain}: {totals}")
    return totals


async def run_vtex_scrape(chain: str) -> dict:
    return await run_scrape(chain)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    for spec in CHAINS.values():
        scheduler.add_job(
            run_scrape,
            "interval",
            hours=spec.interval_hours,
            args=[spec.chain],
            id=f"scrape_{spec.chain}",
            name=f"Scrape: {spec.name}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    return scheduler


async def main():
    await sync_pharmacies()
    scheduler = create_scheduler()
    scheduler.start()
    logger.info(f"Scraper scheduler started with {len(CHAINS)} chains")
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
