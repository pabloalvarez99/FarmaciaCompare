# Coordinación Claude ↔ Grok

Dos agentes trabajando sobre el mismo repo al mismo tiempo. Este archivo evita
que se pisen. Actualizar cuando cambie el reparto.

Última actualización: 2026-08-01 noche (Claude session limit → Grok takeover).

## Reparto actual

| Área | Dueño | Archivos |
|---|---|---|
| Matching / identity / anomalías | **Grok** | `workers/scraper/src/matching/**`, `product_identity.py`, `anomaly.py`, `price_writer.py`, `base_scraper.py`, `scheduler.py` |
| `registry.py` (wire de cadenas) | **Grok** (single-owner) | `workers/scraper/src/registry.py` + `tests/test_registry.py` |
| Conectores por plataforma | **Grok** (evoluciona; Claude los creó) | `workers/scraper/src/connectors/*.py` |
| Infraestructura GCP | **Claude** (pausado) | `cloudbuild.yaml`, `.gcloudignore`, `services/api-gateway/Dockerfile`, `docs/infra-gcloud.md` |
| Deploy y wiring de la web | **Claude** (pausado; `apps/web/**` libre si hace falta) | `apps/web/**`, config de Vercel |
| Stack local de desarrollo | **Grok** | `scripts/dev-env.ps1`, `scripts/setup-local.ps1`, `infra/docker/**` |
| Docs de handoff / bitácora | quien cierra la pasada | `docs/prompt-grok-continuar.md`, `docs/coordinacion-agentes.md`, `bitacora.md` |

### Grok en curso (2026-08-01 noche) — Claude en session limit
- Claude: session limit hasta **~3:20am America/Santiago**. Agentes UI/Preunic/images muertos mid-flight.
- **Grok owns matcher + registry wire.** Matcher fail-closed + knop + preunic wired. MercadoFarma ya estaba.
- Registry: **10 cadenas** online + **~132 físicos Coquimbo** (Places).
- Places: `tablero-iner-maps` key server; CLI `discover-places` / `import-places`; docs `places-coquimbo.md`.
- API live pharmacies Coquimbo; web `/farmacias` + hero Coquimbo-first en Vercel.
- `image_url`: schema+writer+API listos; **0 filas pobladas** en prod hasta re-scrape.
- **`relink` solo dry-run** (80: linked=4 grey=17 none=59). **No** scrapear prod en masa (f1-micro).

Regla práctica: **releer el archivo antes de editarlo**. Los dos estamos
escribiendo en caliente y la copia en memoria se queda vieja rápido.

## Estado del reparto de datos

- `.env` → Postgres **local** (Docker, `localhost:5432`). Dev.
- `.env.production` → **Cloud SQL** (`34.176.88.36`). Producción. Gitignored.

Ninguno de los dos pisa el archivo del otro. El scraper elige por `DATABASE_URL`
del entorno. **Nunca pegar secretos en docs ni en el vault.**

## Matching: evidencia histórica + estado actual

El catálogo ya está cargado (34.166 medicamentos, 35.309 nombres, 586 principios
activos, 34.052 con código de barras), importado desde el sistema tu-farmacia con
`workers/ingestion/src/tufarmacia_importer.py`.

**Vinculación por código de barras: hecha y segura.** ~20.6k `pharmacy_products`
con `medication_id` por EAN exacto contra `medications.barcodes`. Identidad sin
heurística.

**Vinculación por nombre: `relink` full NUNCA se ejecutó** (solo dry-run). Motivo:
falsos positivos inaceptables antes del fail-closed. Ejemplo del dry-run viejo
sobre 1.200 productos (`linked=388`):

```
LINK  0.92 'Leche en Polvo Etapa 3+ 700 gr'      → guante ex nitrilo negro m l polvo x 100
LINK  0.90 'Shampoo Argan 300 ml'                → dalex shampoo 300 ml
LINK  0.90 'Pilexil Serenoa Shampoo Medicado'    → dalex shampoo 300 ml
LINK  0.92 'Extra Suave Extra Grande Toalla Humeda' → cotidian plus 24un grande
LINK  0.92 'Clinical Desodorante Femenino Crema' → nivea desodorante clinical barra mujer 96h
```

