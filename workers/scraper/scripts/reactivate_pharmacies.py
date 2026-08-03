"""Re-activate physical Coquimbo pharmacies that pass looks_like_pharmacy."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.places_discovery import looks_like_pharmacy


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    eng = create_async_engine(url)
    async with eng.begin() as c:
        rows = (
            await c.execute(
                text(
                    """
                    SELECT id, name FROM pharmacies
                    WHERE type = 'physical' AND region = 'Coquimbo' AND is_active = false
                    """
                )
            )
        ).fetchall()
        reactivated: list[str] = []
        for pid, name in rows:
            if looks_like_pharmacy(name or ""):
                await c.execute(
                    text(
                        "UPDATE pharmacies SET is_active = true, updated_at = NOW() WHERE id = :id"
                    ),
                    {"id": str(pid)},
                )
                reactivated.append(name or "")
        print("reactivated", len(reactivated))
        for n in reactivated:
            print(" +", n)
        active = (
            await c.execute(
                text(
                    """
                    SELECT count(*) FROM pharmacies
                    WHERE type = 'physical' AND region = 'Coquimbo' AND is_active
                    """
                )
            )
        ).scalar()
        print("active physical Coquimbo", active)
    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
