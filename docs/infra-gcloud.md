# Infraestructura GCP — FarmaciaCompare

## En producción

| Pieza | URL |
|---|---|
| Web (Vercel) | https://farmacia-compare-web.vercel.app — precios reales en `/precios` |
| API (Cloud Run) | https://api-gateway-446315435132.southamerica-west1.run.app |

Endpoints que sirven datos scrapeados hoy:

- `GET /api/v1/products/search?q=&page=&limit=` — busca sobre
  `pharmacy_products.raw_name` con el último precio. Excluye `source='quarantine'`.
- `GET /api/v1/products/coverage` — productos por cadena; sirve para detectar un
  scraper muerto.

`GET /api/v1/medications/search` responde vacío a propósito: consulta el catálogo
curado `medications`, que sigue sin poblarse.


Coordenadas de producción y runbook. **Sin credenciales**: las contraseñas viven
en `.env.production` (gitignored) y nunca se commitean.

Última actualización: 2026-08-01.

## Proyecto

| Recurso | Valor |
|---|---|
| Proyecto GCP | `farmacia-compare-prod` (número `446315435132`) |
| Cuenta | `timadapa@gmail.com` |
| Billing | `01CFAA-B6DE2D-50B576` (Firebase Payment) |
| Región | `southamerica-west1` (Santiago) |

Se creó un proyecto nuevo a propósito. **No usar `tu-farmacia-prod`**: ahí corre
`tu-farmacia-db`, que sirve el sitio vivo `tu-farmacia.cl`.

## Cloud SQL

| Campo | Valor |
|---|---|
| Instancia | `farmacia-compare-db` |
| Versión | POSTGRES_15 |
| Tier | `db-f1-micro`, 10 GB con auto-crecimiento |
| IP pública | `34.176.88.36` |
| Base | `farmaciacompare` |
| Usuario app | `farmacia_app` |
| Connection name | `farmacia-compare-prod:southamerica-west1:farmacia-compare-db` |

**Red autorizada**: solo la IP del capitán (`190.96.45.87/32`). Para correr los
scrapers desde otra máquina hay que agregar esa IP:

```bash
gcloud sql instances patch farmacia-compare-db \
  --project=farmacia-compare-prod \
  --authorized-networks=190.96.45.87/32,<NUEVA_IP>/32
```

`--authorized-networks` **reemplaza** la lista completa, no agrega: hay que
repetir las IPs que ya estaban o se corta el acceso de los demás.

Cloud Run no pasa por la IP pública — usa el socket
`/cloudsql/<connection name>` vía `--add-cloudsql-instances`.

## Artifact Registry

Repo `farmacia` en `southamerica-west1`. Imagen del gateway:

```
southamerica-west1-docker.pkg.dev/farmacia-compare-prod/farmacia/api-gateway:latest
```

## Build y deploy del API gateway

```bash
# desde la raíz del repo
gcloud builds submit --config=cloudbuild.yaml \
  --project=farmacia-compare-prod --region=southamerica-west1 \
  --substitutions=SHORT_SHA=$(git rev-parse --short HEAD)
```

`cloudbuild.yaml` construye con `-f services/api-gateway/Dockerfile` y contexto
en la raíz, porque el Dockerfile necesita todo el workspace pnpm.

## Trampas ya resueltas (no repetir)

1. **`gcloud builds submit` ignora `.dockerignore`** y usa `.gcloudignore`. Sin
   ese archivo sube el repo completo, incluidos `node_modules` y
   `services/price-service/target`. El `.gcloudignore` está commiteado.
2. **`--frozen-lockfile` exige todos los importers**. `pnpm-lock.yaml` lista
   `apps/web`, `apps/admin` y `apps/dashboard`; el stage `deps` del Dockerfile
   copia sus `package.json` aunque el gateway no los use.
3. **`packages/config` no tiene `node_modules`** — solo trae tsconfigs, sin
   dependencias. Un `COPY` de su `node_modules` rompe el build.
4. **El runner necesita `services/api-gateway/node_modules`**. pnpm resuelve por
   symlinks propios de cada paquete; sin eso, todo `require()` falla en runtime.
