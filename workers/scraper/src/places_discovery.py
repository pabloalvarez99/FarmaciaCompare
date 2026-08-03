"""Discover physical pharmacies via Google Places (legacy Text Search).

Uses `GOOGLE_MAPS_API_KEY` from the environment. Prefer loading it with:

  gcloud services api-keys get-key-string \\
    projects/707448781980/locations/global/keys/e7a2adb4-dd06-4fbc-99d7-345377eea53a \\
    --project=tablero-iner-maps --format="value(keyString)"

Do not commit keys. Key lives on project `tablero-iner-maps` (Places backend).
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from loguru import logger

# Región de Coquimbo — comunas con farmacias relevantes.
COQUIMBO_CITIES: list[str] = [
    "La Serena",
    "Coquimbo",
    "Ovalle",
    "Illapel",
    "Vicuña",
    "Andacollo",
    "Salamanca",
    "Los Vilos",
    "Monte Patria",
    "Combarbalá",
    "Paihuano",
    "Canela",
]

REGION_NAME = "Coquimbo"

# Región Metropolitana — comunas por población (mayores primero).
METROPOLITANA_CITIES: list[str] = [
    "Santiago",
    "Puente Alto",
    "Maipú",
    "La Florida",
    "San Bernardo",
    "Las Condes",
    "Ñuñoa",
    "Peñalolén",
    "Pudahuel",
    "Quilicura",
    "Providencia",
    "Estación Central",
    "La Pintana",
    "Recoleta",
    "Renca",
    "El Bosque",
    "Conchalí",
    "Macul",
    "San Miguel",
    "Quinta Normal",
    "Cerro Navia",
    "La Granja",
    "Independencia",
    "Colina",
    "Melipilla",
    "Talagante",
    "Buin",
    "Lo Barnechea",
    "Vitacura",
    "La Reina",
    "Cerrillos",
    "La Cisterna",
    "Lo Prado",
    "Peñaflor",
]

# Región de Valparaíso.
VALPARAISO_CITIES: list[str] = [
    "Valparaíso",
    "Viña del Mar",
    "Quilpué",
    "Villa Alemana",
    "San Antonio",
    "Quillota",
    "San Felipe",
    "Los Andes",
    "La Calera",
    "Limache",
    "Concón",
    "Casablanca",
    "La Ligua",
    "Cartagena",
    "El Quisco",
    "Algarrobo",
    "Quintero",
    "Olmué",
]

# Región del Biobío.
BIOBIO_CITIES: list[str] = [
    "Concepción",
    "Talcahuano",
    "Chiguayante",
    "San Pedro de la Paz",
    "Hualpén",
    "Coronel",
    "Lota",
    "Penco",
    "Tomé",
    "Los Ángeles",
    "Cañete",
    "Curanilahue",
    "Lebu",
    "Arauco",
    "Nacimiento",
    "Mulchén",
    "Yumbel",
    "Hualqui",
]

# Región del Maule.
MAULE_CITIES: list[str] = [
    "Talca",
    "Curicó",
    "Linares",
    "Constitución",
    "Cauquenes",
    "Molina",
    "San Javier",
    "Parral",
    "San Clemente",
    "Villa Alegre",
    "Longaví",
    "Colbún",
    "Teno",
    "Sagrada Familia",
    "Río Claro",
    "Retiro",
]

# Región de La Araucanía.
ARAUCANIA_CITIES: list[str] = [
    "Temuco",
    "Padre Las Casas",
    "Villarrica",
    "Angol",
    "Victoria",
    "Nueva Imperial",
    "Lautaro",
    "Pucón",
    "Collipulli",
    "Traiguén",
    "Loncoche",
    "Pitrufquén",
    "Gorbea",
    "Carahue",
    "Freire",
    "Curacautín",
]


@dataclass(frozen=True)
class RegionSpec:
    """A discoverable region: slug for the CLI, `pharmacies.region` value, cities."""

    slug: str
    name: str
    cities: list[str]
    # Extra words appended to the text query to disambiguate comuna names that
    # repeat across regions (e.g. "Independencia", "San Pedro de la Paz").
    query_hint: str = ""


REGIONS: dict[str, RegionSpec] = {
    "coquimbo": RegionSpec("coquimbo", "Coquimbo", COQUIMBO_CITIES),
    "metropolitana": RegionSpec(
        "metropolitana", "Metropolitana", METROPOLITANA_CITIES, "Santiago"
    ),
    "valparaiso": RegionSpec(
        "valparaiso", "Valparaíso", VALPARAISO_CITIES, "Región de Valparaíso"
    ),
    "biobio": RegionSpec("biobio", "Biobío", BIOBIO_CITIES, "Región del Biobío"),
    "maule": RegionSpec("maule", "Maule", MAULE_CITIES, "Región del Maule"),
    "araucania": RegionSpec(
        "araucania", "Araucanía", ARAUCANIA_CITIES, "Región de La Araucanía"
    ),
}

# Billed request counters, so a run can report real API volume.
REQUEST_COUNTS: dict[str, int] = {"text_search": 0, "place_details": 0}


def reset_request_counts() -> None:
    REQUEST_COUNTS["text_search"] = 0
    REQUEST_COUNTS["place_details"] = 0

# Map storefront name → our pharmacies.chain slug (online scrapers use same).
_CHAIN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cruz\s*verde", re.I), "cruz_verde"),
    (re.compile(r"salcobrand", re.I), "salcobrand"),
    (re.compile(r"ahumada|magnae", re.I), "ahumada"),
    (re.compile(r"dr\.?\s*simi|farmacias?\s+similares", re.I), "dr_simi"),
    (re.compile(r"\bknop\b", re.I), "knop"),
    (re.compile(r"farmaloop", re.I), "farmaloop"),
    (re.compile(r"\bcurie\b", re.I), "curie"),
    (re.compile(r"\bfarmex\b", re.I), "farmex"),
    (re.compile(r"mercado\s*farma", re.I), "mercadofarma"),
    (re.compile(r"preunic", re.I), "preunic"),
    (re.compile(r"dr\.?\s*amigo", re.I), "dr_amigo"),
    (re.compile(r"tempofarma", re.I), "tempofarma"),
    (re.compile(r"farmacia\s+del\s+pueblo", re.I), "farmacia_del_pueblo"),
    (re.compile(r"farmacia\s+popular", re.I), "farmacia_popular"),
]

# Name signals for pharmacy-like results (Chile chains + generic).
_PHARMACY_NAME_RE = re.compile(
    r"farmacia|farmaceutic|botica|\bfarma\b|farma[a-z]|"  # farma*, farmacéutica
    r"cruz\s*verde|salcobrand|ahumada|simi|\bknop\b|"
    r"dr\.?\s*amigo|tempofarma|easyfarma|farmavid|favibar",
    re.I,
)
# Clear non-pharmacy verticals — drop unless name also contains 'farmacia'.
_NON_PHARMACY_RE = re.compile(
    r"ortop[eé]dic|[oó]ptic[ao]?s?|laboratorio|veterinari|perfumer[ií]a",
    re.I,
)

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


@dataclass(frozen=True)
class DiscoveredPharmacy:
    place_id: str
    name: str
    address: str | None
    city: str | None
    region: str
    lat: float | None
    lng: float | None
    phone: str | None
    website: str | None
    rating: float | None
    rating_count: int | None
    chain: str | None
    google_maps_uri: str | None
    business_status: str | None
    types: list[str]
    query_city: str


def infer_chain(name: str) -> str | None:
    for pattern, chain in _CHAIN_PATTERNS:
        if pattern.search(name or ""):
            return chain
    return None


def looks_like_pharmacy(name: str, types: list[str] | None = None) -> bool:
    """True if Places result is pharmacy-like; filters orthopedics/optics/lab noise.

    Accept when Google type includes `pharmacy`, or the name matches common
    pharmacy/chain tokens. Reject orthopedics, optics, labs, veterinary, and
    perfume shops unless the name also contains 'farmacia'.
    """
    types = types or []
    n = name or ""
    has_farmacia = bool(re.search(r"farmacia", n, re.I))
    if _NON_PHARMACY_RE.search(n) and not has_farmacia:
        return False
    if "pharmacy" in types:
        return True
    if _PHARMACY_NAME_RE.search(n):
        return True
    return False


def _api_key() -> str:
    key = (os.environ.get("GOOGLE_MAPS_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "GOOGLE_MAPS_API_KEY is not set. Load from gcloud api-keys get-key-string "
            "(tablero-iner-maps Tablero INER server key)."
        )
    return key


def _http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "FarmaciaCompareBot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def text_search(query: str, *, page_token: str | None = None) -> dict[str, Any]:
    params: dict[str, str] = {
        "query": query,
        "language": "es",
        "region": "cl",
        "key": _api_key(),
    }
    if page_token:
        params["pagetoken"] = page_token
    url = TEXT_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    REQUEST_COUNTS["text_search"] += 1
    return _http_get_json(url)


def place_details(place_id: str) -> dict[str, Any]:
    params = {
        "place_id": place_id,
        "language": "es",
        "fields": "place_id,name,formatted_address,geometry,formatted_phone_number,"
        "international_phone_number,website,url,rating,user_ratings_total,"
        "business_status,types,address_component",
        "key": _api_key(),
    }
    url = PLACE_DETAILS_URL + "?" + urllib.parse.urlencode(params)
    REQUEST_COUNTS["place_details"] += 1
    return _http_get_json(url)


# Google returns administrative_area_level_1 as e.g. "Coquimbo",
# "Región Metropolitana", "Región del Biobío". Normalize to our short names.
_REGION_ALIASES: dict[str, str] = {
    "coquimbo": "Coquimbo",
    "metropolitana": "Metropolitana",
    "metropolitana de santiago": "Metropolitana",
    "santiago metropolitan": "Metropolitana",
    "valparaiso": "Valparaíso",
    "biobio": "Biobío",
    "bio bio": "Biobío",
    "maule": "Maule",
    "araucania": "Araucanía",
}


def _strip_accents(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    )


def region_from_components(components: list[dict] | None) -> str | None:
    """Canonical `pharmacies.region` from Places address components, or None.

    Returns None when the component is missing or unknown, so callers can fall
    back to the queried region instead of dropping the result.
    """
    if not components:
        return None
    raw = None
    for c in components:
        if "administrative_area_level_1" in (c.get("types") or []):
            raw = c.get("long_name") or c.get("short_name")
            break
    if not raw:
        return None
    key = _strip_accents(raw).lower().strip()
    key = re.sub(r"^regi[oó]n\s+(de\s+la|del|de)\s+", "", key)
    key = re.sub(r"^regi[oó]n\s+", "", key)
    key = re.sub(r"^(la|el)\s+", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    return _REGION_ALIASES.get(key)


def _country_code(components: list[dict] | None) -> str | None:
    for c in components or []:
        if "country" in (c.get("types") or []):
            return (c.get("short_name") or "").upper() or None
    return None


def place_region_matches(components: list[dict] | None, target_region: str) -> bool:
    """True if the place really sits in `target_region` (Chile).

    `region=cl` on Text Search is only a bias, not a filter — queries have
    returned pharmacies in Santiago de los Caballeros, República Dominicana. And
    an unmapped Chilean región (Ñuble, Antofagasta…) is by definition not the
    target, so it must be dropped rather than relabelled.

    Only a missing/unreadable component list is given the benefit of the doubt,
    since `--no-details` runs have no components at all.
    """
    if not components:
        return True
    country = _country_code(components)
    if country and country != "CL":
        return False
    has_admin1 = any(
        "administrative_area_level_1" in (c.get("types") or []) for c in components
    )
    if not has_admin1:
        return True
    return region_from_components(components) == target_region


def _city_from_components(components: list[dict] | None, fallback: str) -> str:
    if not components:
        return fallback
    locality = None
    admin2 = None
    for c in components:
        types = c.get("types") or []
        if "locality" in types:
            locality = c.get("long_name")
        if "administrative_area_level_2" in types:
            admin2 = c.get("long_name")
    return locality or admin2 or fallback


def _parse_result(
    raw: dict,
    query_city: str,
    details: dict | None = None,
    region: str = REGION_NAME,
) -> DiscoveredPharmacy:
    d = details or {}
    loc = (raw.get("geometry") or d.get("geometry") or {}).get("location") or {}
    name = d.get("name") or raw.get("name") or ""
    address = d.get("formatted_address") or raw.get("formatted_address")
    components = d.get("address_components")
    city = _city_from_components(components, query_city)
    phone = d.get("formatted_phone_number") or d.get("international_phone_number")
    rating = d.get("rating") if d.get("rating") is not None else raw.get("rating")
    rating_count = (
        d.get("user_ratings_total")
        if d.get("user_ratings_total") is not None
        else raw.get("user_ratings_total")
    )
    return DiscoveredPharmacy(
        place_id=raw.get("place_id") or d.get("place_id") or "",
        name=name,
        address=address,
        city=city,
        region=region,
        lat=float(loc["lat"]) if loc.get("lat") is not None else None,
        lng=float(loc["lng"]) if loc.get("lng") is not None else None,
        phone=phone,
        website=d.get("website"),
        rating=float(rating) if rating is not None else None,
        rating_count=int(rating_count) if rating_count is not None else None,
        chain=infer_chain(name),
        google_maps_uri=d.get("url"),
        business_status=d.get("business_status") or raw.get("business_status"),
        types=list(d.get("types") or raw.get("types") or []),
        query_city=query_city,
    )


def discover_city(
    city: str,
    *,
    with_details: bool = True,
    max_pages: int = 3,
    sleep_s: float = 2.1,
    region: str = REGION_NAME,
    query_hint: str = "",
    strict_region: bool = True,
) -> list[DiscoveredPharmacy]:
    """Text search `farmacia {city} [hint] Chile` with pagination.

    With `strict_region`, results whose Places address components resolve to a
    different región are dropped. Text search leaks across regions (a "farmacia
    Providencia Santiago" query returns "Farmacia La Providencia" in La Serena),
    and importing those would relabel existing rows of another región.
    """
    query = f"farmacia {city} {query_hint} Chile" if query_hint else f"farmacia {city} Chile"
    logger.info(f"Places text search: {query!r}")
    found: dict[str, DiscoveredPharmacy] = {}
    page_token: str | None = None
    dropped_region = 0

    for page in range(max_pages):
        if page_token:
            time.sleep(sleep_s)  # Google requires short wait before next_page_token works
        data = text_search(query, page_token=page_token)
        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            logger.warning(f"Places status={status} error={data.get('error_message')}")
            break
        for raw in data.get("results") or []:
            pid = raw.get("place_id")
            if not pid or pid in found:
                continue
            types = raw.get("types") or []
            name = raw.get("name") or ""
            if not looks_like_pharmacy(name, types):
                continue
            details = None
            if with_details:
                try:
                    det = place_details(pid)
                    if det.get("status") == "OK":
                        details = det.get("result") or {}
                    time.sleep(0.15)
                except Exception as exc:
                    logger.warning(f"details failed for {pid}: {exc}")
            if strict_region and details:
                if not place_region_matches(details.get("address_components"), region):
                    dropped_region += 1
                    continue
            found[pid] = _parse_result(raw, city, details, region=region)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    suffix = f" ({dropped_region} dropped: other región)" if dropped_region else ""
    logger.info(f"{city}: {len(found)} unique places{suffix}")
    return list(found.values())


def discover_region(
    cities: list[str] | None = None,
    *,
    with_details: bool = True,
    region: str = REGION_NAME,
    query_hint: str = "",
    strict_region: bool = True,
) -> list[DiscoveredPharmacy]:
    cities = cities or COQUIMBO_CITIES
    by_id: dict[str, DiscoveredPharmacy] = {}
    for city in cities:
        for ph in discover_city(
            city,
            with_details=with_details,
            region=region,
            query_hint=query_hint,
            strict_region=strict_region,
        ):
            prev = by_id.get(ph.place_id)
            if not prev or (ph.phone and not prev.phone):
                by_id[ph.place_id] = ph
    return sorted(by_id.values(), key=lambda p: (p.city or "", p.name))


def save_json(
    pharmacies: list[DiscoveredPharmacy], path: Path, region: str = REGION_NAME
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "region": region,
        "source": "google_places_textsearch",
        "count": len(pharmacies),
        "pharmacies": [asdict(p) for p in pharmacies],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Wrote {len(pharmacies)} pharmacies → {path}")


def load_json(path: Path) -> list[DiscoveredPharmacy]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DiscoveredPharmacy(**row) for row in data.get("pharmacies") or []]