El primero es leche de fórmula emparejada con guantes de nitrilo porque ambos
contienen "polvo". Un vínculo equivocado le muestra al usuario el precio de otro
producto: es el peor error posible en este producto, peor que no mostrar nada.

En **medicamentos** el matcher ya andaba bien (dosis + principio activo anclan):

```
LINK  1.00 'Anfibol Nebivolol 5 mg 30 Comprimidos'   → nebivolol 5 mg
LINK  1.00 'Eutirox 137 Levotiroxina 137 mcg'        → levotiroxina 137 mcg
LINK  1.00 'Ciriax Ciprofloxacino 500 mg 10 Comp'    → ciprofloxacino 500 mg
```

### Segundo defecto histórico: dosis sí, tamaño de envase no

El auto-vínculo por nombre también corre dentro de `PriceWriter.write_product`,
no solo en `relink`. Con Dr. Simi se veía:

```
CORRECTO  'Pregabalina 150 mg 30 cápsulas'              -> NEVINEX 150MG.30CAP. (B.E)
CORRECTO  'Paracetamol 500 mg 16 comprimidos'           -> PARACETAMOL 500MG.16COM.
CORRECTO  'Flucloxacilina 500 mg 12 cápsulas'           -> FLUCLOXACILINA CAP 500 MG X 12
MAL       'Levetiracetam 100 mg/mL solución oral 300 mL'-> KOPODEX 100MG.120ML   (300 vs 120 mL)
MAL       'Indometacina 25 mg 30 cápsulas'              -> INDOMETACINA 25MG.24COM. (30 vs 24)
```

Mostrar el precio de un frasco de 120 mL como si fuera el de 300 mL le dice al
usuario que ahorra cuando está viendo menos producto.

### Estado post-Grok (2026-08-01 noche) — FAIL-CLOSED IMPLEMENTADO

Grok cerró defectos a + b en matcher/identity:

- Pack volume / unidades de envase (regla dura si ambos lados declaran y no coinciden)
- Dose médica / concentración (mg/mL, etc.)
- Filtro cosmética + `attributes->>'isMedicine'`
- Barcode EAN-only; compact CH
- Suite + FPs documentados como tests que **deben fallar** el auto-link

**Siguiente paso (no código):** dry-run `relink` + review de muestra a ojo. Solo
después relink real. No re-scrape masivo hasta bajar escritores en f1-micro.

### 2026-08-02: catálogo ISP importado — y un FP nuevo que BLOQUEA el relink

Se importó el registro sanitario del ISP (7.876 medicamentos nuevos). Catálogo:
34.166 → **42.042** medicamentos, 35.309 → **50.443** nombres, 586 → **1.741**
principios activos. Solo 3 colisiones contra los nombres existentes, y los
30.977 vínculos previos quedaron intactos.

Efecto en `relink --dry-run --only-medicine`:

| Cadena | Antes | Después |
|---|---|---|
| salcobrand | linked=0 grey=65 none=235 | **linked=137** grey=72 none=91 |
| ahumada | linked=0 grey=26 none=274 | **linked=134** grey=56 none=110 |

La mayoría de los LINK nuevos son correctos y verificables a ojo:

```
LINK 1.00 'Firialta Finerenona 20mg 28 Comprimidos'  → firialta comprimidos recubiertos 20 mg finerenona
LINK 1.00 'Dalacin C Clindamicina 300mg 16 Cápsulas' → dalacin c capsulas 300 mg clindamicina
LINK 1.00 'Sabril Vigabatrina 500mg 60 Comprimidos'  → sabril comprimidos recubiertos 500 mg vigabatrina
```

**PERO el relink sigue sin correrse en modo escritura**, por este falso positivo:

```
LINK 0.92 'Nevanac Nepafenaco 0.1% Solución Oftálmica 5ml' → 3 a ofteno solucion oftalmica 0.1%
LINK 0.92 'Osmolub 0.1% Solución Oftálmica 10ml'          → 3 a ofteno solucion oftalmica 0.1%
```

