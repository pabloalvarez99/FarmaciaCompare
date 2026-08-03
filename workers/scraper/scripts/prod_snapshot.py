"""Read-only prod snapshot. No secrets printed."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[3]


def url_from_env_file() -> str:
    if os.environ.get("DATABASE_URL"):
        u = os.environ["DATABASE_URL"]
    else:
        for line in (ROOT / ".env.production").read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                u = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        else:
            raise SystemExit("no DATABASE_URL")
    if u.startswith("postgresql://"):
        u = u.replace("postgresql://", "postgresql+asyncpg://", 1)
    return u


async def main() -> None:
    eng = create_async_engine(url_from_env_file())
    async with eng.connect() as c:
        print("medication_names", (await c.execute(text("SELECT count(*) FROM medication_names"))).scalar())
        print("medications", (await c.execute(text("SELECT count(*) FROM medications"))).scalar())
        print(
            "unlinked",
            (
                await c.execute(
                    text(
                        "SELECT count(*) FROM pharmacy_products WHERE medication_id IS NULL AND is_active"
                    )
                )
            ).scalar(),
        )
        print(
            "linked",
            (
                await c.execute(
                    text("SELECT count(*) FROM pharmacy_products WHERE medication_id IS NOT NULL")
                )
            ).scalar(),
        )
        print(
            "running_jobs",
            (
                await c.execute(
                    text("SELECT count(*) FROM scraping_jobs WHERE status = 'running'")
                )
            ).scalar(),
        )
        print("online pharmacies:")
        for row in (
            await c.execute(
                text(
                    "SELECT chain, count(*) FROM pharmacies WHERE type = 'online' GROUP BY chain ORDER BY chain"
                )
            )
        ).fetchall():
            print(" ", row)
        print("products by chain (n, linked, imgs, attrs, isMedicine):")
        for row in (
            await c.execute(
                text(
                    """
                    SELECT ph.chain, count(*) AS n,
                           count(pp.medication_id) AS linked,
                           count(pp.image_url) AS imgs,
                           count(pp.attributes) AS attrs,
                           count(*) FILTER (
                             WHERE attributes->>'isMedicine' IN ('true','True','1')
                                OR (attributes->'isMedicine') = 'true'::jsonb
                           ) AS is_med
                    FROM pharmacy_products pp
                    JOIN pharmacies ph ON ph.id = pp.pharmacy_id
                    GROUP BY ph.chain ORDER BY n DESC
                    """
                )
            )
        ).fetchall():
            n, linked, imgs, attrs, is_med = row[1], row[2], row[3], row[4], row[5]
            img_pct = f"{100 * imgs / n:.0f}%" if n else "n/a"
            print(
                f"  {row[0]:<14} n={n:<6} linked={linked:<6} "
                f"imgs={imgs:<6}({img_pct}) attrs={attrs:<6} isMed={is_med}"
            )

        print("physical pharmacies by region (active):")
        for row in (
            await c.execute(
                text(
                    """
                    SELECT coalesce(region, '(null)'), count(*)
                    FROM pharmacies
                    WHERE type = 'physical' AND is_active
                    GROUP BY region ORDER BY count(*) DESC
                    """
                )
            )
        ).fetchall():
            print(" ", row)
    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
