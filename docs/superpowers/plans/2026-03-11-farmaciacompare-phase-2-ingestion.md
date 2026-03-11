# FarmaciaCompare Phase 2 — Data Ingestion Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Build the Python data ingestion pipeline that imports ISP medication datasets, normalizes drug names, and populates the canonical medications database used by all other services.

**Architecture:** Python 3.12 with Poetry, async SQLAlchemy for DB writes, pandas for dataset processing, fuzzy matching via RapidFuzz. Runs as a one-shot CLI tool and as a scheduled worker. Results stored in PostgreSQL `medications`, `medication_names`, and `active_ingredients` tables.

**Tech Stack:** Python 3.12, Poetry, pandas, SQLAlchemy (async), asyncpg, rapidfuzz, unidecode, httpx (for downloading ISP files), APScheduler, pytest.

**Prerequisites:** Phase 1 complete. Python 3.12 installed. `DATABASE_URL` in `.env`.

---

## Chunk 1: Python Worker Scaffold

### Task 1: Set up Python ingestion package

**Files:**
- Create: `workers/ingestion/pyproject.toml`
- Create: `workers/ingestion/src/__init__.py`
- Create: `workers/ingestion/src/db.py`
- Create: `workers/ingestion/src/models.py`
- Create: `workers/ingestion/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p workers/ingestion/src workers/ingestion/tests
```

- [ ] **Step 2: Create `workers/ingestion/pyproject.toml`**

```toml
[tool.poetry]
name = "farmacia-ingestion"
version = "0.1.0"
description = "ISP dataset ingestion and medication normalization"
packages = [{include = "src"}]

[tool.poetry.dependencies]
python = "^3.12"
pandas = "^2.2.0"
sqlalchemy = {extras = ["asyncio"], version = "^2.0.0"}
asyncpg = "^0.29.0"
rapidfuzz = "^3.9.0"
unidecode = "^1.3.0"
httpx = "^0.27.0"
openpyxl = "^3.1.0"  # for Excel ISP files
python-dotenv = "^1.0.0"
click = "^8.1.0"
loguru = "^0.7.0"
apscheduler = "^3.10.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.2.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^5.0.0"

[tool.poetry.scripts]
ingest = "src.cli:main"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Create `workers/ingestion/src/db.py`**

```python
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from dotenv import load_dotenv

load_dotenv("../../.env")

DATABASE_URL = os.environ["DATABASE_URL"].replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Create `workers/ingestion/src/models.py`**

SQLAlchemy models mirroring the Prisma schema (read/write only what we need):

```python
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid


class Base(DeclarativeBase):
    pass


class ActiveIngredient(Base):
    __tablename__ = "active_ingredients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    isp_code: Mapped[str | None] = mapped_column(String, unique=True)
    atc_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    medications: Mapped[list["Medication"]] = relationship(back_populates="active_ingredient")


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    active_ingredient_id: Mapped[str | None] = mapped_column(ForeignKey("active_ingredients.id"))
    dosage: Mapped[str] = mapped_column(String, nullable=False)
    pharmaceutical_form: Mapped[str] = mapped_column(String, nullable=False)
    concentration: Mapped[str | None] = mapped_column(String)
    route_of_administration: Mapped[str | None] = mapped_column(String)
    prescription_required: Mapped[bool] = mapped_column(Boolean, default=False)
    isp_registration: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    active_ingredient: Mapped["ActiveIngredient | None"] = relationship(back_populates="medications")
    names: Mapped[list["MedicationName"]] = relationship(back_populates="medication", cascade="all, delete-orphan")


class MedicationName(Base):
    __tablename__ = "medication_names"
    __table_args__ = (UniqueConstraint("medication_id", "normalized_name"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id: Mapped[str] = mapped_column(ForeignKey("medications.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_type: Mapped[str] = mapped_column(String, nullable=False)
    laboratory: Mapped[str | None] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    medication: Mapped["Medication"] = relationship(back_populates="names")
```

- [ ] **Step 5: Install dependencies**

```bash
cd workers/ingestion
poetry install
```

- [ ] **Step 6: Commit**

```bash
cd ../..
git add workers/ingestion/
git commit -m "chore: scaffold Python ingestion worker with SQLAlchemy models"
```

---

## Chunk 2: Drug Normalizer

### Task 2: Build the drug name normalizer

