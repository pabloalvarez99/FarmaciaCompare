"""Free Chilean government open-data sources for the medication catalog.

No API keys. Cache downloads under data/official/ and re-use until TTL expires.
Sources: datos.gob.cl (ISP / ANAMED open datasets).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from loguru import logger

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "official"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 1 week — dumps rarely change daily

# Polite client for a free public portal
USER_AGENT = (
    "FarmaciaCompareBot/1.0 (+https://farmaciacompare.cl/bot; "
    "contact=bots@farmaciacompare.cl; purpose=medication-catalog)"
)


@dataclass(frozen=True)
class OfficialSource:
    key: str
    title: str
    url: str
    kind: str  # bioequiv | venta_directa | proteccion
    notes: str


# Canonical free ISP dumps published on datos.gob.cl (CKAN packages 10071, 10080, 1303).
OFFICIAL_SOURCES: list[OfficialSource] = [
    OfficialSource(
        key="bioequiv",
        title="Listado de productos equivalentes terapéuticos (ISP)",
        url=(
            "https://datos.gob.cl/dataset/7a6758f2-7c91-42c9-8fbe-cec006471a2c/"
            "resource/93df17ca-b694-4697-96b2-3dae87d9761d/download/listadocronologico2017.csv"
        ),
        kind="bioequiv",
        notes="Best structured free dump: active ingredient + brand + registro + lab.",
    ),
    OfficialSource(
        key="venta_directa",
        title="Nómina de productos de venta directa (farmacéuticos)",
        url="https://datos.gob.cl/uploads/recursos/Productos_farmaceuticos_vigentes_venta_directa.csv",
        kind="venta_directa",
        notes="OTC / direct-sale list. Name + registro + lab; dose/form from title.",
    ),
    OfficialSource(
        key="proteccion_datos",
        title="Nómina de productos farmacéuticos con protección de datos",
        url="https://datos.gob.cl/uploads/recursos/Productos_farmaceuticos_con_proteccion_de_datos.csv",
        kind="proteccion",
        notes="Small protected-data list; still free public CSV.",
    ),
]


def ensure_data_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def cached_path(source: OfficialSource) -> Path:
    ensure_data_dir()
    return DATA_DIR / f"{source.key}.csv"


def is_fresh(path: Path, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    age = time.time() - path.stat().st_mtime
    return age < ttl_seconds


def fetch_source(
    source: OfficialSource,
    *,
    force: bool = False,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Path:
    """Download one official CSV into the local cache. Returns path."""
    path = cached_path(source)
    if not force and is_fresh(path, ttl_seconds):
        logger.info(f"[{source.key}] cache hit {path} ({path.stat().st_size} bytes)")
        return path

    logger.info(f"[{source.key}] downloading {source.url}")
    headers = {"User-Agent": USER_AGENT, "Accept": "text/csv,*/*"}
    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        response = client.get(source.url)
        response.raise_for_status()
        path.write_bytes(response.content)
    logger.info(f"[{source.key}] saved {path} ({path.stat().st_size} bytes)")
    return path


def fetch_all(*, force: bool = False) -> dict[str, Path]:
    """Download every registered free source. Returns key → path."""
    out: dict[str, Path] = {}
    for source in OFFICIAL_SOURCES:
        try:
            out[source.key] = fetch_source(source, force=force)
        except Exception as exc:
            logger.error(f"[{source.key}] download failed: {exc}")
    return out
