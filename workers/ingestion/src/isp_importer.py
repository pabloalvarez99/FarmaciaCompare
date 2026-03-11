from dataclasses import dataclass
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

        dosage = (
            extract_dosage(raw_concentration)
            or extract_dosage(raw_product)
            or raw_concentration
        )

        return cls(
            isp_registration=str(row.get("NUMERO_REGISTRO", "")).strip(),
            product_name=raw_product,
            active_ingredient=raw_ingredient.title(),
            active_ingredient_normalized=normalize_ingredient_name(raw_ingredient),
            pharmaceutical_form=(
                extract_pharmaceutical_form(raw_form)
                or extract_pharmaceutical_form(raw_product)
            ),
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
                logger.warning(f"Skipping row: {e}")

        logger.info(f"Loaded {len(records)} records ({errors} errors)")
        return records

    def load_excel(self, filepath: str, sheet_name: int = 0) -> list[ISPRecord]:
        logger.info(f"Loading ISP Excel dataset from {filepath}")
        df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str, na_filter=False)
        df.columns = [c.strip().upper() for c in df.columns]
        return [ISPRecord.from_row(row.to_dict()) for _, row in df.iterrows()]