Verificado con el matcher directo: `conf=0.917`, `method=structured`, y
`should_auto_link()` devuelve **True**. O sea, pasa el gate.

Son tres productos oftálmicos **distintos**: nepafenaco es un AINE, Osmolub es
un lubricante ocular, y "3-A Ofteno" es otra cosa. Lo único que comparten es
`0.1%` y la forma farmacéutica.

Causa probable: el nombre del catálogo empieza con el token numérico `3`
(de "3-A Ofteno"). El gate de "token de marca o principio activo compartido"
acepta ese `3` como token compartido, y con la dosis y la forma coincidiendo la
confianza sube lo suficiente para auto-vincular. Dos productos que solo
comparten `0.1%` no deberían llegar nunca a 0.92.

Sugerencia (cancha del dueño del matcher): que un token puramente numérico o de
1-2 caracteres no cuente como token compartido para el gate. Un número no
identifica una marca ni un principio activo.

### 2026-08-02 (cont.): vía de administración agregada a `_NOISE` — RESUELTO

`_NOISE` en `matcher.py` tenía `topica`, `vaginal`, `oral` pero **no**
`oftalmica`, `otica`, `nasal`, `unguento`, `pomada`. Así `_content_tokens`
tomaba `oftalmica` como token de marca/principio activo, el gate duro pasaba, y
dos soluciones oftálmicas cualesquiera de la misma concentración se
auto-vinculaban a 1.00:

```
1.00 'Oftol Loteprednol 0,5% Sol. Oftálmica'  → kaph solucion oftalmica 0.5%   (esteroide vs lubricante)
0.96 'Modusik-A Ciclosporina 0,1% Sol. Oft.'  → 3 a ofteno solucion oftalmica 0.1%
0.92 'Nevanac Nepafenaco 0.1% Sol. Oftálmica' → 3 a ofteno solucion oftalmica 0.1%
```

Agregadas al set las vías y formas que describen **cómo** se administra y nunca
**cuál** es el fármaco: `oftalmica/o`, `otica/o`, `nasal`, `ocular`, `unguento`,
`pomada`, `emulsion`, `nebulizacion`, `inhalacion`, `inhalador`, `supositorio`,
`ovulo`, `parche`, `ampolla`, `shampoo`, `champu`, `locion`, `pote`, `sachet`,
`sobres`.

Verificado: los 5 falsos positivos oftálmicos ahora dan `none`; los verdaderos
(`Dermovate → dermovate pomada topica 0.05% clobetasol`, `Sabril`, `Dalacin C`)
siguen en 1.00. 415 tests scraper + 166 ingestion pasan.

### PENDIENTE CRÍTICO: alias genéricos que colapsan fármacos distintos

**El `relink` en escritura sigue prohibido.** Revisando la muestra de Cruz Verde
apareció esto:

```
LINK 0.99 'Humalog Kwik Insulina Lispro 100 UI 5 Cartridge'    → insulina 100 ui ml
LINK 0.99 'Humulin-N Insulina Humana Protamina Zinc 100 UI'    → insulina 100 ui ml
LINK 0.99 'Tresiba Flextouch Insulina Degludec 100 UI/ml'      → insulina 100 ui ml
```

El alias `insulina 100 ui ml` apunta a Actrapid, Apidra, Insulatard y más. Son
insulinas **farmacológicamente distintas**: rápida, NPH intermedia, glulisina,
lispro, degludec. Mostrarle a un diabético el precio de una insulina rápida como
si fuera su basal no es un error cosmético.

Causa: el alias genérico se construye como `principio activo + dosis`, y para
insulinas el "principio activo" queda en `INSULINA` a secas, sin el tipo. La
concentración 100 UI/mL es común a casi todas, así que no desambigua.

Mismo patrón, menor gravedad: `Concor AM Bisopropol` → `bisoprolol fumarato`
(Concor AM lleva amlodipino además), y `Nistatina 100000 UI Suspensión Oral` →
`nistatina ov 100000 ui` (óvulo vaginal vs suspensión oral: vía distinta).

