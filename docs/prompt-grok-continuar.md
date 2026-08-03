# Prompt de traspaso a Grok

Copiar todo lo que está bajo la línea. Escrito 2026-08-01, refrescado tras session
limit de Claude + takeover Grok (noche). Reemplazar los números de estado si pasó tiempo.

---

Vas a continuar **FarmaciaCompare**, un comparador de precios de medicamentos en
Chile que ya está en producción. Trabajás con subagentes en paralelo, igual que
la sesión anterior. Este prompt tiene todo lo que necesitás; leelo entero antes
de tocar nada.

## Qué es el producto y por qué importa

Una persona busca "paracetamol" y ve lo que cobra cada farmacia online chilena,
para comprar donde sea más barato. Los datos reales de hoy:

- El mismo Ozempic 4mg/3mL: **$209.990** en una cadena, **$413.800** en otra.
- El mismo Algiafin paracetamol: **$2.502** vs **$3.680**.

Para alguien que paga de su bolsillo un tratamiento crónico, esa diferencia es
el mercado del mes. Todo lo que hagas se juzga contra eso.

**La regla que no se rompe:** ningún precio inventado llega a producción. Un
precio falso, o un producto emparejado con el equivocado, es peor que no mostrar
nada — le hace tomar una decisión de plata y de salud sobre información falsa.

**Foco geográfico actual:** Región de Coquimbo (directorio físico de farmacias
vía Google Places + web Coquimbo-first). Precios online siguen siendo nacionales
(cadenas e-commerce); el mapa/listado físico arranca por Coquimbo.

## Estado actual

**En producción:**
- Web: https://farmacia-compare-web.vercel.app (Vercel, proyecto `farmacia-compare-web`)
- Directorio farmacias (Coquimbo-first): https://farmacia-compare-web.vercel.app/farmacias
- API: https://api-gateway-446315435132.southamerica-west1.run.app (Cloud Run)
- Farmacias físicas Coquimbo live:
  `GET …/api/v1/products/pharmacies?region=Coquimbo` → **174 en la tabla**

**Deploy 2026-08-02 (Claude, post-reset):** gateway + web redeployados con
imágenes de producto (`image_url`) y las 10 cadenas. Ver "Datos en Cloud SQL"
abajo para los números medidos.

**Handoff 2026-08-02 (Grok loop ultrathink — post Claude limit):**
- Registry: **10 cadenas online** con productos en prod (incl. preunic 8880).
- Matcher fail-closed **endurecido 2026-08-02**:
  - Combo inhaler `250/25 mcg`; pack `dosis`/`ds`.
  - Coma decimal chilena `0,5` → `0.5` (antes colapsaba a `5`).
  - Dosis `%` con `(?!\w)` (antes `\b` perdía **todas** las % ).
  - Combo oftálmico `0,005%/0,5%`; tableta bare `20/12,5` → `20/12.5mg`.
- Suite scraper: **354 passed**.
- **relink**: flags `--only-medicine` + `--chain`. Dry-runs post-fix:
  only-med 400 → 0 LINK; post-% 300 → 1 LINK (Olmepress FP) → fix bare combo.
  **Sin write relink** todavía.
- **Imágenes prod (aprox):** farmex ~22242/22272; ahumada **5406/5406**;
  preunic 8880/8880; knop/curie/simi/MF altos; **salcobrand re-scrape en curso**
  (iba 0 → subiendo); CV mid-scrape. Farmaloop imgs sí, attrs 0 hasta re-scrape
  (connector ya emite `isMedicine` desde `productCategory`).
- db-f1-micro: **≤2 scrapes writers** concurrentes.
- **`relink` write full sigue prohibido** sin dry-run LINK limpio.

**Directorio físico Coquimbo (HECHO como directorio):**
- Google Places (New) vía proyecto gcloud **`tablero-iner-maps`**, API key server
  **"Tablero INER server"**. **Nunca imprimir la key** ni meterla en git/vault/
  frontend. Cómo cargarla y corridas: `docs/places-coquimbo.md`.
