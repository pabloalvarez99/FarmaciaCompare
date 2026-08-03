"""Soft-deactivate Coquimbo physical rows that fail looks_like_pharmacy (name-only).

No hard-delete. Online pharmacies untouched. Secrets never printed.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# workers/scraper on path for `from src...`
SCRAPER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRAPER_ROOT))

from src.places_discovery import looks_like_pharmacy  # noqa: E402

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
    async with eng.begin() as c:
        rows = (
            await c.execute(
                text(
                    """
                    SELECT id, name, city
                    FROM pharmacies
                    WHERE type = 'physical'
                      AND region = 'Coquimbo'
                      AND is_active = true
                    ORDER BY name
                    """
                )
            )
        ).fetchall()

        print(f"active physical Coquimbo before: {len(rows)}")

        to_deactivate: list[tuple] = []
        for r in rows:
            if not looks_like_pharmacy(r.name or ""):
                to_deactivate.append(r)

        print(f"noise candidates (fail looks_like_pharmacy): {len(to_deactivate)}")
        for r in to_deactivate:
            print(f"  - [{r.city}] {r.name}  id={r.id}")

        if to_deactivate:
            ids = [r.id for r in to_deactivate]
            result = await c.execute(
                text(
                    """
                    UPDATE pharmacies
                    SET is_active = false, updated_at = NOW()
                    WHERE id = ANY(:ids)
                      AND type = 'physical'
                      AND region = 'Coquimbo'
                      AND is_active = true
                    """
                ),
                {"ids": ids},
            )
            print(f"deactivated: {result.rowcount}")
        else:
            print("deactivated: 0")

        remaining = (
            await c.execute(
                text(
                    """
                    SELECT count(*)
                    FROM pharmacies
                    WHERE type = 'physical'
                      AND region = 'Coquimbo'
                      AND is_active = true
                    """
                )
            )
        ).scalar()
        print(f"active physical Coquimbo remaining: {remaining}")

        # sanity: online untouched sample
        online = (
            await c.execute(
                text(
                    """
                    SELECT count(*) FROM pharmacies
                    WHERE type = 'online' AND is_active = true
                    """
                )
            )
        ).scalar()
        print(f"active online (sanity): {online}")

    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
