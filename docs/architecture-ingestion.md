# Arquitectura de ingesta de precios — FarmaciaCompare

Estado: producción local (2026-08-01). Reconocimiento de plataformas **cerrado**; este doc cubre la capa que rodea a los conectores.

## 1. Flujo

```
registry.CHAINS
    → build_scraper(chain)
    → scrape_products()  AsyncIterator[ScrapedProduct]
    → health gate (mínimo de productos / tasa de error)
    → PriceWriter (match + anomaly + change-only)
    → pharmacy_products + prices + scraping_jobs
```

| Cadena | Plataforma | Recorrido | Intervalo |
|---|---|---|---|
| Cruz Verde | SFCC OCAPI | sitemap productos → `/products/{id}` | 12 h |
| Salcobrand | Algolia | faceta `taxonomies` + split por letra si >1000 | 6 h |
| Ahumada | SFCC JSON-LD | sitemap → ficha HTML | 12 h |
| Dr. Simi | VTEX | `catalog_system` paginado | 6 h |
| Farmex / Curie | Shopify | `/products.json` | 6 h |
| Farmaloop | Next.js data | sitemap + `_next/data/{buildId}/…` | 6 h |

**Por qué sitemap y no `start=` en SFCC:** `robots.txt` de Cruz Verde y Ahumada prohíbe URLs con `start`. Paginar `product_search` / `Search-UpdateGrid` viola robots; el sitemap es la vía permitida.

## 2. Detección de scraper roto (fail-closed)

Un scraper que devuelve 0 productos **no** debe:

- marcar catálogo como vacío,
- insertar filas basura,
- silenciar el fallo.

Cada run escribe `scraping_jobs` con `status ∈ {running, success, failed, empty}`.

Reglas:

1. **Vacío duro:** `items_scraped == 0` → `empty` / `failed`. No se toca `is_active` de productos previos.
2. **Umbral mínimo** por cadena (aprox. catálogo online chileno). Si `items_scraped < min_expected * 0.3` → `failed` + alerta. Probable: 404 de plataforma, key Algolia, `buildId` roto, bloqueo.
3. **Tasa de error de escritura:** si `errors / (written+errors) > 0.25` y `written > 0` → `failed` parcial.
4. **Heartbeat de precio:** si una cadena con historial no produce *ningún* cambio de precio en 3 runs consecutivos y el yield es normal, se registra warning (posible cache pegado), no se apaga la cadena.

La UI / API solo muestra precios cuyo último job de la cadena fue `success` en las últimas 36 h (flag de frescura; implementar en gateway cuando se exponga).

## 3. Identidad de producto (el problema difícil)

**Regla de oro:** un match falso es peor que no match. Precio barato de otro SKU destruye confianza.

### Señales (orden de confianza)

| Rango | Señal | Acción |
|---|---|---|
| 1.00 | EAN/barcode exacto (8–14 dígitos) → `pharmacy_products.barcode` o catálogo ISP | Auto-link |
| 0.95–0.99 | Misma clave estructurada: dosis + forma + pack + token de marca/principio | Auto-link |
| 0.85–0.94 | Fuzzy nombre **y** dosis idéntica **y** forma compatible | Auto-link solo ≥ 0.90 |
| 0.75–0.84 | Fuzzy sin acuerdo de pack, o forma ambigua | **Cola gris** — no link automático |
| < 0.75 | — | Sin match |

### Normalización

- `unidecode` + lower + colapsar espacios + quitar ®™.
- Dosis: `500mg`, `1g`, `0.5%` (coma decimal → punto). **Dosis distinta = rechazo duro** aunque el nombre fuzzy sea alto (Kitadol 500 ≠ Xumadol 1000).
- Forma: mapa comp/comprimidos/tabletas → `comprimido`; caps/cápsulas → `capsula`; etc.
- Pack: `x 20`, `c/24`, `20 comprimidos` → entero. Pack distinto **baja** score; no auto-link si pack difiere y no hay EAN.
- No inventar principio activo desde el nombre comercial sin catálogo ISP.

### Zona gris

`match_status` implícito:

- `linked` — `medication_id` seteado
- `unlinked` — visible por cadena/SKU, no entra al ranking “mismo medicamento”
- (futuro) `review` — tabla de candidatos para humano/admin

Sin filas en `medications` / `medication_names` (catálogo ISP vacío), el writer **solo** persiste SKU+precio por cadena. Eso es correcto: no inventamos identidad.

## 4. Modelo de precios sin explosión

7 cadenas × ~10–30k SKUs × N runs/día.

**Change-only history:** insertar en `prices` **solo si** cambió al menos uno de:

- `price`
- `original_price`
- `stock_status`

Si nada cambió: actualizar `pharmacy_products.updated_at` (heartbeat de “visto”) y no insertar fila.

Estimación: con 2 cambios de precio/semana/SKU → ~2–4 M filas/año peores casos; con change-only realista ~cientos de miles. Índice existente `(pharmacy_product_id, recorded_at DESC)` basta para “último precio” y series.

**Retención (ops, no código aún):** job mensual archiva/borra puntos intermedios de más de 18 meses dejando 1 muestra/día; o partición por mes si crece.

No hay `current_price` denormalizado en schema hoy: el “precio actual” es el último `prices` por producto (query indexada). Si el ranking se vuelve caliente, añadir `pharmacy_products.latest_price` + trigger/update en writer.

## 5. Anomalías

Antes de publicar un precio nuevo, comparar con el último precio no-cuarentena:

| Condición | Acción |
|---|---|
| `price <= 0` | Descartar (Farmex Cenabast $0 ya filtrado en conector) |
| `price < 200` y nombre no sugiere monodosis/muestra | Quarantine |
| `price < 0.15 * last` o `price > 8 * last` | Quarantine + log |
| `price` cae >70% y no hay `original_price`/`discount` coherente | Quarantine |

**Quarantine:** no insertar en el stream público; contar en `stats["quarantined"]`; log estructurado. Un operador puede re-aceptar más adelante (admin). Ofertas reales profundas existen — por eso el umbral es agresivo (15%/8×) y no 50%.

## 6. Ética y límites

Defendible:

- Precios y stock **públicos** de e-commerce, con rate limit, delays, User-Agent identificable (`FarmaciaCompareBot/+https://…`).
- Respeto a `robots.txt` (sitemap vs `start=`).
- Un job por cadena, `max_instances=1`, intervalos ≥ 6 h.
- No reintentar en bucle un endpoint que devuelve 403/404 de plataforma.

No hacer aunque sea técnicamente posible:

- Bypass de paywall / login / bot- fort (Akamai, PerimeterX) con farms de proxies.
- Credenciales de empleados, APIs internas no públicas, volcado de datos personales de recetas.
- Scraping de `farmaciasdoctorsimi.cl` además de `drsimi.cl` (duplicado de cadena).
- Publicar match de identidad con confianza media “porque el ranking se ve más lleno”.
- Mentir el User-Agent solo para evadir bloqueos después de un 403 legítimo — si el sitio dice no, documentar y bajar frecuencia o negociar feed.

Contacto ops (rellenar en prod): `bots@farmaciacompare.cl` en el UA.

## 7. Operación local

```powershell
. .\scripts\dev-env.ps1
.\scripts\setup-local.ps1 -SyncPharmacies
cd workers\scraper
poetry run scraper list-chains
poetry run scraper scrape farmex          # Shopify, barato
poetry run scraper scrape-all             # 7 cadenas — suave con el rate limit
```

Postgres: `localhost:5432`, user/db `farmacia` / `farmaciacompare`.