- CLI: `python -m src.cli discover-places` → JSON; `import-places` → Cloud SQL
  (`type=physical`, `rut=gp:<place_id>`, `region=Coquimbo`).
- ~132 farmacias físicas activas en prod (filtro anti-ruido sobre import bruto).
- Web `/farmacias` prioriza Coquimbo. API `?region=Coquimbo` live.

**Datos en Cloud SQL — medidos 2026-08-02, las 10 cadenas con productos:**

| Cadena | Productos | Con imagen | Vinculados |
|---|---|---|---|
| Farmex | 22.276 | 22.242 | 16.878 |
| Salcobrand | 12.795 | 12.741 | 2.742 |
| Cruz Verde | 9.395 | 8.500 | 1.208 |
| Preunic | 8.880 | 8.880 | 0 |
| Ahumada | 5.406 | 5.406 | 1.090 |
| MercadoFarma | 4.970 | 4.784 | 776 |
| Farmaloop | 4.860 | 4.786 | 3.205 |
| Curie | 4.604 | 4.598 | 2.895 |
| Knop | 1.651 | 1.651 | 0 |
| Dr. Simi | 1.294 | 1.294 | 571 |
| **TOTAL** | **76.131** | **74.882 (98,4%)** | **29.365** |

Farmacias físicas: **174** (Coquimbo vía Places).

Catálogo de medicamentos: 34.166, con 34.052 códigos de barras. Los vínculos son
por **EAN exacto** más lo que escribió el writer durante los scrapes; `relink`
full sigue sin correrse. Preunic y Knop en 0 vinculados: Preunic es beauty y Knop
no cruza EAN con el catálogo.

Suite scraper: **379 passed** (`--ignore=tests/test_dr_simi.py`).

**Documentación que tenés que leer primero:**
- `docs/infra-gcloud.md` — coordenadas GCP, runbook, trampas de build resueltas
- `docs/places-coquimbo.md` — Places, key Tablero INER server, discover/import
- `docs/coordinacion-agentes.md` — reparto de archivos y evidencia histórica de
  matching (defectos a/b **ya cerrados en código**)
- `bitacora.md` — historia de la sesión + takeover Grok
- `docs/prompt-grok-scraping.md` — el reconocimiento de plataformas de cada sitio

## Infraestructura

| Recurso | Valor |
|---|---|
| Proyecto GCP (prod) | `farmacia-compare-prod` |
| Places (key server) | `tablero-iner-maps` · key display name **Tablero INER server** (ver `docs/places-coquimbo.md`; no imprimir) |
| Región | `southamerica-west1` (Santiago) |
| Cloud SQL | `farmacia-compare-db`, POSTGRES_15, `db-f1-micro`, base `farmaciacompare` |
| Connection name | `farmacia-compare-prod:southamerica-west1:farmacia-compare-db` |
| Red autorizada | solo la IP del capitán — `--authorized-networks` **reemplaza** la lista, no agrega |
| Artifact Registry | repo `farmacia` |
| Cloud Run service | `api-gateway` |
| Cloud Run job | `scraper` + triggers de Cloud Scheduler (en `southamerica-east1`: Scheduler no existe en west1) |
| Web (Vercel) | `farmacia-compare-web` · deploy desde monorepo root (no `apps/web`) |

Credenciales en `.env.production` (gitignored). Nunca imprimirlas ni commitearlas.
`.env` apunta al Postgres local de desarrollo; no se pisan.
`GOOGLE_MAPS_API_KEY` se obtiene con gcloud al vuelo (Places); no commitear.

Deploys, ambos idempotentes:
```bash
./scripts/deploy-api-gateway.sh [TAG]
./scripts/deploy-scraper-job.sh [TAG]
```

