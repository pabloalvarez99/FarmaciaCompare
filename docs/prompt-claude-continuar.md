# Prompt de traspaso Grok → Claude CLI

Copiar **todo** lo que está bajo la línea `---`. Actualizado **2026-08-02 ~01:50**
America/Santiago (Grok loop ultrathink). Re-medí snapshot prod antes de escribir.

---

Vas a continuar **FarmaciaCompare**, comparador de precios de medicamentos Chile
en producción. Grok estuvo en loop (matcher + scrapes de imágenes/attrs +
Coquimbo). Claude vuelve post session-limit. **Leé este prompt entero** antes de
tocar código o prod.

## Qué es y por qué importa

Usuario busca "paracetamol" y ve precio por cadena online. Precios reales cruzan
mucho (Ozempic / Algiafin). **Regla no negociable:** ningún precio inventado ni
match falso a prod — es plata + salud. Fail-closed > cobertura.

**Foco geo:** Región de Coquimbo (directorio físico Places + web Coquimbo-first).
Precios online = nacionales (e-commerce).

## URLs prod

| Qué | URL |
|-----|-----|
| Web | https://farmacia-compare-web.vercel.app |
| `/farmacias` | https://farmacia-compare-web.vercel.app/farmacias |
| API | https://api-gateway-446315435132.southamerica-west1.run.app |
| Pharmacies Coquimbo | `GET /api/v1/products/pharmacies?region=Coquimbo` → **132 activas** (lat/lng OK) |
| Search c/ imágenes | `GET /api/v1/products/search?q=paracetamol` → `imageUrl` real multi-cadena |

Deploy web: **desde monorepo root** (`farmacia-compare-web`), **no** `apps/web`
(ese `.vercel` apunta a otro proyecto).

## Repo / paths

- Repo: `D:\Respaldo Proyectos\GitHub\02-products\FarmaciaCompare`
- Scraper: `workers/scraper/` · venv `.venv` · CLI `python -m src.cli …`
- Prod DB: `DATABASE_URL` desde **`.env.production`** (gitignored). **Nunca**
  pegar secretos en chat, vault, bitácora, ni Notion.
- Vault digest Grok: `D:\obsidian-mind\work\sessions\2026-08-02-grok.md`
- Bitácora: `bitacora.md` · coord: `docs/coordinacion-agentes.md`
- Places: `docs/places-coquimbo.md` · gcloud key proyecto `tablero-iner-maps`
  ("Tablero INER server") — solo env runtime `GOOGLE_MAPS_API_KEY`.

## Snapshot Cloud SQL (medido 2026-08-02 ~01:50)

Fleet activo ~**76.5k** productos · **~98%+ con `image_url`** · ~**29.5k** linked.

| Cadena | n | imgs | linked | attrs | isMed |
|--------|---|------|--------|-------|-------|
| farmex | 22276 | 22242 (100%) | 17084 | 22276 | 7289 |
| salcobrand | 12795 | **12741 (100%)** | 2742 | 12781 | 3507 |
| cruz_verde | 9839 | **~9500 (97%) mid-scrape** | 1211 | 9000* | 2545 |
| preunic | 8880 | 8880 | 0 | 8880 | 0 |
| ahumada | 5406 | **5406** | 1090 | 5406 | 2432 |
| mercadofarma | 4970 | 4784 | 776 | 4966 | 2610 |
| farmaloop | 4860 | 4786 | 3205 | **4860** | **3831** |
| curie | 4604 | 4598 | 2895 | 4604 | 3817 |
| knop | 1651 | 1651 | 0 | 1634 | 274 |
| dr_simi | 1294 | 1294 | 571 | 1294 | 840 |

\* CV attrs pueden ir detrás de imgs mientras corre el scrape.  
Físicas Coquimbo activas: **132**. Catálogo ISP: ~34k medications / ~35k names.

### Scrapes Grok cerró (logs en vault `cli-logs/`)

| Cadena | Log | Notas |
|--------|-----|--------|
| ahumada | `2026-08-02-scrape-ahumada.txt` | success, 100% imgs |
| salcobrand | `2026-08-02-scrape-salcobrand.txt` | success 12781 written, 0→100% imgs |
| farmaloop | `2026-08-02-scrape-farmaloop-attrs.txt` | success attrs 0→4860 + isMedicine |
| preunic | `2026-08-02-scrape-preunic.txt` | beauty, 0 linked OK |

**Aún corriendo al handoff:** proceso local `python -m src.cli scrape cruz_verde`
(desde ~23:08; n creció ~7.7k→9.8k). **No matarlo** si sigue vivo.  
db-f1-micro: **≤2 writers** concurrentes (mejor 1 mientras CV termina).

Snapshot rápido:

```powershell
cd "D:\Respaldo Proyectos\GitHub\02-products\FarmaciaCompare\workers\scraper"
# cargar DATABASE_URL desde ../../.env.production
.venv\Scripts\python.exe scripts\prod_snapshot.py
```

## Matcher fail-closed (Grok 2026-08-02) — **no deshacer**

Archivos: `workers/scraper/src/product_identity.py`, `matcher.py`, tests.

1. Combo inhaler `250/25 mcg` → `250/12.5mcg` form; pack `dosis`/`ds`.
2. **Coma decimal chilena:** `0,5` → `0.5` **antes** del noise strip (antes
   `0 5` → extraía `5mg` falso).
