"""Elasticsearch indexer for medications catalog."""

import asyncio
import os

from elasticsearch import AsyncElasticsearch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://farmacia:farmacia@localhost:5432/farmaciacompare",
)


async def index_all_medications():
    """Fetch all medications from DB and bulk-index into Elasticsearch."""
    es = AsyncElasticsearch([ES_URL])
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(
            text("""
                SELECT
                    m.id,
                    m.name,
                    ai.name AS active_ingredient_name,
                    m.dosage,
                    m.pharmaceutical_form,
                    m.prescription_required,
                    ARRAY_AGG(DISTINCT mn.name) AS brand_names,
                    MIN(p.price) AS lowest_price,
                    COUNT(DISTINCT pp.pharmacy_id) AS pharmacy_count
                FROM medications m
                LEFT JOIN active_ingredients ai ON ai.id = m.active_ingredient_id
                LEFT JOIN medication_names mn ON mn.medication_id = m.id
                LEFT JOIN pharmacy_products pp ON pp.medication_id = m.id AND pp.is_active = true
                LEFT JOIN LATERAL (
                    SELECT price FROM prices
                    WHERE pharmacy_product_id = pp.id
                    ORDER BY recorded_at DESC LIMIT 1
                ) p ON true
                GROUP BY m.id, ai.name
            """)
        )

        operations = []
        for row in result:
            doc = {
                "id": str(row[0]),
                "name": row[1],
                "activeIngredientName": row[2],
                "dosage": row[3],
                "pharmaceuticalForm": row[4],
                "prescriptionRequired": row[5],
                "brandNames": [n for n in (row[6] or []) if n],
                "lowestPrice": row[7],
                "pharmacyCount": row[8] or 0,
            }
            operations.append({"index": {"_index": "medications", "_id": doc["id"]}})
            operations.append(doc)

        if operations:
            await es.bulk(operations=operations)
            await es.indices.refresh(index="medications")
            print(f"Indexed {len(operations) // 2} medications")
        else:
            print("No medications to index")

    await engine.dispose()
    await es.close()


if __name__ == "__main__":
    asyncio.run(index_all_medications())