Correr scrapers / matcher / Places contra producción:
```bash
cd workers/scraper
export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production | cut -d= -f2-)
export PYTHONIOENCODING=utf-8      # sin esto, imprimir '→' revienta en consola Windows
python -m src.cli scrape <cadena>
python -m src.cli relink --dry-run --limit 80   # o 500; NUNCA sin --dry-run aún
# Places (key vía gcloud — ver docs/places-coquimbo.md):
python -m src.cli discover-places --region coquimbo --out data/coquimbo-places.json
python -m src.cli import-places --from-json data/coquimbo-places.json [--dry-run]
```

## Los problemas abiertos, en orden de valor

### 1. Coquimbo directorio — HECHO; no reabrir salvo huecos

Directorio físico Coquimbo ya está en prod (~132 activas), API `?region=Coquimbo`
y web `/farmacias` Coquimbo-first. CLI `discover-places` / `import-places` y
docs en `docs/places-coquimbo.md`. No re-correr Places en loop (costo Text
Search + Details). Solo ampliar si el capitán pide más ciudades/regiones.

### 2. Re-scrape de atributos + `image_url` (siguiente valor)

Salcobrand y Cruz Verde casi sin vincular por nombre: no publican EAN. Su
identidad son `attributes` estructurados (ya se guardan en writer):
- Cruz Verde: `c_activeIngredient`, `c_dose`, `c_format`, `c_isMedProduct`,
  `c_bioequivalentSubCategoryID`.
- Salcobrand: breadcrumb `product_categories.lvl3` + `options_text`.

Falta re-scrapear **Farmex, Cruz Verde y Farmaloop** (y el resto cuando haya
hueco) para poblar attrs **y** `image_url` (columna existe, **0 filled**). Una
cadena a la vez en f1-micro (≤2 escritores).

### 3. Matcher fail-closed HECHO — falta validar muestra y recién ahí relink

Defectos a (FP cosmética / "polvo") y b (pack size / dose) **ya están en código**
(`workers/scraper/src/matching/matcher.py`, `identity.py` + tests). Evidencia
histórica de los FPs sigue en `docs/coordinacion-agentes.md`.

**Dry-run muestra 80:** linked=4 · grey=17 · none=59. **Aún no corras `relink`
write.** Los ~20.6k vínculos actuales son por barcode. Orden:

1. Más dry-run si hace falta (`--limit 500`) + revisión a ojo (no-medicamento,
   envases, dose)
2. Solo si la muestra está limpia → relink real, carga baja en f1-micro

### 4. Cadenas nuevas wired, sin datos en prod

`mercadofarma`, `knop`, `preunic` están en `registry.py` (10 cadenas). No hay
scrape prod de las tres todavía. Cuando haya hueco de escritores: `sync-pharmacies`
+ scrape una cadena a la vez. Preunic es beauty/drugstore (`isMedicine=false`);
no esperes que alimente el matcher médico.

### 5. CI + higiene de prod

- Sin CI: tests y builds solo cuando alguien se acuerda → hay que cablear.
- `DATABASE_URL` en texto plano como env var en Cloud Run (service y job);
  debería estar en Secret Manager.
- Filas huérfanas en `scraping_jobs` con `status='running'` de corridas
  interrumpidas.
- Retención de `prices`: crece sin política (7–10 cadenas × decenas de miles ×
  corridas). f1-micro: ≤2 escritores concurrentes.
- `workers/ingestion/tests/test_db_writer.py` y `test_isp_importer.py` no
  colectan por falta de `pandas` — no protegen nada.

## Trampas ya pagadas — no las vuelvas a descubrir

**Scraping:**
- Cruz Verde, Salcobrand y Ahumada **ya no son VTEX**; sus hosts
  `<cuenta>.vtexcommercestable.com.br` dan 404. Solo Dr. Simi sigue en VTEX.
