import uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from .base_scraper import ScrapedProduct
from .matcher import DrugMatcher


class PriceWriter:
    def __init__(self, session: AsyncSession, pharmacy_id: str, matcher: DrugMatcher):
        self.session = session
        self.pharmacy_id = pharmacy_id
        self.matcher = matcher

    async def write_product(self, product: ScrapedProduct) -> dict:
        result = await self.session.execute(
            text("""
                INSERT INTO pharmacy_products (id, pharmacy_id, sku, raw_name, brand, laboratory, barcode, source, is_active)
                VALUES (:id, :pharmacy_id, :sku, :raw_name, :brand, :laboratory, :barcode, :source, true)
                ON CONFLICT (pharmacy_id, sku) DO UPDATE SET
                    raw_name = EXCLUDED.raw_name, brand = EXCLUDED.brand, is_active = true, updated_at = NOW()
                RETURNING id, medication_id
            """),
            {"id": str(uuid.uuid4()), "pharmacy_id": self.pharmacy_id, "sku": product.sku,
             "raw_name": product.name, "brand": product.brand, "laboratory": product.laboratory,
             "barcode": product.barcode, "source": product.source}
        )
        row = result.fetchone()
        pharmacy_product_id = str(row[0])
        existing_medication_id = row[1]

        medication_id = existing_medication_id
        if not medication_id:
            match = self.matcher.match(product.name)
            if match and match.confidence >= 0.85:
                medication_id = match.medication_id
                await self.session.execute(
                    text("UPDATE pharmacy_products SET medication_id = :mid WHERE id = :id"),
                    {"mid": medication_id, "id": pharmacy_product_id}
                )

        if product.price > 0:
            await self.session.execute(
                text("""
                    INSERT INTO prices (id, pharmacy_product_id, price, original_price, discount_pct, stock_status, stock_quantity, source)
                    VALUES (:id, :ppid, :price, :original_price, :discount_pct, :stock_status, :stock_quantity, :source)
                """),
                {"id": str(uuid.uuid4()), "ppid": pharmacy_product_id, "price": product.price,
                 "original_price": product.original_price, "discount_pct": product.discount_pct,
                 "stock_status": product.stock_status, "stock_quantity": product.stock_quantity,
                 "source": product.source}
            )
        return {"pharmacy_product_id": pharmacy_product_id, "medication_id": medication_id}

    async def write_batch(self, products: list[ScrapedProduct]) -> dict:
        stats = {"written": 0, "errors": 0}
        batch = []
        for product in products:
            batch.append(product)
            if len(batch) >= 100:
                for p in batch:
                    try:
                        await self.write_product(p)
                        stats["written"] += 1
                    except Exception as e:
                        logger.error(f"Error writing product {p.sku}: {e}")
                        stats["errors"] += 1
                await self.session.commit()
                batch = []
        if batch:
            for p in batch:
                try:
                    await self.write_product(p)
                    stats["written"] += 1
                except Exception as e:
                    logger.error(f"Error writing product {p.sku}: {e}")
                    stats["errors"] += 1
            await self.session.commit()
        return stats
