"""Upsert Google Places discoveries into `pharmacies` (type=physical)."""
from __future__ import annotations

import uuid
from pathlib import Path

from loguru import logger
from sqlalchemy import text

from .places_discovery import DiscoveredPharmacy, load_json


async def upsert_physical_pharmacies(
    pharmacies: list[DiscoveredPharmacy],
) -> dict[str, int]:
    """Insert or update physical pharmacies by Google place_id (stored in rut field as gp:...).

    We use `rut` as a stable external id bucket: `gp:<place_id>`. RUT legal is
    unknown from Places; this avoids unique collisions and makes re-runs idempotent.
    """
    from .db import AsyncSessionLocal

    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    async with AsyncSessionLocal() as session:
        for ph in pharmacies:
            if not ph.place_id or not ph.name:
                stats["skipped"] += 1
                continue
            external = f"gp:{ph.place_id}"
            existing = await session.execute(
                text("SELECT id FROM pharmacies WHERE rut = :rut LIMIT 1"),
                {"rut": external},
            )
            row = existing.fetchone()
            if row:
                await session.execute(
                    text(
                        """
                        UPDATE pharmacies SET
                          name = :name,
                          chain = COALESCE(:chain, chain),
                          address = COALESCE(:address, address),
                          city = COALESCE(:city, city),
                          region = COALESCE(:region, region),
                          lat = COALESCE(:lat, lat),
                          lng = COALESCE(:lng, lng),
                          phone = COALESCE(:phone, phone),
                          website = COALESCE(:website, website),
                          rating = COALESCE(:rating, rating),
                          rating_count = COALESCE(:rating_count, rating_count),
                          is_active = true,
                          updated_at = NOW()
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": str(row[0]),
                        "name": ph.name,
                        "chain": ph.chain,
                        "address": ph.address,
                        "city": ph.city,
                        "region": ph.region,
                        "lat": ph.lat,
                        "lng": ph.lng,
                        "phone": ph.phone,
                        "website": ph.website or ph.google_maps_uri,
                        "rating": ph.rating,
                        "rating_count": ph.rating_count or 0,
                    },
                )
                stats["updated"] += 1
            else:
                await session.execute(
                    text(
                        """
                        INSERT INTO pharmacies (
                          id, name, chain, type, rut, address, city, region,
                          lat, lng, phone, website, is_active, has_delivery, has_pickup,
                          rating, rating_count, created_at, updated_at
                        ) VALUES (
                          :id, :name, :chain, 'physical', :rut, :address, :city, :region,
                          :lat, :lng, :phone, :website, true, false, true,
                          :rating, :rating_count, NOW(), NOW()
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "name": ph.name,
                        "chain": ph.chain,
                        "rut": external,
                        "address": ph.address,
                        "city": ph.city,
                        "region": ph.region,
                        "lat": ph.lat,
                        "lng": ph.lng,
                        "phone": ph.phone,
                        "website": ph.website or ph.google_maps_uri,
                        "rating": ph.rating,
                        "rating_count": ph.rating_count or 0,
                    },
                )
                stats["inserted"] += 1
        await session.commit()
    logger.info(f"upsert physical pharmacies: {stats}")
    return stats


async def import_from_json(path: Path) -> dict[str, int]:
    return await upsert_physical_pharmacies(load_json(path))
