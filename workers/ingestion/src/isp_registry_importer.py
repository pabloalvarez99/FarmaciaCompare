"""Import the *full* ISP sanitary registry into the medication catalog.

Why this exists
---------------
The catalog was seeded from a single pharmacy's inventory
(`tufarmacia_importer`). It holds what that one pharmacy stocked, so the large
chains sell thousands of drugs it has never heard of: of 600 unlinked
Salcobrand / Cruz Verde / Ahumada listings, 504 found *no candidate at all*.

The Instituto de Salud Pública publishes every product with a live sanitary
registration at https://registrosanitario.ispch.gob.cl/. That is the
authoritative universe of medicines legally sold in Chile, and it ships an
active ingredient for ~99% of pharmaceutical rows — which is exactly what the
generic alias needs to match a brand from one chain against a generic from
another.

Where the data comes from
-------------------------
The search page is ASP.NET WebForms. Its "Exportar a Excel" button
(`ImgBntExcel`) returns the *entire* result set in one response — an HTML
`<table>` served as `application/ms-excel`, cp1252, ~39 MB for the 46.434
products with `Estado = Vigente`. No pagination, one request, ~6 s.

The flow the button needs is not obvious and is encoded in `fetch_registry`:

1. GET `/` for `__VIEWSTATE` / `__EVENTVALIDATION`.
2. POST with `chkTipoBusqueda$0` (Nombre Producto) ticked and **no** search
   text. ASP.NET event validation rejects `txtNombreProducto` on this first
   POST because the textbox is not rendered until a criterion is ticked — and
   an empty criterion matches everything, which is what we want anyway.
3. POST again, with the viewstate from step 2, pressing `ImgBntExcel`.

`robots.txt` is absent on `registrosanitario.ispch.gob.cl` (404) and
`www.ispch.gob.cl` disallows only `/wp-admin/`, so this path is permitted.
Two requests per run is as light as a full-catalog refresh gets.

Scope
-----
The export mixes every product family the ISP registers. Only pharmaceutical
prefixes are imported (see `PHARMA_PREFIXES`); disinfectants (`D-`),
sanitizers (`S-`), pesticides (`P-`) and cosmetics (`…C-`) are not medicines
and would only add noise to a drug matcher.

Usage
-----
    python -m src.isp_registry_importer --fetch --dry-run
    python -m src.isp_registry_importer data/official/isp_registry.xls --dry-run
    python -m src.isp_registry_importer data/official/isp_registry.xls
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import html
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

# Reused verbatim: these carry bug fixes that must not be reintroduced —
# whole-word form matching, "15 mg/ml" not collapsing to "15 mg", and the
# digit/letter split that makes "400mg" and "400 mg" produce the same key.
from .tufarmacia_importer import (
    extract_dosage,
    extract_form,
    normalize_name,
    split_ingredients,
)

REGISTRY_URL = "https://registrosanitario.ispch.gob.cl/"
USER_AGENT = (
    "FarmaciaCompareBot/1.0 (+https://farmaciacompare.cl/bot; "
    "contact=bots@farmaciacompare.cl; purpose=medication-catalog)"
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "official"
DEFAULT_EXPORT = DATA_DIR / "isp_registry.xls"
VENTA_DIRECTA_CSV = DATA_DIR / "venta_directa.csv"

# `ddlEstado` option values, exactly as the page renders them.
ESTADO_VIGENTE = "Sí"
ESTADO_SUSPENDIDO = "Suspendido"
ESTADO_NO_VIGENTE = "No"

# Registration prefixes that denote a medicine. Everything else the ISP
# registers in the same table — `D-` disinfectants, `S-` sanitizers,
# `P-` pesticides, `<digits>C-` cosmetics — is not a drug.
#   F/FX  farmacéutico          B    biológico
#   N/NX  fitofármaco natural   H/HX homeopático
#   M/MX  medicamento especial  K/E  suplemento con registro sanitario
PHARMA_PREFIXES = frozenset({"F", "FX", "B", "N", "NX", "H", "HX", "M", "MX", "K", "E"})

# Prefixes that are over-the-counter by nature; `venta_directa.csv` only lists
# F- and B- registrations, so without this every herbal and homeopathic product
# would be flagged as prescription-only.
OTC_PREFIXES = frozenset({"N", "NX", "H", "HX", "K", "E"})

REGISTRATION_RE = re.compile(r"^([A-Z]+|\d+C{1,2})-\d+/\d+$", re.IGNORECASE)

# The ISP writes multi-ingredient products as "METFORMINA//VILDAGLIPTINA" and
# sometimes "Alfalfa T.M.;Oleum Jecor D3". `split_ingredients` splits on "/"
# already (and drops the empty token "//" leaves behind), so only ";" has to be
# translated before handing the string over.
INGREDIENT_SEPARATOR = "//"

# Bookkeeping markers the ISP appends to ingredient names; they are not part of
# the substance and would fragment `active_ingredients`, whose name is UNIQUE.
INGREDIENT_MARKER_RE = re.compile(r"\(\s*(?:\*|NUEVO)\s*\)", re.IGNORECASE)

# "ANFEBUTAMONA CLORHIDRATO (BUPROPIÓN)" — the parenthetical is a second name
# for the same substance, and chains list products under either one, so both
# are worth keeping as separate generic aliases.
INGREDIENT_ALIAS_RE = re.compile(r"\(([^()]{4,})\)")


@dataclass
class ISPProduct:
    """One row of the ISP registry export."""

    registration: str
    name: str
    registered_on: str
    company: str | None
    active_ingredient: str | None
    legal_control: str | None = None
    barcodes: list[str] = field(default_factory=list)

    @property
    def prefix(self) -> str:
        """'F-27355/23' -> 'F'; '2323C-355/22' -> '2323C'."""
        head, _, _ = self.registration.partition("-")
        return head.upper()

    @property
    def is_pharmaceutical(self) -> bool:
        return self.prefix in PHARMA_PREFIXES

    def _parsed_ingredients(self) -> tuple[list[str], list[str]]:
        """Split the ISP ingredient string into (substances, synonyms).

        Names are uppercased because `active_ingredients.name` is UNIQUE and
        the catalog already stores its existing rows that way — mixing
        "Aconitum D6" with "ACONITUM D6" would create two rows for one
        substance.
        """
        raw = INGREDIENT_MARKER_RE.sub(" ", self.active_ingredient or "")
        raw = raw.replace(";", INGREDIENT_SEPARATOR)

        substances: list[str] = []
        synonyms: list[str] = []
        for part in split_ingredients(raw):
            for alias in INGREDIENT_ALIAS_RE.findall(part):
                cleaned = " ".join(alias.split()).upper()
                if cleaned and cleaned not in synonyms:
                    synonyms.append(cleaned)
            # A stray "(" from an unbalanced ISP string leaves punctuation
            # behind; keep the readable head rather than the bracket.
            base = " ".join(INGREDIENT_ALIAS_RE.sub(" ", part).split()).upper()
            base = base.strip(" (),.-")
            if base and base not in substances:
                substances.append(base)
        return substances, [s for s in synonyms if s not in substances]

    @property
    def ingredients(self) -> list[str]:
        return self._parsed_ingredients()[0]

    @property
    def ingredient_synonyms(self) -> list[str]:
        """Alternative names the ISP gives in parentheses, e.g. "(BUPROPIÓN)".

        Chains list the same drug under either name, so each synonym earns its
        own generic alias.
        """
        return self._parsed_ingredients()[1]


def _cell_text(cell_html: str) -> str:
    """Strip tags, unescape entities and collapse whitespace inside one <td>."""
    text = re.sub(r"<[^>]+>", "", cell_html)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_registry(path: str | Path) -> list[ISPProduct]:
    """Parse the "Exportar a Excel" response.

    Despite the `.xls` name and `application/ms-excel` content type the payload
    is an HTML table in cp1252 — openpyxl and xlrd both reject it, so it is
    parsed as markup.
    """
    raw = Path(path).read_bytes()
    # cp1252 is what the response declares; fall back rather than crash on the
    # occasional stray byte in a company name.
    text = raw.decode("cp1252", errors="replace")

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", text, re.S | re.I)
    if not rows:
        raise SystemExit(f"No <tr> rows in {path} — is this the ISP export?")

    header = [_cell_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", rows[0], re.S | re.I)]
    index = {name.lower(): i for i, name in enumerate(header)}
    for required in ("registro", "nombre"):
        if required not in index:
            raise SystemExit(f"Export header missing '{required}': {header}")

    def column(cells: list[str], key: str) -> str:
        position = index.get(key)
        if position is None or position >= len(cells):
            return ""
        return cells[position]

    products: list[ISPProduct] = []
    malformed = 0
    for row in rows[1:]:
        cells = [_cell_text(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S | re.I)]
        registration = column(cells, "registro")
        name = column(cells, "nombre")
        if not registration or not name or not REGISTRATION_RE.match(registration):
            malformed += 1
            continue
        products.append(
            ISPProduct(
                registration=registration.upper(),
                name=name,
                registered_on=column(cells, "fecha registro"),
                company=column(cells, "empresa") or None,
                active_ingredient=column(cells, "principio activo") or None,
                legal_control=column(cells, "control legal") or None,
            )
        )

    logger.info(f"Registro ISP leído: {len(products)} filas ({malformed} descartadas) de {path}")
    return products


def load_otc_registrations(path: str | Path = VENTA_DIRECTA_CSV) -> set[str]:
    """Registrations sold without a prescription, from the datos.gob.cl dump.

    The registry export carries no sale-condition column, so this free CSV
    ("Nómina de productos de venta directa") is the only way to tell OTC from
    prescription-only without hitting one detail page per product.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"{path} no existe — todo F-/B- quedará como receta obligatoria")
        return set()

    registrations: set[str] = set()
    with path.open(encoding="cp1252", errors="replace", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            for key, value in row.items():
                if key and "registro" in key.lower() and value:
                    registrations.add(value.strip().upper())
                    break
    logger.info(f"Venta directa: {len(registrations)} registros OTC")
    return registrations


def select_pharmaceuticals(products: list[ISPProduct]) -> list[ISPProduct]:
    """Keep medicines, drop the rest, and collapse same-name duplicates.

    The ISP issues a fresh registration number every renewal, so the same drug
    appears several times under different numbers ("GALVUS COMPRIMIDOS 50 mg"
    is both F-27368/23 and F-21478/24). Importing all of them would create
    medications that are indistinguishable to the matcher, so one row per
    normalized name survives: the one that carries an active ingredient, and
    among those the most recently registered.
    """
    pharma = [p for p in products if p.is_pharmaceutical]

    best: dict[str, ISPProduct] = {}
    for product in pharma:
        key = normalize_name(product.name)
        if not key:
            continue
        current = best.get(key)
        if current is None:
            best[key] = product
            continue
        # An active ingredient is worth more than recency: it is what produces
        # the generic alias, and the alias is the whole point of this import.
        if bool(product.active_ingredient) != bool(current.active_ingredient):
            if product.active_ingredient:
                best[key] = product
            continue
        if product.registered_on > current.registered_on:
            best[key] = product

    logger.info(
        f"Farmacéuticos: {len(pharma)} filas → {len(best)} únicos por nombre normalizado "
        f"({len(products) - len(pharma)} no medicamentos descartados)"
    )
    return list(best.values())


# DER encoding of the id-ad-caIssuers access method OID (1.3.6.1.5.5.7.48.2)
# inside the Authority Information Access extension, followed by a context tag
# 6 (uniformResourceIdentifier). Enough to pull the issuer URL out of a
# certificate without depending on `cryptography`, which is not installed.
_CA_ISSUERS_OID = bytes.fromhex("06082B06010505073002")
_URI_TAG = 0x86


def _ca_issuer_url(certificate_der: bytes) -> str | None:
    """Read the CA Issuers URL out of a certificate's AIA extension."""
    start = certificate_der.find(_CA_ISSUERS_OID)
    if start < 0:
        return None
    cursor = start + len(_CA_ISSUERS_OID)
    if cursor + 1 >= len(certificate_der) or certificate_der[cursor] != _URI_TAG:
        return None
    length = certificate_der[cursor + 1]
    if length >= 0x80:  # long-form length: no real AIA URL is this long
        return None
    url = certificate_der[cursor + 2 : cursor + 2 + length]
    try:
        return url.decode("ascii")
    except UnicodeDecodeError:
        return None


def _completed_chain_context(host: str, port: int = 443):
    """Build an SSL context that can verify a host missing its intermediate.

    `registrosanitario.ispch.gob.cl` sends only its leaf certificate, so the
    default bundle cannot build a path and verification fails with "unable to
    get local issuer certificate".

    The fix is to do what a browser does: follow the leaf's Authority
    Information Access pointer, download the missing intermediate, and add it
    to the trust material. Verification stays fully on — the downloaded
    intermediate is only a bridge, and the chain must still terminate at a
    root already in `certifi`. A forged intermediate cannot satisfy that, so
    this is not a weakening of the check.
    """
    import ssl
    import tempfile

    import certifi
    import httpx

    leaf_pem = ssl.get_server_certificate((host, port))
    issuer_url = _ca_issuer_url(ssl.PEM_cert_to_DER_cert(leaf_pem))
    if not issuer_url:
        raise SystemExit(f"{host} no publica un CA Issuers en su AIA — no se puede completar la cadena")

    logger.info(f"Descargando el intermedio faltante de {host}: {issuer_url}")
    response = httpx.get(issuer_url, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    intermediate = response.content
    # CA Issuers is usually DER (.crt); accept PEM too.
    if intermediate.lstrip().startswith(b"-----BEGIN"):
        intermediate_pem = intermediate.decode("ascii")
    else:
        intermediate_pem = ssl.DER_cert_to_PEM_cert(intermediate)

    bundle = tempfile.NamedTemporaryFile(
        "w", suffix=".pem", delete=False, encoding="utf-8"
    )
    with bundle:
        bundle.write(Path(certifi.where()).read_text(encoding="utf-8"))
        bundle.write("\n")
        bundle.write(intermediate_pem)
    return ssl.create_default_context(cafile=bundle.name)


def fetch_registry(
    destination: str | Path = DEFAULT_EXPORT,
    *,
    estado: str = ESTADO_VIGENTE,
    timeout: float = 600.0,
) -> Path:
    """Download the whole registry through the page's Excel export button."""
    import httpx

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def hidden(page: str, name: str) -> str:
        match = re.search(r'id="%s"[^>]*value="([^"]*)"' % name, page)
        return html.unescape(match.group(1)) if match else ""

    def viewstate(page: str) -> dict[str, str]:
        return {
            "__EVENTTARGET": "",
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": hidden(page, "__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": hidden(page, "__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hidden(page, "__EVENTVALIDATION"),
            "__VIEWSTATEENCRYPTED": "",
        }

    def run(verify) -> bytes:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
        ) as client:
            landing = client.get(REGISTRY_URL).content.decode("utf-8", "replace")

            # Ticking "Nombre Producto" with no text matches every product.
            # The textbox itself must not be posted here: it is not rendered
            # until a criterion is ticked, and ASP.NET event validation
            # rejects unregistered fields with HTTP 500.
            search = viewstate(landing)
            search["ctl00$ContentPlaceHolder1$chkTipoBusqueda$0"] = "on"
            search["ctl00$ContentPlaceHolder1$ddlEstado"] = estado
            search["ctl00$ContentPlaceHolder1$btnBuscar"] = "Buscar"
            results = client.post(REGISTRY_URL, data=search).content.decode("utf-8", "replace")

            total = re.search(r'id="ctl00_ContentPlaceHolder1_lbl\w*"[^>]*>([\d.]+)</span>', results)
            if total:
                logger.info(f"Registro ISP ({estado}): {total.group(1)} productos")

            export = viewstate(results)
            export["ctl00$ContentPlaceHolder1$chkTipoBusqueda$0"] = "on"
            export["ctl00$ContentPlaceHolder1$txtNombreProducto"] = ""
            export["ctl00$ContentPlaceHolder1$ddlEstado"] = estado
            export["ctl00$ContentPlaceHolder1$ImgBntExcel.x"] = "10"
            export["ctl00$ContentPlaceHolder1$ImgBntExcel.y"] = "10"
            response = client.post(REGISTRY_URL, data=export)
            response.raise_for_status()
            return response.content

    try:
        payload = run(True)
    except Exception as exc:  # noqa: BLE001 — retried with a completed chain, then re-raised
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        host = REGISTRY_URL.split("//", 1)[1].strip("/")
        logger.warning(f"{host} no envía su cadena intermedia; completándola vía AIA")
        payload = run(_completed_chain_context(host))

    if b"<tr" not in payload[:4096]:
        raise SystemExit("La exportación no devolvió una tabla HTML — ¿cambió el formulario?")

    destination.write_bytes(payload)
    logger.info(f"Exportación guardada en {destination} ({len(payload)} bytes)")
    return destination


async def import_registry(
    products: list[ISPProduct],
    *,
    dry_run: bool = False,
    otc_registrations: set[str] | None = None,
) -> dict:
    """Insert medications that are not in the catalog yet.

    Nothing is ever updated or deleted: 30.970 pharmacy products already point
    at existing medications and a duplicate row would split those links. A
    product is skipped when its sanitary registration is already stored, or
    when its normalized name already exists in `medication_names` — in the
    latter case the drug is in the catalog under a different identifier and a
    second row would just make the matcher ambiguous.
    """
    from sqlalchemy import text

    from .db import AsyncSessionLocal  # type: ignore[attr-defined]

    otc_registrations = otc_registrations or set()
    stats = {
        "ingredients": 0,
        "medications": 0,
        "names": 0,
        "generic_aliases": 0,
        "skipped_registration": 0,
        "skipped_name": 0,
        "skipped_empty": 0,
    }

    async with AsyncSessionLocal() as session:
        rows = await session.execute(text("SELECT name, id FROM active_ingredients"))
        ingredient_ids: dict[str, str] = {name: str(pk) for name, pk in rows}

        rows = await session.execute(
            text("SELECT UPPER(isp_registration) FROM medications WHERE isp_registration IS NOT NULL")
        )
        known_registrations: set[str] = {r[0] for r in rows}

        rows = await session.execute(text("SELECT DISTINCT normalized_name FROM medication_names"))
        known_names: set[str] = {r[0] for r in rows}

        logger.info(
            f"Catálogo actual: {len(known_registrations)} registros, "
            f"{len(known_names)} nombres normalizados, {len(ingredient_ids)} principios activos"
        )

        for product in products:
            if product.registration in known_registrations:
                stats["skipped_registration"] += 1
                continue

            normalized = normalize_name(product.name)
            if not normalized:
                stats["skipped_empty"] += 1
                continue
            if normalized in known_names:
                stats["skipped_name"] += 1
                continue

            # Reserve both keys immediately so duplicates inside this batch are
            # caught even in --dry-run, where nothing reaches the database.
            known_registrations.add(product.registration)
            known_names.add(normalized)

            ingredients = product.ingredients
            primary = ingredients[0] if ingredients else None
            dosage = extract_dosage(product.name)
            aliases = generic_aliases(product, dosage, skip=normalized)

            ingredient_id = None
            if primary:
                ingredient_id = ingredient_ids.get(primary)
                if not ingredient_id:
                    ingredient_id = str(uuid.uuid4())
                    ingredient_ids[primary] = ingredient_id
                    stats["ingredients"] += 1
                    if not dry_run:
                        await session.execute(
                            text("""
                                INSERT INTO active_ingredients (id, name, created_at)
                                VALUES (:id, :name, NOW())
                                ON CONFLICT (name) DO NOTHING
                            """),
                            {"id": ingredient_id, "name": primary},
                        )

            stats["medications"] += 1
            stats["names"] += 1
            stats["generic_aliases"] += len(aliases)

            if dry_run:
                continue

            medication_id = str(uuid.uuid4())
            # Prisma's @updatedAt is applied by the client, not the database:
            # a raw INSERT has to set created_at and updated_at or it violates
            # NOT NULL.
            await session.execute(
                text("""
                    INSERT INTO medications (
                        id, name, active_ingredient_id, dosage, pharmaceutical_form,
                        prescription_required, isp_registration, barcodes,
                        therapeutic_action, laboratory, created_at, updated_at
                    )
                    VALUES (
                        :id, :name, :ingredient_id, :dosage, :form,
                        :prescription, :registration, :barcodes,
                        NULL, :laboratory, NOW(), NOW()
                    )
                """),
                {
                    "id": medication_id,
                    "name": product.name,
                    "ingredient_id": ingredient_id,
                    "dosage": dosage,
                    "form": extract_form(product.name, None),
                    "prescription": requires_prescription(product, otc_registrations),
                    "registration": product.registration,
                    "barcodes": product.barcodes,
                    "laboratory": product.company,
                },
            )

            await session.execute(
                text("""
                    INSERT INTO medication_names (
                        id, medication_id, name, name_type, laboratory,
                        normalized_name, created_at
                    )
                    VALUES (:id, :mid, :name, 'commercial', :lab, :normalized, NOW())
                    ON CONFLICT (medication_id, normalized_name) DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "mid": medication_id,
                    "name": product.name,
                    "lab": product.company,
                    "normalized": normalized,
                },
            )

            # The generic alias ("vildagliptina 50 mg") is what lets a branded
            # listing on one chain match an unbranded listing on another.
            for display, alias in aliases:
                await session.execute(
                    text("""
                        INSERT INTO medication_names (
                            id, medication_id, name, name_type, laboratory,
                            normalized_name, created_at
                        )
                        VALUES (:id, :mid, :name, 'generic', NULL, :normalized, NOW())
                        ON CONFLICT (medication_id, normalized_name) DO NOTHING
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "mid": medication_id,
                        "name": display,
                        "normalized": alias,
                    },
                )

            if stats["medications"] % 1000 == 0:
                await session.commit()
                logger.info(f"Importados {stats['medications']} medicamentos…")

        if not dry_run:
            await session.commit()

    return stats


def generic_aliases(
    product: ISPProduct, dosage: str, *, skip: str = ""
) -> list[tuple[str, str]]:
    """`(display name, normalized name)` for every generic form of a product.

    The primary substance gives the main alias ("vildagliptina 50 mg"). Each
    parenthetical synonym gives another, because a chain that lists
    "Bupropión 150mg" and one that lists "Anfebutamona 150mg" are selling the
    same drug and both spellings have to reach the same medication.

    `skip` drops an alias identical to the commercial name — that row would be
    rejected by the `(medication_id, normalized_name)` unique index anyway.
    """
    if not product.ingredients:
        return []

    out: list[tuple[str, str]] = []
    seen = {skip} if skip else set()
    for substance in [product.ingredients[0], *product.ingredient_synonyms]:
        display = f"{substance} {dosage}".strip()
        normalized = normalize_name(display)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append((display, normalized))
    return out


def requires_prescription(product: ISPProduct, otc_registrations: set[str]) -> bool:
    """Rx unless the ISP lists the registration as direct sale.

    Defaulting to `True` is the safe direction: showing a prescription warning
    on an OTC painkiller is a nuisance, hiding one on an antibiotic is not.
    """
    if product.registration in otc_registrations:
        return False
    return product.prefix not in OTC_PREFIXES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "export",
        nargs="?",
        help="Path to a saved ISP export (omit together with --fetch)",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help=f"Download a fresh export into {DEFAULT_EXPORT} before importing",
    )
    parser.add_argument(
        "--estado",
        default=ESTADO_VIGENTE,
        choices=[ESTADO_VIGENTE, ESTADO_SUSPENDIDO, ESTADO_NO_VIGENTE],
        help="Registration state to download (default: vigente)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.fetch:
        path = fetch_registry(args.export or DEFAULT_EXPORT, estado=args.estado)
    elif args.export:
        path = Path(args.export)
        if not path.exists():
            raise SystemExit(f"No existe {path} — usá --fetch para descargarlo")
    else:
        parser.error("pasá un archivo exportado o usá --fetch")

    products = select_pharmaceuticals(parse_registry(path))
    stats = asyncio.run(
        import_registry(
            products,
            dry_run=args.dry_run,
            otc_registrations=load_otc_registrations(),
        )
    )
    mode = "DRY-RUN" if args.dry_run else "IMPORT"
    logger.info(f"{mode} terminado: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
