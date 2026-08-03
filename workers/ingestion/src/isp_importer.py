"""Parse ISP / datos.gob.cl medication dumps into ISPRecord rows.

Supports:
- Internal canonical CSV (isp_sample.csv)
- Official free dumps with heterogeneous Spanish headers and `;` separators
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from loguru import logger

from .normalizer import (
    extract_dosage,
    extract_pharmaceutical_form,
    normalize_ingredient_name,
)

# Map any known header variant → canonical field name.
COLUMN_ALIASES: dict[str, str] = {
    # registro
    "NUMERO_REGISTRO": "NUMERO_REGISTRO",
    "N° REGISTRO": "NUMERO_REGISTRO",
    "Nº REGISTRO": "NUMERO_REGISTRO",
    "N REGISTRO": "NUMERO_REGISTRO",
    "REGISTRO": "NUMERO_REGISTRO",
    "N°": "NUMERO_REGISTRO",  # only when unambiguous — handled carefully below
    # product name
    "NOMBRE_PRODUCTO": "NOMBRE_PRODUCTO",
    "NOMBRE PRODUCTO": "NOMBRE_PRODUCTO",
    "PRODUCTO": "NOMBRE_PRODUCTO",
    "PRODUCTO ": "NOMBRE_PRODUCTO",
    # ingredient
    "PRINCIPIO_ACTIVO": "PRINCIPIO_ACTIVO",
    "PRINCIPIO ACTIVO": "PRINCIPIO_ACTIVO",
    # form / concentration
    "FORMA_FARMACEUTICA": "FORMA_FARMACEUTICA",
    "FORMA FARMACEUTICA": "FORMA_FARMACEUTICA",
    "CONCENTRACION": "CONCENTRACION",
    "CONCENTRACIÓN": "CONCENTRACION",
    # lab / titular
    "LABORATORIO": "LABORATORIO",
    "RAZON SOCIAL TITULAR": "LABORATORIO",
    "RAZÓN SOCIAL TITULAR": "LABORATORIO",
    "TITULAR": "LABORATORIO",
    # route / rx / sale condition
    "VIA_ADMINISTRACION": "VIA_ADMINISTRACION",
    "VIA ADMINISTRACION": "VIA_ADMINISTRACION",
    "REQUIERE_RECETA": "REQUIERE_RECETA",
    "CONDICION VENTA": "CONDICION_VENTA",
    "CONDICIÓN VENTA": "CONDICION_VENTA",
    "ESTADO": "ESTADO",
    "USO / TRATAMIENTO": "USO_TRATAMIENTO",
}


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
    source: str = "isp"

    @classmethod
    def from_row(cls, row: dict, *, source: str = "isp") -> "ISPRecord":
        raw_ingredient = str(row.get("PRINCIPIO_ACTIVO", "") or "").strip()
        raw_form = str(row.get("FORMA_FARMACEUTICA", "") or "").strip()
        raw_concentration = str(row.get("CONCENTRACION", "") or "").strip()
        raw_product = str(row.get("NOMBRE_PRODUCTO", "") or "").strip()
        raw_reg = str(row.get("NUMERO_REGISTRO", "") or "").strip()

        if not raw_product and not raw_reg:
            raise ValueError("row missing product name and registration")

        # Dosage: explicit concentration column, else parse product title.
        dosage = (
            extract_dosage(raw_concentration)
            or extract_dosage(raw_product)
            or (raw_concentration.replace(" ", "").lower() if raw_concentration else "")
            or ""
        )

        form = (
            extract_pharmaceutical_form(raw_form)
            if raw_form
            else extract_pharmaceutical_form(raw_product)
        ) or "otro"

        # Venta directa / OTC → no prescription; bioequiv often Rx.
        condicion = str(row.get("CONDICION_VENTA", "") or "").strip().upper()
        requiere = str(row.get("REQUIERE_RECETA", "") or "").strip().upper()
        if requiere in ("SI", "SÍ", "YES", "TRUE", "1"):
            rx = True
        elif requiere in ("NO", "FALSE", "0"):
            rx = False
        elif "DIRECTA" in condicion:
            rx = False
        else:
            # Unknown — default conservative for prescription-like forms
            rx = form in ("inyectable",) or bool(raw_ingredient)

        ingredient = raw_ingredient.title() if raw_ingredient else ""
        if not ingredient:
            # No active ingredient column — leave empty rather than inventing.
            ingredient = ""

        return cls(
            isp_registration=raw_reg or f"NAME:{raw_product[:40]}",
            product_name=raw_product or raw_reg,
            active_ingredient=ingredient,
            active_ingredient_normalized=normalize_ingredient_name(ingredient)
            if ingredient
            else "",
            pharmaceutical_form=form,
            dosage=dosage,
            laboratory=str(row.get("LABORATORIO", "") or "").strip(),
            route_of_administration=str(row.get("VIA_ADMINISTRACION", "") or "")
            .strip()
            .lower()
            or "oral",
            prescription_required=rx,
            source=source,
        )


class ISPImporter:
    """Load medication rows from canonical or official free government CSVs."""

    REQUIRED_MIN = ("NOMBRE_PRODUCTO",)  # registration preferred but optional

    def _read_dataframe(self, filepath: str) -> pd.DataFrame:
        path = Path(filepath)
        raw = path.read_bytes()
        # Official dumps are often Windows-1252 / latin-1 with `;`
        encodings = ("utf-8-sig", "utf-8", "latin-1", "cp1252")
        seps = (";", ",", "\t")
        last_err: Exception | None = None
        for enc in encodings:
            for sep in seps:
                try:
                    df = pd.read_csv(
                        filepath,
                        sep=sep,
                        encoding=enc,
                        dtype=str,
                        na_filter=False,
                        engine="python",
                    )
                    if len(df.columns) >= 2:
                        return df
                except Exception as exc:
                    last_err = exc
                    continue
        raise ValueError(f"Could not parse CSV {filepath}: {last_err}")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename headers to canonical fields.

        Bioequiv dumps have both ``N°`` (row index 1..N) and ``Registro``
        (F-18790/16). Prefer sanitary registration over the index.
        """
        # Build rename map carefully when multiple cols map to the same target.
        target_to_source: dict[str, str] = {}
        priority = {
            "NUMERO_REGISTRO": [
                "REGISTRO",
                "N° REGISTRO",
                "Nº REGISTRO",
                "N REGISTRO",
                "NUMERO_REGISTRO",
                "N°",
            ],
        }

        # Keep real DataFrame column objects as keys (trailing spaces matter for rename).
        col_meta: list[tuple[object, str]] = []
        for c in df.columns:
            upper = " ".join(str(c).strip().upper().split())
            col_meta.append((c, upper))

        # Prefer high-priority sources for contested fields (Registro over N°).
        for target, preferred in priority.items():
            for pref in preferred:
                for original, upper in col_meta:
                    if upper == pref:
                        target_to_source[target] = original
                        if pref != "N°":
                            break
                if target in target_to_source:
                    chosen_upper = next(
                        u for o, u in col_meta if o is target_to_source[target]
                    )
                    if chosen_upper != "N°":
                        break

        rename: dict[object, str] = {}
        used_targets: set[str] = set()
        for target, original in target_to_source.items():
            rename[original] = target
            used_targets.add(target)

        for original, upper in col_meta:
            if original in rename:
                continue
            target = COLUMN_ALIASES.get(upper)
            if target and target not in used_targets:
                rename[original] = target
                used_targets.add(target)
            elif not target:
                rename[original] = upper.replace(" ", "_")
            else:
                rename[original] = f"_drop_{upper.replace(' ', '_')}"

        out = df.rename(columns=rename)
        drop_cols = [c for c in out.columns if str(c).startswith("_drop_")]
        if drop_cols:
            out = out.drop(columns=drop_cols)

        if "NUMERO_REGISTRO" in out.columns:
            series = out["NUMERO_REGISTRO"]
            if isinstance(series, pd.DataFrame):
                out = out.loc[:, ~out.columns.duplicated(keep="last")]
                series = out["NUMERO_REGISTRO"]
            sample = series.astype(str).head(30).tolist()
            if sample and all(s.isdigit() or not s for s in sample):
                out = out.drop(columns=["NUMERO_REGISTRO"])

        return out

    def _detect_bioequiv_header(self, filepath: str) -> pd.DataFrame | None:
        """Bioequiv file has title rows before the real header."""
        for enc in ("latin-1", "cp1252", "utf-8"):
            try:
                lines = Path(filepath).read_text(encoding=enc).splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines[:20]):
                upper = line.upper()
                if "PRINCIPIO ACTIVO" in upper and "PRODUCTO" in upper and "REGISTRO" in upper:
                    df = pd.read_csv(
                        filepath,
                        sep=";",
                        encoding=enc,
                        dtype=str,
                        na_filter=False,
                        skiprows=i,
                        engine="python",
                    )
                    return df
        return None

    def load_csv(self, filepath: str, *, source: str | None = None) -> list[ISPRecord]:
        logger.info(f"Loading ISP dataset from {filepath}")
        path = Path(filepath)
        source = source or path.stem

        df: pd.DataFrame | None = None
        # Special-case bioequiv messy header
        if "bioequiv" in path.name.lower() or "listado" in path.name.lower():
            df = self._detect_bioequiv_header(filepath)

        if df is None:
            df = self._read_dataframe(filepath)

        df = self._normalize_columns(df)

        # Bioequiv: ensure Registro mapped (header "Registro")
        # After normalize, PRODUCTO / PRINCIPIO_ACTIVO / NUMERO_REGISTRO should exist.

        records: list[ISPRecord] = []
        errors = 0
        seen_reg: set[str] = set()

        for _, row in df.iterrows():
            canonical = {str(k).strip().upper(): str(v) for k, v in row.to_dict().items()}
            try:
                reg = str(canonical.get("NUMERO_REGISTRO", "")).strip()
                name = str(canonical.get("NOMBRE_PRODUCTO", "")).strip()
                if not name:
                    errors += 1
                    continue
                if name.lower().startswith("listado") or "bioequivalentes" in name.lower():
                    continue
                if reg.isdigit():
                    reg = ""
                    canonical["NUMERO_REGISTRO"] = ""
                if reg and reg in seen_reg:
                    continue
                record = ISPRecord.from_row(canonical, source=source)
                if reg:
                    seen_reg.add(reg)
                records.append(record)
            except Exception as e:
                errors += 1
                logger.debug(f"Skipping row: {e}")

        logger.info(f"Loaded {len(records)} records ({errors} skipped) from {path.name}")
        return records

    def load_excel(self, filepath: str, sheet_name: int = 0) -> list[ISPRecord]:
        logger.info(f"Loading ISP Excel dataset from {filepath}")
        df = pd.read_excel(filepath, sheet_name=sheet_name, dtype=str, na_filter=False)
        df = self._normalize_columns(df)
        records = []
        for _, row in df.iterrows():
            data = {str(k).strip().upper(): v for k, v in row.to_dict().items()}
            records.append(ISPRecord.from_row(data, source=Path(filepath).stem))
        return records

    def load_official_dir(self, directory: str | Path) -> list[ISPRecord]:
        """Load and merge every CSV under data/official/ (dedupe by registration)."""
        directory = Path(directory)
        if not directory.exists():
            return []
        merged: dict[str, ISPRecord] = {}
        for path in sorted(directory.glob("*.csv")):
            for rec in self.load_csv(str(path), source=path.stem):
                key = rec.isp_registration.upper()
                # Prefer rows that carry an active ingredient
                existing = merged.get(key)
                if existing is None:
                    merged[key] = rec
                elif not existing.active_ingredient and rec.active_ingredient:
                    merged[key] = rec
        logger.info(f"Merged official catalog: {len(merged)} unique registrations")
        return list(merged.values())
