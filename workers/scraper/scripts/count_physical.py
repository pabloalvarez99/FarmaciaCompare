import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    url = os.environ["DATABASE_URL"]
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    eng = create_async_engine(url)
    async with eng.connect() as c:
        print("by type/region:")
        for row in (
            await c.execute(
                text(
                    "SELECT type, region, count(*) FROM pharmacies GROUP BY 1, 2 ORDER BY 3 DESC"
                )
            )
        ):
            print(row)
        print("physical Coquimbo by city:")
        for row in (
            await c.execute(
                text(
                    """
                    SELECT city, count(*) FROM pharmacies
                    WHERE type = 'physical' AND region = 'Coquimbo'
                    GROUP BY city ORDER BY 2 DESC
                    """
                )
            )
        ):
            print(row)
    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