5. **`main.ts` escucha en `process.env.PORT` y bindea `0.0.0.0`**, que es lo que
   Cloud Run exige. `CORS_ORIGINS` (lista separada por comas) agrega los dominios
   de Vercel, que no se pueden hardcodear.
6. **`pnpm-lock.yaml` tenía dos documentos YAML concatenados** — un fragmento de
   `pnpm self-install` pegado arriba — y rompía todo `pnpm install` con
   `ERR_PNPM_BROKEN_LOCKFILE`. Ya está corregido.

## Correr los scrapers contra producción

```bash
cd workers/scraper
export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production | cut -d= -f2-)
python -m src.cli sync-pharmacies     # una vez por base nueva
python -m src.cli scrape farmex       # una cadena
python -m src.cli scrape-all          # todas, secuencial
```

`.env` apunta al Postgres **local** (Docker, puerto 5432) y `.env.production` a
Cloud SQL. No se pisan: el scraper toma `DATABASE_URL` del entorno.

## Reglas de datos

- **Nunca correr `scripts/seed.mjs` contra Cloud SQL.** Genera precios
  inventados con 30 días de historial falso; contaminaría la tabla que lee el
  sitio público.
- Los precios en `prices` deben venir siempre de un scrape real.
- Vigilar el disco: 7 cadenas × decenas de miles de productos × varias corridas
  diarias hacen crecer `prices` rápido. Va a necesitar política de retención.

## Costo

La instancia `db-f1-micro` corre del orden de USD 10-15/mes. Se puede apagar
entre corridas con `gcloud sql instances patch --activation-policy=NEVER`.

## Scrapers automáticos — Cloud Run Job + Cloud Scheduler

Los scrapers ya no se lanzan a mano. Corren como un **Cloud Run Job** llamado
`scraper`, disparado por **Cloud Scheduler**.

| Pieza | Valor |
|---|---|
| Imagen | `southamerica-west1-docker.pkg.dev/farmacia-compare-prod/farmacia/scraper:latest` |
| Dockerfile | `workers/scraper/Dockerfile` (contexto = raíz del repo) |
| Build config | `cloudbuild-scraper.yaml` |
| Cloud Run Job | `scraper` en `southamerica-west1` |
| Recursos | 1 vCPU, 2 GiB, `--task-timeout=7200s`, `--max-retries=1`, 1 tarea |
| Cloud SQL | `--set-cloudsql-instances` + `DATABASE_URL` con socket `/cloudsql/...` |
| Service account de los triggers | `scraper-scheduler@farmacia-compare-prod.iam.gserviceaccount.com` |
| Schedulers | 9 jobs en `southamerica-east1`, zona horaria `America/Santiago` |

### Deploy completo (una sola orden)

```bash
./scripts/deploy-scraper-job.sh [TAG]     # TAG por defecto: git rev-parse --short HEAD
```

Es idempotente: habilita APIs, construye la imagen, redeploya el job, crea la
service account si falta y crea/actualiza los 9 schedulers.

### Cómo está armado

Hay **un solo** Cloud Run Job. Cada trigger de Cloud Scheduler hace un POST a la
API de Cloud Run v2 pisando los argumentos del contenedor:

```
POST https://run.googleapis.com/v2/projects/farmacia-compare-prod/locations/southamerica-west1/jobs/scraper:run
{"overrides":{"containerOverrides":[{"args":["scrape","farmex"]}]}}
```

El `ENTRYPOINT` de la imagen es `python -m src.cli`, así que los args son
directamente el subcomando del CLI.

### Calendario

Cadencia tomada de `interval_hours` en `workers/scraper/src/registry.py`
(6h → 4 corridas/día, 12h → 2/día), escalonada para no golpear la instancia
`db-f1-micro` con dos cadenas a la vez.