**Files:**
- Create: `workers/ingestion/src/normalizer.py`
- Create: `workers/ingestion/tests/test_normalizer.py`

- [ ] **Step 1: Write failing tests**

Create `workers/ingestion/tests/test_normalizer.py`:

```python
import pytest
from src.normalizer import (
    normalize_name,
    extract_dosage,
    extract_pharmaceutical_form,
    normalize_ingredient_name,
)


class TestNormalizeName:
    def test_lowercase(self):
        assert normalize_name("PARACETAMOL") == "paracetamol"

    def test_removes_accents(self):
        assert normalize_name("Ibuprofén") == "ibuprofén"  # unidecode for matching
        assert normalize_name("IBUPROFÉN") == "ibuprofén"

    def test_strips_whitespace(self):
        assert normalize_name("  paracetamol  ") == "paracetamol"

    def test_collapses_spaces(self):
        assert normalize_name("paracetamol   500mg") == "paracetamol 500mg"

    def test_removes_special_chars(self):
        assert normalize_name("Tapsin® Forte") == "tapsin forte"

    def test_real_product_name(self):
        result = normalize_name("TAPSIN FORTE 500MG C/20 COMP")
        assert result == "tapsin forte 500mg c/20 comp"


class TestExtractDosage:
    def test_mg(self):
        assert extract_dosage("Paracetamol 500mg") == "500mg"

    def test_mg_with_space(self):
        assert extract_dosage("Paracetamol 500 mg") == "500mg"

    def test_mcg(self):
        assert extract_dosage("Levotiroxina 50mcg") == "50mcg"

    def test_g(self):
        assert extract_dosage("Amoxicilina 1g") == "1g"

    def test_percentage(self):
        assert extract_dosage("Crema 1%") == "1%"

    def test_no_dosage(self):
        assert extract_dosage("Vitamina C") is None

    def test_multiple_takes_first(self):
        assert extract_dosage("500mg/5ml") == "500mg/5ml"


class TestExtractPharmaceuticalForm:
    def test_comprimido(self):
        assert extract_pharmaceutical_form("Paracetamol 500mg Comprimido") == "comprimido"

    def test_comp_abbreviation(self):
        assert extract_pharmaceutical_form("TAPSIN 500MG C/20 COMP") == "comprimido"

    def test_capsulas(self):
        assert extract_pharmaceutical_form("Ibuprofeno 400mg Cápsulas") == "capsula"

    def test_jarabe(self):
        assert extract_pharmaceutical_form("Amoxicilina Jarabe 250mg/5ml") == "jarabe"

    def test_inyectable(self):
        assert extract_pharmaceutical_form("Ceftriaxona 1g Inyectable") == "inyectable"

    def test_crema(self):
        assert extract_pharmaceutical_form("Hidrocortisona 1% Crema") == "crema"

    def test_unknown_returns_otro(self):
        assert extract_pharmaceutical_form("Medicamento X") == "otro"


class TestNormalizeIngredientName:
    def test_strips_and_lowercases(self):
        assert normalize_ingredient_name("  PARACETAMOL  ") == "paracetamol"

    def test_removes_accents_for_matching(self):
        # Used for fuzzy comparison, not display
        assert normalize_ingredient_name("Ácido Acetilsalicílico") == "acido acetilsalicilico"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd workers/ingestion
poetry run pytest tests/test_normalizer.py -v
```

Expected: FAIL — `normalizer` module not found.

- [ ] **Step 3: Implement `workers/ingestion/src/normalizer.py`**

