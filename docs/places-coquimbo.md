# Google Places — directorio físico (Coquimbo + expansión nacional)

> Doc original: Región de Coquimbo. Desde 2026-08-02 `discover-places` soporta
> varias regiones — ver §"Multi-región" al final.

## Proyecto y clave

- Proyecto GCP con Places habilitado: **`tablero-iner-maps`**
- APIs: `places-backend.googleapis.com`, `geocoding-backend.googleapis.com`, maps, routes, …
- Clave server (sin restricción de browser): **Tablero INER server**
  - resource: `projects/707448781980/locations/global/keys/e7a2adb4-dd06-4fbc-99d7-345377eea53a`
- También se habilitó Places/Geocoding en **`farmacia-compare-prod`** y se creó
  la key server **FarmaciaCompare Places server**
  (`projects/446315435132/locations/global/keys/d128352c-98f1-401a-a7f9-bfda82bc1e1d`).
  Preferir esa key para trabajo del producto; `tablero-iner-maps` sigue válida.
  **Nunca** poner la key en el frontend ni en git/vault. Solo
  `gcloud services api-keys get-key-string …` en runtime.

## Cargar la key (PowerShell)

```powershell
$env:GOOGLE_MAPS_API_KEY = (
  gcloud services api-keys get-key-string `
    projects/707448781980/locations/global/keys/e7a2adb4-dd06-4fbc-99d7-345377eea53a `
    --project=tablero-iner-maps --format="value(keyString)"
).Trim()
```

## Descubrir e importar

```powershell
cd workers/scraper
$env:PYTHONIOENCODING = "utf-8"
# DATABASE_URL from .env.production for import
Get-Content ../../.env.production | ForEach-Object {
  if ($_ -match '^DATABASE_URL=(.*)$') { $env:DATABASE_URL = $matches[1].Trim().Trim('"') }
}

# Descubrir (Text Search + Details)
.\.venv\Scripts\python.exe -m src.cli discover-places --region coquimbo --out data/coquimbo-places.json

# Solo 3 ciudades grandes:
.\.venv\Scripts\python.exe -m src.cli discover-places --region coquimbo `
  --city "La Serena" --city "Coquimbo" --city "Ovalle"

# Dry-run import
.\.venv\Scripts\python.exe -m src.cli import-places --from-json data/coquimbo-places.json --dry-run

# Import real a Cloud SQL (type=physical, rut=gp:<place_id>)
.\.venv\Scripts\python.exe -m src.cli import-places --from-json data/coquimbo-places.json
```

## Modelo

- `pharmacies.type = 'physical'`
- `pharmacies.region = 'Coquimbo'`
- `pharmacies.rut = 'gp:<google_place_id>'` (id estable; no es RUT chileno)
- `pharmacies.chain` inferido del nombre cuando es cadena conocida

## Costo

Text Search + Place Details por resultado. Empezar por La Serena / Coquimbo / Ovalle.
No re-correr en loop agresivo.

## Estado prod 2026-08-01

| Ciudad | ~locales (import bruto) |
|---|---|
| La Serena | 51 |
| Coquimbo | 42 |
| Ovalle | 35 |
| Illapel | 18 |
| Los Vilos | 9 |
| Vicuña | 7 |
| Salamanca | 7 |
| otras | Monte Patria, Andacollo, Pichidangui |

- Importados ~174; tras filtro anti-ruido + reactivación `farma*`/`farmacéutica*`: **~132 activos**.
- API live: `GET …/api/v1/products/pharmacies?region=Coquimbo` → 132
- Web: https://farmacia-compare-web.vercel.app/farmacias
- `is_active=false` para ortopedia/vet/perfumería/edificios (soft).

## Multi-región

`--region` acepta: `coquimbo`, `metropolitana`, `valparaiso`, `biobio`, `maule`,
`araucania`. Las listas de comunas viven en `src/places_discovery.py` (`REGIONS`,
un `RegionSpec` por región). El `out` por defecto es `data/<region>-places.json`.

```powershell
.\.venv\Scripts\python.exe -m src.cli discover-places --region metropolitana
.\.venv\Scripts\python.exe -m src.cli import-places --from-json data/metropolitana-places.json
```

Flags útiles: `--limit-cities N` (corre solo las N primeras comunas, para test de
costo) y `--city "X"` (repetible).

### Filtro estricto de región — no sacarlo

Text Search **cruza regiones**: la query `farmacia Providencia Santiago Chile`
devuelve "Farmacia La Providencia" que está en **La Serena, Coquimbo**. Sin filtro
ese resultado se importaba con `region='Metropolitana'` y, como el upsert hace
`region = COALESCE(:region, region)` sobre el `rut = gp:<place_id>` ya existente,
**le cambiaba la región a una farmacia de Coquimbo ya cargada**.

`discover_city(..., strict_region=True)` (default) usa `place_region_matches()`,
que descarta el resultado si:

1. el componente `country` no es `CL` — `region=cl` en Text Search es solo un
   *bias*, no un filtro: aparecieron farmacias en **Santiago de los Caballeros,
   República Dominicana** y en **Chaco, Argentina**;
2. `administrative_area_level_1` no resuelve exactamente a la región buscada —
   incluso una región chilena que no mapeamos (Ñuble, Antofagasta…) se descarta,
   porque tampoco es el target.

Solo se acepta sin verificar cuando **no hay components** (caso `--no-details`).
El log dice `N dropped: other región`.

### Costo — medido, no estimado

`discover-places` imprime al final `API requests: text_search=… place_details=… total=…`.

| Región | comunas | farmacias | requests |
|---|---|---|---|
| Metropolitana | 34 | 768 | 875 |
| Valparaíso | 18 | 438 | 478 |
| Biobío | 18 | 353 | 391 |
| Maule | 16 | 286 | 313 |
| Araucanía | 16 | 214 | 240 |
| **total** | **102** | **2.059** | **2.297** |

~22 requests por comuna en promedio (no 60): solo las comunas urbanas densas
topan las 3 páginas × 20 resultados. Place Details es el ~98% del gasto.

Place Details acá pide Contact (`formatted_phone_number`, `website`) y Atmosphere
(`rating`, `user_ratings_total`), así que cae en el SKU caro, no en Basic.
A tarifa legacy (~$25/1k details, ~$32/1k text search) las 5 regiones son ~US$60.
Usar `--limit-cities N` para tantear antes de correr una región entera.