| Scheduler | Cron (America/Santiago) | Args |
|---|---|---|
| `scraper-sync-pharmacies` | `0 4 * * *` | `sync-pharmacies` |
| `scraper-farmex` | `20 1,7,13,19 * * *` | `scrape farmex` |
| `scraper-salcobrand` | `0 2,8,14,20 * * *` | `scrape salcobrand` |
| `scraper-curie` | `40 2,8,14,20 * * *` | `scrape curie` |
| `scraper-farmaloop` | `10 3,9,15,21 * * *` | `scrape farmaloop` |
| `scraper-dr-simi` | `40 3,9,15,21 * * *` | `scrape dr_simi` |
| `scraper-cruz-verde-full` | `10 5,17 * * *` | `scrape cruz_verde` |
| `scraper-cruz-verde-fast` | `10 11,23 * * *` | `scrape cruz_verde --fast` |
| `scraper-ahumada` | `40 5,17 * * *` | `scrape ahumada` |

### Disparar a mano

```bash
# una cadena
gcloud run jobs execute scraper --project=farmacia-compare-prod \
  --region=southamerica-west1 --args=scrape,farmex --wait

# todas, secuencial (lo que corre por defecto si no se pasan args)
gcloud run jobs execute scraper --project=farmacia-compare-prod \
  --region=southamerica-west1 --wait

# forzar un scheduler (usa sus propios args)
gcloud scheduler jobs run scraper-farmex \
  --project=farmacia-compare-prod --location=southamerica-east1

# pausar / reanudar un scheduler
gcloud scheduler jobs pause scraper-farmex --location=southamerica-east1 \
  --project=farmacia-compare-prod
```

### Ver qué pasó

```bash
gcloud run jobs executions list --job=scraper \
  --project=farmacia-compare-prod --region=southamerica-west1

gcloud logging read \
  'resource.type="cloud_run_job" AND labels."run.googleapis.com/execution_name"="<EXEC>"' \
  --project=farmacia-compare-prod --limit=50 --format='value(textPayload)'
```

También queda registro en la tabla `scraping_jobs` (una fila por corrida, con
`status`, `items_scraped`, `items_updated` y `errors`).

### Trampas nuevas (no repetir)

7. **Cloud Scheduler no existe en `southamerica-west1`.** La location más
   cercana es `southamerica-east1` (São Paulo); los triggers viven ahí y llaman
   por HTTPS al job de Santiago. Verificar con
   `gcloud scheduler locations list`.
8. **`roles/run.invoker` no alcanza para los triggers.** Mandar
   `containerOverrides` exige el permiso `run.jobs.runWithOverrides`, que está
   en `roles/run.jobsExecutorWithOverrides`. Con solo `run.invoker` el intento
   falla con `status.code: 7` (PERMISSION_DENIED) y **no** aparece ninguna
   ejecución en Cloud Run — hay que mirar
   `gcloud scheduler jobs describe <job>`.
9. **La imagen del scraper no instala navegadores.** `playwright install` sumaba
   ~700 MB para código muerto: el único scraper con browser es el legacy
   `src/pharmacies/dr_simi.py`, que `registry.py` no usa (dr_simi entra por el
   conector VTEX HTTP). El paquete `playwright` sigue en `pyproject.toml`, solo
   no se bajan los binarios.
10. **`poetry.lock` es lock-version 2.1 (Poetry 2.4.1).** La imagen fija
    `poetry==2.4.1`; cualquier Poetry <2.1 no puede leer el lockfile.
11. **El `CMD` viejo del Dockerfile no hacía nada.** Apuntaba a
    `python -m src.scheduler`, y `scheduler.py` no tiene bloque
    `if __name__ == "__main__"`: el contenedor arrancaba, importaba el módulo y
    salía con 0 sin scrapear. Ahora el entrypoint es `python -m src.cli`.
12. **SQLAlchemy + asyncpg y el socket de Cloud SQL**: el connection name lleva
    dos puntos (`proyecto:region:instancia`), pero el parser de multihost de
    SQLAlchemy no se confunde porque la ruta empieza con `/`. La URL correcta es
    `postgresql://USER:PASS@localhost/farmaciacompare?host=/cloudsql/<conn>`
    (el `?host=` pisa al `localhost`).