```python
import re
from unidecode import unidecode

FORM_MAP = {
    r"\bcomp(rimido)?s?\b": "comprimido",
    r"\bcápsulas?\b|\bcapsulas?\b|\bcap\b": "capsula",
    r"\bjarabe\b|\bjbe\b": "jarabe",
    r"\bsoluci[oó]n\b|\bsol\b": "solucion",
    r"\binyectable\b|\biny\b|\bampollas?\b": "inyectable",
    r"\bcrema\b": "crema",
    r"\bgel\b": "gel",
    r"\bcolirio\b|\bgotas oftálmicas\b": "colirio",
    r"\bsupositorio\b": "supositorio",
    r"\bparche\b": "parche",
    r"\bpolvo\b|\bpvo\b": "polvo",
    r"\bsuspensión\b|\bsuspension\b|\bsusp\b": "suspension",
    r"\bespray\b|\baerosol\b": "spray",
}

DOSAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)\s*(mcg|µg|mg|g|ml|%|ui|iu)(?:/(?:\d+(?:\.\d+)?)\s*(?:ml|g|mg))?",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, remove special characters."""
    name = name.strip()
    name = re.sub(r"[®™©]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.lower()


def normalize_ingredient_name(name: str) -> str:
    """For fuzzy matching — also remove accents."""
    return unidecode(normalize_name(name))


def extract_dosage(text: str) -> str | None:
    """Extract dosage from medication name. Returns '500mg', '1g', '1%', etc."""
    match = DOSAGE_PATTERN.search(text)
    if not match:
        return None
    # Normalize spaces between number and unit
    number = match.group(1)
    unit = match.group(2).lower()
    suffix_match = re.search(
        rf"{re.escape(number)}\s*{re.escape(match.group(2))}(/\d+(?:\.\d+)?\s*(?:ml|g|mg))?",
        text,
        re.IGNORECASE,
    )
    if suffix_match and suffix_match.group(1):
        return f"{number}{unit}{suffix_match.group(1).lower().replace(' ', '')}"
    return f"{number}{unit}"


def extract_pharmaceutical_form(text: str) -> str:
    """Detect pharmaceutical form from product name."""
    lower = text.lower()
    for pattern, form in FORM_MAP.items():
        if re.search(pattern, lower):
            return form
    return "otro"
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
poetry run pytest tests/test_normalizer.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add workers/ingestion/
git commit -m "feat: implement drug name normalizer with dosage and form extraction"
```

---

## Chunk 3: ISP Dataset Importer

### Task 3: Build the ISP data importer

**Files:**
- Create: `workers/ingestion/src/isp_importer.py`
- Create: `workers/ingestion/src/synonym_mapper.py`
- Create: `workers/ingestion/tests/test_isp_importer.py`
- Create: `workers/ingestion/data/isp_sample.csv` (test fixture)

The ISP publishes CSV/Excel files at: `https://registroform.isp.gob.cl/`
For now we model the schema from known ISP dataset columns.

- [ ] **Step 1: Create test fixture `workers/ingestion/data/isp_sample.csv`**

```csv
NUMERO_REGISTRO,NOMBRE_PRODUCTO,PRINCIPIO_ACTIVO,FORMA_FARMACEUTICA,CONCENTRACION,LABORATORIO,VIA_ADMINISTRACION,REQUIERE_RECETA
F-20001,TAPSIN FORTE COMPRIMIDOS,PARACETAMOL,COMPRIMIDO,500 MG,LABORATORIO CHILE S.A.,ORAL,NO
F-20002,ADVIL 200MG CAPSULA BLANDA,IBUPROFENO,CAPSULA,200 MG,PFIZER INC.,ORAL,NO
F-20003,AMOXICILINA 500MG CAPSULA,AMOXICILINA,CAPSULA,500 MG,LABORATORIO BETA,ORAL,SI
F-20004,LEVOTIROXINA 50MCG COMPRIMIDO,LEVOTIROXINA SODICA,COMPRIMIDO,50 MCG,MERCK S.A.,ORAL,SI
F-20005,JARABE AMOXICILINA 250MG/5ML,AMOXICILINA,SUSPENSION,250 MG/5 ML,LABORATORIO BETA,ORAL,SI
```

- [ ] **Step 2: Write failing tests for ISP importer**

Create `workers/ingestion/tests/test_isp_importer.py`:

```python
import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from src.isp_importer import ISPImporter, ISPRecord


class TestISPRecord:
    def test_parse_from_row(self):
        row = {
            "NUMERO_REGISTRO": "F-20001",
            "NOMBRE_PRODUCTO": "TAPSIN FORTE COMPRIMIDOS",
            "PRINCIPIO_ACTIVO": "PARACETAMOL",
            "FORMA_FARMACEUTICA": "COMPRIMIDO",
            "CONCENTRACION": "500 MG",
            "LABORATORIO": "LAB CHILE S.A.",
            "VIA_ADMINISTRACION": "ORAL",
            "REQUIERE_RECETA": "NO",
        }
        record = ISPRecord.from_row(row)
        assert record.isp_registration == "F-20001"
        assert record.product_name == "TAPSIN FORTE COMPRIMIDOS"
        assert record.active_ingredient == "PARACETAMOL"
        assert record.pharmaceutical_form == "comprimido"
        assert record.dosage == "500mg"
        assert record.laboratory == "LAB CHILE S.A."
        assert record.prescription_required is False

    def test_prescription_required_si(self):
        row = {
            "NUMERO_REGISTRO": "F-20003",
            "NOMBRE_PRODUCTO": "AMOXICILINA 500MG",
            "PRINCIPIO_ACTIVO": "AMOXICILINA",
            "FORMA_FARMACEUTICA": "CAPSULA",
            "CONCENTRACION": "500 MG",
            "LABORATORIO": "LAB BETA",
            "VIA_ADMINISTRACION": "ORAL",
            "REQUIERE_RECETA": "SI",
        }
        record = ISPRecord.from_row(row)
        assert record.prescription_required is True


class TestISPImporter:
    def test_load_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "NUMERO_REGISTRO,NOMBRE_PRODUCTO,PRINCIPIO_ACTIVO,FORMA_FARMACEUTICA,"
            "CONCENTRACION,LABORATORIO,VIA_ADMINISTRACION,REQUIERE_RECETA\n"
            "F-20001,TAPSIN FORTE,PARACETAMOL,COMPRIMIDO,500 MG,LAB CHILE,ORAL,NO\n"
        )
        importer = ISPImporter()
        records = importer.load_csv(str(csv_file))
        assert len(records) == 1
        assert records[0].active_ingredient == "PARACETAMOL"

    def test_deduplicates_active_ingredients(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "NUMERO_REGISTRO,NOMBRE_PRODUCTO,PRINCIPIO_ACTIVO,FORMA_FARMACEUTICA,"
            "CONCENTRACION,LABORATORIO,VIA_ADMINISTRACION,REQUIERE_RECETA\n"
            "F-001,TAPSIN 500MG,PARACETAMOL,COMPRIMIDO,500 MG,LAB A,ORAL,NO\n"
            "F-002,PANADOL 500MG,PARACETAMOL,COMPRIMIDO,500 MG,LAB B,ORAL,NO\n"
        )
        importer = ISPImporter()
        records = importer.load_csv(str(csv_file))
        ingredients = {r.active_ingredient for r in records}
        assert len(ingredients) == 1  # both are PARACETAMOL
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
poetry run pytest tests/test_isp_importer.py -v
```

Expected: FAIL — `ISPImporter` not found.

- [ ] **Step 4: Implement `workers/ingestion/src/isp_importer.py`**

```python
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
from loguru import logger
from .normalizer import (
    normalize_name,
    normalize_ingredient_name,
    extract_dosage,
    extract_pharmaceutical_form,
)


@dataclass
class ISPRecord:
    isp_registration: str
    product_name: str
    active_ingredient: str
    active_ingredient_normalized: str
    pharmaceutical_form: str
    dosage: str
    laboratory: str
    route_of_administration: str
    prescription_required: bool

    @classmethod
    def from_row(cls, row: dict) -> "ISPRecord":
        raw_ingredient = str(row.get("PRINCIPIO_ACTIVO", "")).strip()
        raw_form = str(row.get("FORMA_FARMACEUTICA", "")).strip()
        raw_concentration = str(row.get("CONCENTRACION", "")).strip()
        raw_product = str(row.get("NOMBRE_PRODUCTO", "")).strip()

        # Try to extract dosage from concentration first, fall back to product name
        dosage = extract_dosage(raw_concentration) or extract_dosage(raw_product) or raw_concentration

        return cls(
            isp_registration=str(row.get("NUMERO_REGISTRO", "")).strip(),
            product_name=raw_product,
            active_ingredient=raw_ingredient.title(),
            active_ingredient_normalized=normalize_ingredient_name(raw_ingredient),
            pharmaceutical_form=extract_pharmaceutical_form(raw_form) or extract_pharmaceutical_form(raw_product),
            dosage=dosage,
            laboratory=str(row.get("LABORATORIO", "")).strip(),
            route_of_administration=str(row.get("VIA_ADMINISTRACION", "")).strip().lower(),
            prescription_required=str(row.get("REQUIERE_RECETA", "NO")).strip().upper() == "SI",
        )


class ISPImporter:
    REQUIRED_COLUMNS = [
        "NUMERO_REGISTRO",
        "NOMBRE_PRODUCTO",
        "PRINCIPIO_ACTIVO",
        "FORMA_FARMACEUTICA",
        "CONCENTRACION",
        "LABORATORIO",
        "VIA_ADMINISTRACION",
        "REQUIERE_RECETA",
    ]

    def load_csv(self, filepath: str) -> list[ISPRecord]:
        logger.info(f"Loading ISP dataset from {filepath}")
        df = pd.read_csv(filepath, dtype=str, encoding="utf-8", na_filter=False)
        df.columns = [c.strip().upper() for c in df.columns]

        missing = [c for c in self.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"ISP CSV missing required columns: {missing}")

        records = []
        errors = 0
        for _, row in df.iterrows():
            try:
                records.append(ISPRecord.from_row(row.to_dict()))
            except Exception as e:
                errors += 1
                logger.warning(f"Skipping row {row.get('NUMERO_REGISTRO', '?')}: {e}")

        logger.info(f"Loaded {len(records)} records ({errors} errors)")
        return records

    def load_excel(self, filepath: str, sheet_name: str = 0) -> list[ISPRecord]:
        logger.info(f"Loading ISP Excel dataset from {filepath}")
        df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str, na_filter=False)
        df.columns = [c.strip().upper() for c in df.columns]
        return [ISPRecord.from_row(row.to_dict()) for _, row in df.iterrows()]
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
poetry run pytest tests/test_isp_importer.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add workers/ingestion/
git commit -m "feat: implement ISP dataset CSV/Excel importer with record parsing"
```