3. **Dosis `%`:** boundary `(?!\w)` no `\b` (antes **toda** dosis `%` se perdía).
4. Combo oftálmico dual `0,005 % / Timolol 0,5 %` → `0.005/0.5%`.
5. Combo tableta bare `20/12,5` → `20/12.5mg` (bloquea FP
   **Olmepress-D → olmesartan solo**).
6. Cosméticos / pack / volume hard-reject; `isMedicine=false` corta fuzzy.

Suite scraper: **354+ passed** (Grok mid-loop). Claude puede haber subido más
tests después — corré `pytest` antes de confiar en un número.

## Relink — política

```text
python -m src.cli relink --dry-run --only-medicine --limit 300
python -m src.cli relink --dry-run --chain ahumada --only-medicine --limit 200
```

Flags nuevos: **`--only-medicine`**, **`--chain <name>`**.

Dry-runs post-fix:
- only-med 400 → **0 LINK**
- post-% fix 300 → **1 LINK** (Olmepress FP) → fix bare combo → match None
- farmaloop only-med 200 (attrs ya llenos) → **0 LINK** / 10 GREY

**NO `relink` write a ciegas.** Solo write chico tras revisar cada línea `LINK`
(misma molécula, dosis/combo, pack/vol). Greys de conf 1.00 sin `q_med` o pack
incompleto son esperables.

## Farmaloop attrs (hecho en código + re-scrape)

`farmaloop_connector.extract_attributes`: `productCategory` → `isMedicine`,
PA (`composicionSearch`), bioeq, rx, presentation. Prod attrs ya **4860/4860**.

## Qué NO hacer

- No re-probe VTEX/OCAPI/Algolia “from scratch” (ya mapeado).
- No inventar precios ni auto-link grey zone.
- No secretos en vault/git (keys, `DATABASE_URL` password, Places keyString).
- No deploy desde `apps/web/.vercel`.
- No `scrape-all` agresivo; ≤2 writers; preferí 1 si CV sigue.
- No re-scrape farmex full “por las dudas” (casi 100% imgs, pesado).
- No colisionar con scrapes locales vivos (`Get-CimInstance` python + `scrape`).

## Fronteras de archivos (sugeridas)

| Área | Dueño sugerido | Paths |
|------|----------------|-------|
| Matcher / identity / relink CLI | Grok hizo el lote; Claude puede endurecer | `product_identity.py`, `matcher.py`, `cli.py` relink, tests |
| Connectors / registry | compartido — releer antes de editar | `connectors/*`, `registry.py` |
| Web UI / Vercel / PriceTable thumbs | Claude natural | `apps/web/**` |
| API gateway / Cloud Run deploy | Claude natural | `services/api-gateway/**` |
| Places Coquimbo | estable; no re-import masivo sin need | `places_*.py`, `docs/places-coquimbo.md` |
| Infra gcloud docs | Claude | `docs/infra-gcloud.md`, cloudbuild |

`docs/coordinacion-agentes.md` puede estar un turno atrasado: **actualizarlo** al
tomar ownership.

## Próximos pasos de valor (orden)

1. **Confirmar CV:** si proceso vivo, dejarlo; si zombie job en `scraping_jobs`,
   `cleanup-jobs` / reap. Snapshot hasta imgs CV ~100%.
2. **Web:** verificar thumbs en `/precios` con salcobrand/ahumada (ProductThumb
   ya es `<img>` plain; API expone `imageUrl`).
3. **Relink cauteloso (opcional):** dry-run `--only-medicine --chain farmaloop|ahumada`
   post-CV; si aparecen LINKs limpios, write `--limit 100` y re-auditar.
4. **No prioritario:** Preunic/Knop linked=0 es esperado (beauty / homeopático).
5. **Coquimbo product UX:** mapa/listado ya con 132; no expandir nacional aún.
6. Cerrar con digest vault `work/sessions/2026-08-02-claude.md` (Goal/Done/…).

## Comandos útiles

```powershell
cd "D:\Respaldo Proyectos\GitHub\02-products\FarmaciaCompare\workers\scraper"
$env:PYTHONIOENCODING = "utf-8"
# DATABASE_URL desde ..\..\ .env.production (no echo)
.venv\Scripts\python.exe scripts\prod_snapshot.py
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m src.cli relink --dry-run --only-medicine --limit 200
.venv\Scripts\python.exe -m src.cli list-chains
```

Procesos scrape:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'scrape' } |
  Select-Object ProcessId, CommandLine
```

## Lectura obligatoria (barata)

1. `bitacora.md` (arriba)
2. `docs/coordinacion-agentes.md`
3. `docs/architecture-ingestion.md` (fail-closed, change-only prices)
4. `D:\obsidian-mind\work\sessions\2026-08-02-grok.md`
5. Este archivo

## Mensaje de arranque (si Claude pregunta “qué hago”)

> CV scrape local puede seguir. Snapshot + no matar writers. Matcher/relink flags
> y scrapes ahumada/salcobrand/farmaloop ya hechos por Grok. Prioridad: UI
> imágenes en prod web, CV al 100%, relink write **solo** tras dry-run LINK limpio.
> Fail-closed. Coquimbo first. Sin secretos en vault.

---

Fin del prompt de traspaso.
)
