from typing import Literal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from .models import ActiveIngredient, Medication, MedicationName
from .isp_importer import ISPRecord
from .normalizer import normalize_name
import uuid


class DatabaseWriter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_record(self, record: ISPRecord) -> Literal["created", "updated", "skipped"]:
        # Check if this ISP registration already exists
        existing = (
            await self.session.execute(
                select(Medication).where(Medication.isp_registration == record.isp_registration)
            )
        ).scalar_one_or_none()

        if existing:
            return "skipped"

        # Get or create active ingredient
        ingredient = await self._get_or_create_ingredient(record)

        # Create medication
        medication = Medication(
            id=str(uuid.uuid4()),
            name=record.product_name.title(),
            active_ingredient_id=ingredient.id,
            dosage=record.dosage,
            pharmaceutical_form=record.pharmaceutical_form,
            route_of_administration=record.route_of_administration,
            prescription_required=record.prescription_required,
            isp_registration=record.isp_registration,
        )
        self.session.add(medication)
        await self.session.flush()

        # Add brand name entry
        normalized = normalize_name(record.product_name)
        self.session.add(MedicationName(
            id=str(uuid.uuid4()),
            medication_id=medication.id,
            name=record.product_name.title(),
            name_type="brand",
            laboratory=record.laboratory or None,
            normalized_name=normalized,
        ))

        # Add generic name entry (active ingredient) if different
        generic_normalized = normalize_name(record.active_ingredient)
        if generic_normalized != normalized:
            self.session.add(MedicationName(
                id=str(uuid.uuid4()),
                medication_id=medication.id,
                name=record.active_ingredient,
                name_type="generic",
                normalized_name=generic_normalized,
            ))

        return "created"

    async def _get_or_create_ingredient(self, record: ISPRecord) -> ActiveIngredient:
        ingredient = (
            await self.session.execute(
                select(ActiveIngredient).where(
                    ActiveIngredient.name == record.active_ingredient
                )
            )
        ).scalar_one_or_none()

        if not ingredient:
            ingredient = ActiveIngredient(
                id=str(uuid.uuid4()),
                name=record.active_ingredient,
            )
            self.session.add(ingredient)
            await self.session.flush()

        return ingredient

    async def import_records(self, records: list[ISPRecord]) -> dict:
        stats: dict[str, int] = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
        for record in records:
            try:
                result = await self.upsert_record(record)
                stats[result] += 1
            except Exception as e:
                logger.error(f"Error importing {record.isp_registration}: {e}")
                stats["errors"] += 1

        await self.session.commit()
        return stats