Caminos posibles: no generar alias genérico cuando el principio activo es de una
familia con múltiples moléculas (insulinas, heparinas); o exigir que la forma
farmacéutica coincida además de la dosis cuando el match es contra un alias
`nameType='generic'`.

### 2026-08-02 (cont. 2): tres gates nuevos en `matcher.py` — 5 de 6 cerrados

Medido primero: de 3.399 alias genéricos, **2.060 apuntan a 1 medicamento**,
**211 colapsan varios y no llevan dosis** (`amlodipino` a secas cubre 80
medicamentos, 5 mg y 10 mg por igual) y **1.128 colapsan con dosis**. En total
**3.328 claves ambiguas**.

Tres reglas agregadas:

1. **Clave ambigua → nunca auto-link.** `DrugMatcher.__init__` cuenta cuántos
   `medication_id` distintos comparten cada `normalized_name`; los repetidos van
   a `self._ambiguous` y fuerzan `grey_zone`. Una clave compartida no puede
   decir cuál de los N medicamentos era: el vínculo sería un sorteo entre
   iguales. Esto cierra el caso de las insulinas.
2. **Vías de administración fuera de `_content_tokens`** (ver bloque anterior).
3. **Un combo no colapsa sobre uno de sus componentes.** `_is_combination()`
   exige letras a ambos lados de la barra, así que `500mg/5ml` (concentración) y
   `20/12.5` (proporción de dosis) **no** se confunden con un combo — verificado.

Resultado sobre el set de regresión: **5 de 6 falsos positivos bloqueados,
7 de 7 vínculos correctos preservados.** 415 tests scraper + 166 ingestion pasan.

**El que queda: `Concor AM Bisopropol Fumarato 5 mg` → `bisoprolol fumarato
comprimidos 5 mg`.** Concor AM lleva amlodipino además, pero el nombre **no lo
dice**: el segundo fármaco vive solo en el sufijo de marca "AM". Ninguna regla
que lea el nombre puede saberlo. Se necesitaría una fuente que declare la
composición completa por producto — el registro ISP la tiene en su ficha de
detalle, a un request por producto.

Alcance del riesgo: **366 productos sin vincular tienen nombre de combo (`X / Y`)
y el catálogo tiene 0 claves con esa forma**, porque `normalize_name` colapsa la
barra entre letras. O sea que hoy un combo declarado no encuentra su par exacto y
tiende a caer sobre un componente; el gate 3 lo bloquea. Los combos con el
segundo fármaco escondido en la marca siguen abiertos.

## Hueco de producto abierto

Sin `medication_id` no hay comparación cruzada entre farmacias. Hoy:

- Catálogo **sí** está en Cloud SQL (import tu-farmacia).
- Vínculos seguros = barcode.
- Name-match pendiente de dry-run limpio post fail-closed.
- Salcobrand/Cruz Verde casi sin barcode → dependen de attrs + re-scrape.
- `image_url` en prod con **0** filled.
- knop / preunic / mercadofarma en registry, **0** productos en prod aún.

Lo que **no** sirve: `scripts/seed.mjs` (inventa precios + historial falso).

## Convenciones compartidas

- Precios en CLP enteros, sin decimales.
- `parse_price` es para texto de página (`$12.990` → `12990`).
  `parse_machine_price` es para números de API (`"1004.0"` → `1004`). Mezclarlos
  produce precios inflados ×10.
- Un precio `$0` no es una oferta: Farmex publica variantes placeholder y
  Farmaloop marca así lo agotado.
- Cada cadena tiene una farmacia `type = 'online'`; los precios scrapeados son
  nacionales y cuelgan de esa fila, no de una sucursal física.
- `registry.py` es la fuente única de cadenas. Agregar una cadena es una entrada
  ahí; el CLI, el scheduler y el seeding la toman solos. **Single-owner: Grok.**

## Verificación antes de dar algo por hecho

```bash
cd workers/scraper
python -m pytest tests -q --ignore=tests/test_dr_simi.py   # ~319 passed hoy
python -m src.cli scrape <cadena> --dry-run --limit 3      # golpea el sitio real
python -m src.cli relink --dry-run --limit 500             # NUNCA sin --dry-run primero
```
