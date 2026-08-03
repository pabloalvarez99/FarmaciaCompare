# Catálogo de medicamentos — datos abiertos del gobierno (gratis)

No hay API de pago. El catálogo canónico se llena desde **datos.gob.cl** (ISP).

## Fuentes

| key | Dataset | Contenido útil |
|-----|---------|----------------|
| `bioequiv` | Equivalentes terapéuticos | Principio activo, producto, registro F-…, lab |
| `venta_directa` | Venta directa / OTC | Registro, nombre, titular (dosis desde el título) |
| `proteccion_datos` | Protección de datos | Registro, producto, titular |

Precios de góndola de las cadenas **no** vienen del Estado: siguen en `workers/scraper`.

## Comandos

```powershell
cd workers\ingestion
poetry run ingest list-sources
poetry run ingest fetch-official          # cache en data/official/ (TTL 7 días)
poetry run ingest import-official --also-sample
poetry run ingest lookup "metformina 850"

cd ..\scraper
poetry run scraper relink                 # re-enlaza pharmacy_products sin medication_id
```

## Notas

- Cache local: `workers/ingestion/data/official/` (gitignored).
- Re-fetch: `fetch-official --force`.
- El portal de consulta [registrosanitario.ispch.gob.cl](https://registrosanitario.ispch.gob.cl/) es gratis pero web; estos CSV son el dump bulk usable.
- Dumps de datos.gob.cl a veces son antiguos: cuando ISP publique un dump más fresco, basta cambiar la URL en `official_sources.py`.