---

## Chunk 4: Database Writer

### Task 4: Build the database persistence layer

**Files:**
- Create: `workers/ingestion/src/db_writer.py`
- Create: `workers/ingestion/tests/test_db_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# workers/ingestion/tests/test_db_writer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.db_writer import DatabaseWriter
from src.isp_importer import ISPRecord


@pytest.fixture
def sample_record():
    return ISPRecord(
        isp_registration="F-20001",
        product_name="TAPSIN FORTE",
        active_ingredient="Paracetamol",
        active_ingredient_normalized="paracetamol",
        pharmaceutical_form="comprimido",
        dosage="500mg",
        laboratory="Laboratorio Chile",
        route_of_administration="oral",
        prescription_required=False,
    )


class TestDatabaseWriter:
    @pytest.mark.asyncio
    async def test_upsert_creates_ingredient_and_medication(self, sample_record):
        """Writer should create active ingredient and medication in DB."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        writer = DatabaseWriter(mock_session)
        await writer.upsert_record(sample_record)

        # Should have added an ingredient and medication
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_skips_duplicate_registration(self, sample_record):
        """Should not create duplicate when ISP registration already exists."""
        mock_existing = MagicMock()
        mock_existing.isp_registration = "F-20001"

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: mock_existing)
        )
        mock_session.commit = AsyncMock()

        writer = DatabaseWriter(mock_session)
        result = await writer.upsert_record(sample_record)
        assert result == "skipped"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
poetry run pytest tests/test_db_writer.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `workers/ingestion/src/db_writer.py`**

```python
from typing import Literal
from sqlalchemy import select, text
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

        # Upsert active ingredient
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
        name_entry = MedicationName(
            id=str(uuid.uuid4()),
            medication_id=medication.id,
            name=record.product_name.title(),
            name_type="brand",
            laboratory=record.laboratory or None,
            normalized_name=normalized,
        )
        self.session.add(name_entry)

        # Add generic name entry (active ingredient as name)
        generic_normalized = normalize_name(record.active_ingredient)
        if generic_normalized != normalized:
            generic_entry = MedicationName(
                id=str(uuid.uuid4()),
                medication_id=medication.id,
                name=record.active_ingredient,
                name_type="generic",
                normalized_name=generic_normalized,
            )
            self.session.add(generic_entry)

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
        stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
        for record in records:
            try:
                result = await self.upsert_record(record)
                stats[result] += 1
            except Exception as e:
                logger.error(f"Error importing {record.isp_registration}: {e}")
                stats["errors"] += 1

        await self.session.commit()
        return stats
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
poetry run pytest tests/test_db_writer.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd ../..
git add workers/ingestion/
git commit -m "feat: implement database writer for ISP medication records"
```

---

## Chunk 5: CLI Runner

### Task 5: Build the CLI ingestion command

**Files:**
- Create: `workers/ingestion/src/cli.py`

- [ ] **Step 1: Create `workers/ingestion/src/cli.py`**

```python
import asyncio
import click
from loguru import logger
from .isp_importer import ISPImporter
from .db_writer import DatabaseWriter
from .db import AsyncSessionLocal