- `robots.txt` de Cruz Verde y Ahumada prohíbe **cualquier URL con `start`**, lo
  que mata paginar `product_search` y `Search-UpdateGrid`. Usá sus sitemaps.
- Algolia solo deja alcanzar **1000 hits por query** y su key está restringida
  por **Referer**. Salcobrand se recorre particionado por faceta.
- El `buildId` de Next.js rota en cada deploy: leerlo del HTML.
- **Dos parsers de precio.** `parse_price` lee "." como separador de miles
  ("$12.990" → 12990); `parse_machine_price` lo lee como decimal ("1000.0" →
  1000). Confundirlos infla precios ×10 en silencio.
- Un precio `$0` no es oferta: Farmex publica placeholders Cenabast.
- Ahumada tardaba 95 min en serie y la sesión de DB se caía esperando el primer
  lote de 500 — por eso nunca escribió. Con concurrencia acotada (4 workers,
  chunks de 100) baja a ~10 min. Mismo patrón en `farmaloop_connector.py`.
- MercadoFarma: `product_type` "medicamento" / "sin medicamento" (el negativo
  contiene el positivo); SKUs internos, no EAN. Knop: Bolder, no Shopify;
  catálogo en farmaciasknop.com (knop.cl es lab). Preunic: Empathy.co, no Algolia.

**Places / Coquimbo:**
- Key de Places vive en **`tablero-iner-maps`**, no en `farmacia-compare-prod`.
  Nunca la pegues en chat, vault ni frontend. Ver `docs/places-coquimbo.md`.
- `rut=gp:<place_id>` no es RUT chileno; es id estable de Google.
- Import bruto trae ruido (ortopedia, vet, perfumería): soft `is_active=false`.

**Build y deploy:**
- `gcloud builds submit` **ignora `.dockerignore`** y usa `.gcloudignore`.
- `pnpm install --frozen-lockfile` exige el `package.json` de **todos** los
  importers del lockfile, aunque la imagen no los use.
- Un paquete sin dependencias no tiene `node_modules`: COPYarlo revienta.
- pnpm resuelve por symlinks propios de cada paquete: el runner necesita
  `services/<svc>/node_modules`, y el bundle tiene que correr desde su ruta
  dentro del workspace o `require()` falla.
- Los paquetes del workspace hay que compilarlos antes del servicio, o `nest
  build` muere con `TS2307`.
- Prisma en `node:20-alpine` necesita
  `binaryTargets = ["native","linux-musl-openssl-3.0.x"]` + `apk add openssl`.
- Cloud Run exige escuchar en `process.env.PORT` con bind `0.0.0.0`.
- Cloud Scheduler con `containerOverrides` necesita
  `roles/run.jobsExecutorWithOverrides`, no alcanza `run.invoker`. Con invoker
  solo falla en silencio (`status.code: 7`, sin ejecución visible).
- Deploy web: desde **raíz del monorepo** (`.vercel` → `farmacia-compare-web`).
  No desde `apps/web` (apunta a otro proyecto).

**Entorno Windows:**
- `/tmp` de Git Bash y `/tmp` del Python de Windows son lugares distintos. Un
  script escrito en `/tmp` desde bash puede no existir para Python. Usar rutas
  absolutas del scratchpad.
- `tail` bufferea: un proceso en background con `| tail -N` no muestra nada hasta
  terminar. Verificá contra la base, no contra el log.
- Sin `PYTHONIOENCODING=utf-8`, imprimir `→` lanza `UnicodeEncodeError` en cp1252.

**SQL:**
- Con SQLAlchemy `text()`, un `CAST(:param AS jsonb)` en el SQL sin la clave en el
  dict de parámetros lanza `InvalidRequestError: A value is required for bind
  parameter`. Eso rompió **todas** las escrituras de producto durante horas: el
  scraper reportaba miles de productos y escribía cero.
- Prisma `@updatedAt` es a nivel aplicación, no default de base: un INSERT crudo
  tiene que setear `created_at`/`updated_at` o viola NOT NULL.

