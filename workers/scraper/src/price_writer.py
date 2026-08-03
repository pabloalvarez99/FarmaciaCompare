"""Persist scraped products with change-only price history and anomaly gates."""
from __future__ import annotations

import json
import uuid

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .anomaly import check_price
from .base_scraper import ScrapedProduct, normalize_image_url
from .matcher import DrugMatcher


class PriceWriter:
    def __init__(self, session: AsyncSession, pharmacy_id: str, matcher: DrugMatcher):
        self.session = session
        self.pharmacy_id = pharmacy_id
        self.matcher = matcher
        self.stats = {
            "written": 0,
            "price_rows": 0,
            "unchanged": 0,
            "quarantined": 0,
            "linked": 0,
            "unlinked": 0,
            "errors": 0,
        }

    async def write_product(self, product: ScrapedProduct) -> dict:
        result = await self.session.execute(
            text("""
                INSERT INTO pharmacy_products (
                    id, pharmacy_id, sku, raw_name, brand, laboratory, barcode,
                    source, image_url, attributes, is_active, created_at, updated_at
                )
                VALUES (
                    :id, :pharmacy_id, :sku, :raw_name, :brand, :laboratory, :barcode,
                    :source, :image_url, CAST(:attributes AS jsonb), true, NOW(), NOW()
                )
                ON CONFLICT (pharmacy_id, sku) DO UPDATE SET
                    raw_name = EXCLUDED.raw_name,
                    brand = EXCLUDED.brand,
                    laboratory = EXCLUDED.laboratory,
                    barcode = COALESCE(EXCLUDED.barcode, pharmacy_products.barcode),
                    -- Same rule as barcode: a run where the storefront happened
                    -- to omit the photo must not wipe an image we already have.
                    image_url = COALESCE(EXCLUDED.image_url, pharmacy_products.image_url),
                    attributes = COALESCE(EXCLUDED.attributes, pharmacy_products.attributes),
                    is_active = true,
                    updated_at = NOW()
                RETURNING id, medication_id
            """),
            {
                "id": str(uuid.uuid4()),
                "pharmacy_id": self.pharmacy_id,
                "sku": product.sku,
                "raw_name": product.name,
                "brand": product.brand,
                "laboratory": product.laboratory,
                "barcode": product.barcode,
                "source": product.source,
                # Every bind parameter in the statement above must have a key
                # here, present or not: a missing one raises InvalidRequestError
                # and the whole batch fails.
                #
                # Normalised here rather than in each connector: this is the one
                # place all ten chains funnel through, so a storefront that
                # starts returning unencoded spaces cannot poison the table, and
                # connectors added later get the guarantee for free.
                "image_url": normalize_image_url(product.image_url),
                # jsonb needs a JSON string, not a dict — asyncpg has no adapter
                # for a plain dict here.
                "attributes": json.dumps(product.attributes) if product.attributes else None,
            },
        )
        row = result.fetchone()
        pharmacy_product_id = str(row[0])
        medication_id = row[1]

        if not medication_id:
            attrs = product.attributes or {}
            is_med = attrs.get("isMedicine")
            if is_med is None:
                is_med = attrs.get("is_medicine")
            if isinstance(is_med, str):
                is_med = is_med.strip().lower() in ("1", "true", "yes", "si", "sí")
            match = self.matcher.match(
                product.name,
                barcode=product.barcode,
                brand=product.brand,
                is_medicine=is_med if isinstance(is_med, bool) else None,
            )
            if self.matcher.should_auto_link(match):
                medication_id = match.medication_id
                await self.session.execute(
                    text(
                        "UPDATE pharmacy_products SET medication_id = :mid WHERE id = :id"
                    ),
                    {"mid": medication_id, "id": pharmacy_product_id},
                )
                self.stats["linked"] += 1
            else:
                self.stats["unlinked"] += 1
                if match and match.grey_zone:
                    logger.debug(
                        f"grey-zone match sku={product.sku} "
                        f"conf={match.confidence:.2f} → {match.matched_name}"
                    )
        else:
            self.stats["linked"] += 1

        price_action = await self._maybe_write_price(pharmacy_product_id, product)
        self.stats["written"] += 1
        return {
            "pharmacy_product_id": pharmacy_product_id,
            "medication_id": medication_id,
            "price_action": price_action,
        }

    async def _maybe_write_price(
        self, pharmacy_product_id: str, product: ScrapedProduct
    ) -> str:
        if not product.price or product.price <= 0:
            return "skipped_zero"

        last = await self.session.execute(
            text("""
                SELECT price, original_price, stock_status
                FROM prices
                WHERE pharmacy_product_id = :ppid
                  AND source <> 'quarantine'
                ORDER BY recorded_at DESC
                LIMIT 1
            """),
            {"ppid": pharmacy_product_id},
        )
        last_row = last.fetchone()
        last_price = int(last_row[0]) if last_row else None

        # The name is what lets the single-unit floor apply: without it every
        # 90-130 CLP needle, tongue depressor and sachet is quarantined on
        # every run and never gets an accepted price at all.
        verdict = check_price(product.price, last_price, name=product.name)
        if not verdict.ok:
            logger.warning(
                f"quarantine price sku={product.sku} price={product.price} "
                f"last={last_price} reason={verdict.reason}"
            )
            self.stats["quarantined"] += 1
            await self.session.execute(
                text("""
                    INSERT INTO prices (
                        id, pharmacy_product_id, price, original_price, discount_pct,
                        stock_status, stock_quantity, source, recorded_at
                    )
                    VALUES (
                        :id, :ppid, :price, :original_price, :discount_pct,
                        :stock_status, :stock_quantity, 'quarantine', NOW()
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "ppid": pharmacy_product_id,
                    "price": product.price,
                    "original_price": product.original_price,
                    "discount_pct": product.discount_pct,
                    "stock_status": product.stock_status,
                    "stock_quantity": product.stock_quantity,
                },
            )
            return "quarantined"

        if last_row:
            same_price = int(last_row[0]) == product.price
            same_original = (last_row[1] or None) == (product.original_price or None)
            same_stock = (last_row[2] or None) == (product.stock_status or None)
            if same_price and same_original and same_stock:
                self.stats["unchanged"] += 1
                return "unchanged"

        await self.session.execute(
            text("""
                INSERT INTO prices (
                    id, pharmacy_product_id, price, original_price, discount_pct,
                    stock_status, stock_quantity, source, recorded_at
                )
                VALUES (
                    :id, :ppid, :price, :original_price, :discount_pct,
                    :stock_status, :stock_quantity, :source, NOW()
                )
            """),
            {
                "id": str(uuid.uuid4()),
                "ppid": pharmacy_product_id,
                "price": product.price,
                "original_price": product.original_price,
                "discount_pct": product.discount_pct,
                "stock_status": product.stock_status,
                "stock_quantity": product.stock_quantity,
                "source": product.source,
            },
        )
        self.stats["price_rows"] += 1
        return "inserted"

    async def write_batch(self, products: list[ScrapedProduct]) -> dict:
        """Write products and return deltas for this batch only."""
        before = dict(self.stats)
        for p in products:
            try:
                await self.write_product(p)
            except Exception as e:
                logger.error(f"Error writing product {p.sku}: {e}")
                self.stats["errors"] += 1
        await self.session.commit()
        return {k: self.stats[k] - before[k] for k in self.stats}