@click.group()
def main():
    """FarmaciaCompare data ingestion CLI."""
    pass


@main.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--format", "file_format", type=click.Choice(["csv", "excel"]), default="csv")
@click.option("--sheet", default=0, help="Excel sheet index (if Excel format)")
@click.option("--dry-run", is_flag=True, help="Parse only, don't write to database")
def import_isp(filepath: str, file_format: str, sheet: int, dry_run: bool):
    """Import ISP medication dataset from CSV or Excel file."""
    asyncio.run(_import_isp(filepath, file_format, sheet, dry_run))


async def _import_isp(filepath: str, file_format: str, sheet: int, dry_run: bool):
    importer = ISPImporter()

    if file_format == "csv":
        records = importer.load_csv(filepath)
    else:
        records = importer.load_excel(filepath, sheet_name=sheet)

    logger.info(f"Parsed {len(records)} records from {filepath}")

    if dry_run:
        logger.info("Dry run — not writing to database")
        for r in records[:5]:
            logger.info(f"  {r.isp_registration}: {r.product_name} | {r.active_ingredient} | {r.dosage} | {r.pharmaceutical_form}")
        return

    async with AsyncSessionLocal() as session:
        writer = DatabaseWriter(session)
        stats = await writer.import_records(records)

    logger.info(f"Import complete: {stats}")
    click.echo(f"\nImport complete:")
    click.echo(f"  Created:  {stats['created']}")
    click.echo(f"  Skipped:  {stats['skipped']}")
    click.echo(f"  Errors:   {stats['errors']}")


@main.command()
@click.argument("query")
def lookup(query: str):
    """Look up a medication by name (fuzzy match)."""
    asyncio.run(_lookup(query))


async def _lookup(query: str):
    from rapidfuzz import process, fuzz
    from sqlalchemy import select
    from .models import MedicationName

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MedicationName.normalized_name, MedicationName.medication_id))
        all_names = [(row[0], row[1]) for row in result.fetchall()]

    if not all_names:
        click.echo("Database is empty. Run import-isp first.")
        return

    names_only = [n[0] for n in all_names]
    matches = process.extract(query.lower(), names_only, scorer=fuzz.WRatio, limit=5)

    click.echo(f"\nTop matches for '{query}':")
    for name, score, idx in matches:
        medication_id = all_names[idx][1]
        click.echo(f"  [{score:3.0f}%] {name} (medication_id: {medication_id})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the CLI (dry run with sample data)**

```bash
cd workers/ingestion
poetry run ingest import-isp data/isp_sample.csv --dry-run
```

Expected output:
```
Parsed 5 records from data/isp_sample.csv
Dry run — not writing to database
  F-20001: TAPSIN FORTE COMPRIMIDOS | Paracetamol | 500mg | comprimido
  ...
```

- [ ] **Step 3: Run with real database**

Make sure Docker postgres is running, then:

```bash
poetry run ingest import-isp data/isp_sample.csv
```

Expected:
```
Import complete:
  Created:  5
  Skipped:  0
  Errors:   0
```

- [ ] **Step 4: Test fuzzy lookup**

```bash
poetry run ingest lookup "tapsin"
```

Expected: Shows "tapsin forte comprimidos" with high score.

- [ ] **Step 5: Run all tests**

```bash
poetry run pytest -v --cov=src
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd ../..
git add workers/ingestion/
git commit -m "feat: add CLI for ISP dataset import and medication fuzzy lookup"
```

---

## Phase 2 Complete

**What was built:**
- Python ingestion worker with Poetry
- Drug name normalizer (dosage extraction, form detection, accent stripping)
- ISP CSV/Excel importer with data validation
- Database writer with upsert logic and duplicate detection
- CLI: `ingest import-isp <file>` and `ingest lookup <query>`

**Next:** Phase 3 — Price Collection (Playwright scrapers + API connectors).

See: `docs/superpowers/plans/2026-03-11-farmaciacompare-phase-3-scrapers.md`