## Cómo usar subagentes — lo que funcionó y lo que no

**Fronteras de archivos estrictas, siempre.** El error que hay que evitar es dos
agentes editando el mismo archivo. Lo que funcionó:
- Cada agente es dueño de archivos explícitos y tiene una lista de prohibidos.
- **`registry.py` es single-owner** (hoy Grok). Si un agente agrega una cadena,
  reporta la línea `ChainSpec(...)` exacta; no la wirea solo. Tres agentes
  colisionarían ahí.
- Los agentes de tests solo escriben en `tests/`, nunca en fuente. Si encuentran
  un bug, lo reportan; no lo arreglan.
- Un agente de UI y uno de datos pueden chocar en las mismas páginas: repartí
  por página, no por "el frontend".
- Mientras Claude esté en session limit, `apps/web/**` queda libre si hace falta.

**Exigí evidencia, no afirmaciones.** "Definition of done: mostrame el conteo
antes y después, la fila de `scraping_jobs` con `status='success'`, el `curl -I`
devolviendo 200". Sin eso los agentes reportan éxito sobre un build que compila
pero no corre.

**Decíles que lean el archivo justo antes de editarlo.** Con varios agentes y vos
trabajando a la vez, la copia en memoria queda vieja en minutos.

**Los agentes se mueren por límite de sesión** a mitad de trabajo, dejando
archivos a medio escribir. Cuando uno falle, revisá qué alcanzó a dejar antes de
relanzar: en esta sesión uno dejó el conector de Ahumada completo y funcionando
justo antes de morir, y otro dejó tests que documentaban tres bugs reales.
Claude main + UI/Preunic/images murieron en el session limit del 2026-08-01
(reset ~3:20am America/Santiago); Preunic e image_url quedaron mayormente en
disco y Grok los cerró / wireó.

**Un agente de tests bien escrito encuentra bugs que vos no ves.** El de esta
sesión encontró que yo calculaba `attributes` en el conector Shopify y nunca lo
pasaba al constructor: 22.000 productos llegaban con el campo en NULL.

## Reglas de trabajo

1. **Verificá antes de decir que algo funciona.** Corré el comando, mostrá la
   salida. Un build que compila no es un servicio que arranca.
2. **Nunca corras `scripts/seed.mjs` contra producción.** Genera precios
   inventados con 30 días de historial falso, indistinguibles de los reales en la
   tabla que lee el sitio.
3. **Respetá `robots.txt`.** Si un sitio no se puede scrapear sin violarlo,
   pará y decilo, no lo rodees.
4. **Sin secretos** en git ni en el vault (`D:\obsidian-mind`). Incluye la key
   de Places: solo puntero (`docs/places-coquimbo.md`), nunca el valor.
5. **Documentá** en `bitacora.md` y en el vault (`work/sessions/`,
   `brain/Gotchas.md`). Es la Regla 0 del proyecto.
6. Tests: `cd workers/scraper && .venv/Scripts/python.exe -m pytest tests -q
   --ignore=tests/test_dr_simi.py` (319 pasan hoy; `test_dr_simi` pide playwright).

## Por dónde empezar

Mi orden sería:

1. **Re-scrape attrs + `image_url`** (Farmex / Cruz Verde / Farmaloop), una
   cadena a la vez en f1-micro. Coquimbo directorio ya está.
2. **Más dry-run `relink` + revisión de muestra** (dry-run 80: 4/17/59). Solo si
   la muestra está limpia → relink real con carga baja. **Sin write todavía.**
3. **Scrape de knop / mercadofarma / preunic** cuando haya hueco de escritores.
4. **CI** + Secret Manager + limpieza `scraping_jobs` + retención de `prices`.

Antes de arrancar, contame qué vas a hacer y con qué agentes, para que no
choquemos. Ver `docs/coordinacion-agentes.md` por ownership actual.
