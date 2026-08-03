# FarmaciaCompare — Bitácora

## 2026-08-02 (auditoría de vínculos + alcance nuevo) — Claude

### Lo más importante: la tasa de error de vínculos era 16,35%

No la sabíamos. La medí y estaba mal.

De los 35.248 vínculos en producción, 20.737 venían de **código de barras exacto**
(identidad, sin heurística) y **14.511 del matcher difuso**. Sobre esos difusos,
**2.372 estaban equivocados — uno de cada seis**.

| Categoría | Casos |
|---|---|
| Envase distinto | 1.181 |
| Dosis distinta | 463 |
| Forma distinta | 252 |
| Combo a componente | 236 |
| Volumen distinto | 179 |
| Clave ambigua | 60 |
| Vía distinta | 1 |

**Alcance real del daño — verificado, no supuesto.** La web (`/precios` y
`/precios/[barcode]`) agrupa por **código de barras**, así que esa superficie nunca
estuvo afectada: el EAN es identidad exacta. Los vínculos malos vivían en la base y
en el endpoint público `?groupBy=medication`, que responde 200 con datos pero que la
web todavía no consume.

O sea: **riesgo latente a punto de activarse, no daño consumado**. Limpiar igual era
lo correcto — esa vía es la única forma de comparar Cruz Verde, Salcobrand y
Dr. Simi, que no publican EAN, y va a ser la superficie principal apenas la web la
use. Mejor limpio antes de exponerla.

Ejemplos reales, todos presentes en la base hasta hoy:

```
Pañales Babysec XXXG 112 Unidades        → BABYSEC PREMIUM XXG.32UN.
Pañal Emubaby Super Premium XXG 34 Un.   → BABYSEC PREMIUM XXG.32UN.   (otra marca)
La Roche Posay Agua Termal 150 mL        → VICHY AGUA TERMAL 150 ML    (otra marca)
Gotely 0,4 mg x 30 Cápsulas              → GOTELY DUO 0.5/0.4MG.30CAP. (simple vs combo)
Xuzal Levocetirizina 5 mL                → ALERPRIV JBE. 100 ML        (20× volumen)
Vitde Gotas Vitamina D3                  → VITAMINA D3 TABLETAS EFERV. (otra forma)
```

**Corregido:** 2.372 vínculos cortados. Re-auditoría: **0 sospechosos sobre 12.139
difusos**. Los 20.737 respaldados por EAN nunca estuvieron en discusión.

Herramientas nuevas, ambas de bajo riesgo:
- `workers/scraper/src/audit_links.py` — solo lectura, produce la tasa de error.
  Correrlo después de cada scrape para vigilar que no vuelva a subir.
- `workers/scraper/src/clean_bad_links.py` — corta los malos, `--dry-run` primero.

**Por qué cortar y no dejar:** `medication_id` es dato derivado, no fuente. El
scrape queda intacto; un producto sin vínculo sigue buscable y con precio, solo
deja de agruparse. Y los riesgos son asimétricos: cortar un vínculo bueno cuesta
una comparación; dejar uno malo cuesta un precio equivocado en una decisión de
salud.

**Lo que enseñó:** la categoría dominante de error fue *envase distinto*, y los
casos eran pañales y suplementos — categorías nuevas emparejadas con un matcher que
asume semántica farmacológica. Es la evidencia empírica de que **el matcher tiene
que ser por categoría**, que estaba en el plan como intuición.

### La causa raíz: el matcher premiaba coincidir pero no castigaba diferir

Una hora después de la limpieza la tasa **había vuelto a 2,83%**. Los schedulers
siguen corriendo y `PriceWriter` auto-vincula en cada scrape, así que la limpieza
sola es un parche: hay que arreglar la fuente.

Dos defectos encadenados en `matcher.py` / `product_identity.py`:

1. **El matcher daba un bonus cuando `pack_count` coincidía, pero no había ningún
   gate cuando difería.** Un candidato podía ganar por similitud de nombre
   vendiendo otra cantidad. Eso explica que `envase_distinto` fuera la categoría de
   error #1 con 1.181 casos.
2. **`extract_pack_count` no parseaba `30 cap blandas`.** La lista de unidades tenía
   `caps` pero no `cap` en singular — que es justo como abrevia el catálogo
   (`NEVINEX 150MG.30CAP.`). Con `pack_count = None` de un lado, el gate
   `query.pack_count and cand.pack_count` se cortocircuita y **nunca dispara**.

O sea: aunque el gate hubiera existido, no habría servido para las filas del
catálogo. Los dos defectos se tapaban mutuamente.

**Arreglado:** gates duros para `pack_count`, `pack_volume_ml` y forma
farmacéutica; y la lista de unidades ampliada con las abreviaturas reales del
catálogo (`cap`, `com`, `un`, `sobres`, `ampollas`, `óvulos`, `parches`,
`grageas`, `jeringas`…).

Verificado: **8 de 9 falsos positivos conocidos bloqueados, 6 de 6 vínculos
correctos preservados**, 415 tests pasan. El único que resiste es `Concor AM`, que
no es resoluble desde el nombre — el segundo fármaco vive en el sufijo de marca.

Segunda limpieza: 639 vínculos cortados → **0% de error** otra vez, esta vez con la
fuente corregida. Imagen del job de Cloud Run redesplegada para que los scrapes
programados usen el matcher nuevo.

### Categorías: 54.608 productos dejan de ser ruido

El proyecto dejó de ser un comparador de remedios. Escrito y verificado en producción:

| Categoría | Productos | Cadenas |
|---|---|---|
| Medicamentos | 23.786 | 9 |
| Cosmética y maquillaje | 10.062 | 10 |
| Higiene y cuidado personal | 7.120 | 10 |
| Dermocosmética | 6.487 | 10 |
| Suplementos y vitaminas | 4.191 | 10 |
| Cuidado del bebé | 1.569 | 10 |
| Dispositivos y accesorios | 1.393 | 10 |
| Sin categoría (NULL) | 22.925 | 10 |

**30.822 productos de salud y belleza que antes se filtraban como ruido ahora son
catálogo.** Ya estaban scrapeados, con imagen y atributos; solo les faltaba
categoría.

Tres defectos corregidos en `classify_categories.py` antes de escribir:

1. **Mascarillas quirúrgicas en higiene.** El comentario nombraba
   `"primeros auxilios"` entre las etiquetas de dispositivo pero **faltaba en la
   lista de patrones**. La intención estaba escrita, la implementación no.
2. **El mismo pañal en dos categorías según la tienda.** `paniales` (grafía de
   Cruz Verde) iba a bebé, pero `panales` a secas vivía en la regla de higiene
   junto a incontinencia. El mismo Babysec quedaba en `bebe` desde Ahumada y en
   `higiene` desde Farmex. Para un comparador eso es letal: el producto que
   querés comparar aparece en dos lugares. Movido a bebé con guarda, los de
   adulto siguen en higiene por sus patrones propios.
3. **Toallitas para lentes como medicamento.** Farmex las etiqueta con un blob
   que incluye la palabra "medicamentos"; nombrar la etiqueta precisa la hace
   ganar en la primera pasada.

**Sobre Farmex, corrigiendo una conclusión apurada:** sí publica palabras de
categoría dentro de `tags` (`antimicoticos`, `panales`, `insumo medico`,
`cosmetico`), mezcladas con ruido de precios (`over 10000`, `1000 5000`),
inventario (`persistente`) y convenios de salud (`banmedica`, `pluxee`,
`vidatres`, `miahealth`). Por eso 7.593 de sus 22.785 sí se clasificaron. Los
15.098 restantes traen solo ruido — no hay dato que leer, y quedan en NULL en vez
de forzarles una categoría inventada.

### La marca no se estaba mirando, y fuera de medicamentos es la identidad

El auditor revisaba dosis, envase, volumen, forma y combos — **nunca la marca**.
En medicamentos eso es correcto: paracetamol genérico y Panadol son el mismo
producto, y tratarlos como distintos rompería la bioequivalencia. En cosmética,
higiene, suplementos y bebé la marca **es** la identidad, y esa ceguera dejó
pasar 710 vínculos equivocados.

Lo encontró el agente de deploy revisando el sitio en vivo: cuatro shampoos de
marcas distintas —Eucerin Dermocapillaire, Le Petit Olivier, Katmandú— agrupados
a `ALL OUT SHAMPOO 250 ML PEDIC`, un pediculicida. El sitio publicaba "$3.999 de
ahorro" comparando un shampoo anticaspa con uno antipiojos.

Otros que estaban vivos:

```
La Roche-Posay Agua Micelar Toleriane  -> AVENE LOC.MICELAR    (otra marca)
Filorga Time Filler Intensive          -> EUC.VOL-FILLER       (Eucerin)
VitaminLife Calcium + Vitamin D        -> VITAMINA K2          (otro nutriente)
SKIN1004 Madagascar Centella Cream     -> GARNIER BB CREAM
```

**783 cortados**, 710 por marca. Auditoría de vuelta en 0%.

**Dos intentos fallidos, documentados porque el fallo enseña:**

1. **Exigir la marca literal** cortaba vínculos correctos: `ALCON Opti Free
   Express` → `OPTI-FREE EXPRESS` es válido (el campo `brand` guarda el
   fabricante, no la línea) y `Hawaiian Tropic` → `H.TROP.GEL` también (el
   catálogo abrevia). Resuelto exigiendo además que los títulos no compartan
   dos palabras de contenido.
2. **Eximir cuando comparten una palabra de 8+ letras** salvaba
   `BIODERMA Sensibio` → `SENSIBIO-AR`, pero también eximía `original` y
   `vitamina` — ocho letras, cero identidad. **Distinguir una línea de producto
   de un sustantivo genérico necesita vocabulario, no longitud.** Revertido.

Quedó la regla simple con su defecto medido en el docstring: **~1 de cada 10
cortes pierde un vínculo bueno**. Se envía así porque los costos no son
simétricos.

### Identidad derivada para lo que no tiene registro ni EAN

`workers/scraper/src/derived_identity.py` (+24 tests). Llave
`marca + tamaño + palabras distintivas` para las categorías sin registro
sanitario. Medido sobre 25.031 listados: **1.255 grupos comparables nuevos**,
contra los 15 que cosmética tiene hoy por código de barras.

Dos defectos encontrados construyéndolo:

- **Colapso de variantes.** La primera llave tomaba 3 palabras alfabéticas y
  juntaba `Esmalte Vogue Jaguar`, `Flamingo` y `Resiliencia`. En cosmética la
  variante *es* la identidad; la llave conserva todas las palabras distintivas.
- **`1L` contra `1000ml`.** Lo atrapó un test: `1000ml` sobrevivía como palabra
  distintiva por ser alfanumérico mientras `1L` no generaba token. El tamaño ya
  es campo propio, así que se quita del texto antes de tokenizar.

### El alcance nuevo trae catálogo, no comparaciones

| Categoría | Listados | Con EAN | Comparables |
|---|---|---|---|
| Medicamentos | 23.786 | 46% | 2.694 |
| Cosmética | 10.062 | **7%** | **15** |
| Higiene | 7.120 | 20% | 175 |
| Dermocosmética | 6.487 | 25% | 121 |
| Bebé | 1.569 | 12% | 6 |

Cosmética tiene 10.062 productos y 15 comparaciones. Categorizar los hizo
visibles y filtrables; **hacerlos comparables es otro trabajo**, y necesita el
catálogo derivado.

**Historial de precios: no construirlo todavía.** 1,1 precios promedio por
producto, solo 1.974 con más de uno. Un gráfico hoy mostraría un punto suelto.
Esa parte de Fase 3 necesita que pase tiempo, no código.

### Categorías expuestas en API y web

`GET /api/v1/products/categories` con conteos reales, y filtro `?category=` en
búsqueda. Verificado en producción: `q=shampoo` da 1.615 sin filtro, 1.095 en
cosmética, 21 en higiene, 65 en medicamento (shampoo con ketoconazol — la
distinción correcta), y **0** para una categoría inexistente.

Detalle que importaba: hay **dos planes de consulta** y el barato ignoraba
`filters` por completo, así que filtrar sin tocar precio habría devuelto el
catálogo entero. Va en ambos, y en el conteo además de la página.

Chips de categoría en `/precios`, con conteos traídos de la API. Sin chip de
"sin categoría": ofrecer los 22.925 NULL como cajón navegable convertiría un
"no sabemos" en una clasificación.

### `?query=` devolvía el catálogo entero con HTTP 200

Un parámetro mal escrito hacía que `q` cayera a vacío, y vacío significa
"navegar todo": 74.778 resultados alfabéticos empezando por "100 Fluid Color
Protector Solar", con 200 OK. Ahora es 400 con sugerencia (`¿quisiste decir
'q'?`). Los parámetros de analítica (`utm_*`, `gclid`, `fbclid`) pasan sin
error — no piden nada, y rechazar un enlace compartido por traerlos sería
romper una petición bien formada. 105 tests en el gateway.

### El techo de cobertura no son los gates

De 400 productos de Salcobrand sin vincular: **258 no tienen candidato en el
catálogo** (64%), 73 otro gate, 38 confianza baja, 30 clave ambigua. Aflojar
gates no sube la cobertura; completar el catálogo sí.

### Alcance ampliado y documentado

`CLAUDE.md` reescrito de cero. El producto ya no es un comparador de medicamentos:
apunta al nivel de **solotodo.cl** aplicado a salud y bienestar — medicamentos,
suplementos, dermocosmética, cosmética, higiene, cuidado del bebé, dispositivos.
Perfumería queda **fuera** por decisión explícita.

Consecuencia que cambia el trabajo: lo no-medicamento **deja de ser ruido a
filtrar** y pasa a ser catálogo. Los 8.880 productos de Preunic y los 4.604 de
Curie ya están scrapeados con imagen y atributos — es el mayor valor no explotado
de la base.

`docs/PLAN.md` nuevo: arquitectura por categorías, las 7 llaves de identidad, el
método abajo-arriba para las categorías sin registro oficial, y las fases con
criterio de salida medible.

### Fase 1 arrancada

- Tabla `categories` sembrada con las 7 categorías
- `pharmacy_products.category_id` y `medications.specs` en el schema
- Clasificación, deduplicación y retención en curso con verificación adversarial

### Estado

77.241 listados · 42.042 en catálogo · 32.876 vínculos · **0% de error** ·
99,5% con imagen · 415 tests scraper + 166 ingestion

## 2026-08-02 (loop: ahumada + matcher % + farmaloop attrs) — Grok

- **Ahumada scrape complete**: 5406 written, **5406/5406 imgs**, 1090 linked, 0 errors.
- **Matcher fixes (suite 354 pass)**:
  - Coma decimal chilena `0,5` → `0.5` (antes `0 5` → extraía `5mg` falso).
  - `%` con `(?!\w)` en vez de `\b` (antes **toda** dosis `%` se perdía).
  - Combo oftálmico `0,005 % / 0,5 %` y `0.3/0.1 %`.
  - Combo tableta bare `20/12,5` → `20/12.5mg` (bloquea FP Olmepress-D → olmesartan solo).
- **Relink CLI**: `--only-medicine` + `--chain`. Dry-run only-med 400 → **0 LINK**;
  post-%-fix 300 → 1 LINK (Olmepress FP) → fix combo bare → match None. **Sin write**.
- **Farmaloop**: `extract_attributes` (isMedicine desde productCategory, bioeq, PA,
  rx). Prod attrs siguen 0 hasta re-scrape.
- **Imágenes prod (post-ahumada)**: ahumada 5406/5406; farmex ~22242/22272;
  CV ~6000/7699 mid; **salcobrand 0/12795** (deuda re-scrape, mapper OK).
- **Relink write**: NO — dry-runs no dan LINKs limpios en masa.
- **Live API**: search `paracetamol` devuelve `imageUrl` real (Dr.Simi VTEX + Farmex Shopify).
  Coquimbo pharmacies API **132** (La Serena 42) con lat/lng. Web vercel `/farmacias` 200.
- **Salcobrand scrape complete**: written 12781, **imgs 12741/12795 (~100%)**, linked 2742, 0 errors.
  Log: `cli-logs/2026-08-02-scrape-salcobrand.txt`.
- **Cruz Verde** mid: n~9.4k, imgs ~90% (sigue).
- **Farmaloop re-scrape complete**: written 4860, **attrs 4860/4860**, isMed=3831,
  imgs 4786 (98%), linked 3205. Log: `cli-logs/2026-08-02-scrape-farmaloop-attrs.txt`.

## 2026-08-02 (combo-dose inhalers + scrapes) — Grok

- **Matcher**: dosis combinadas `250/25 mcg` → `250/25mcg` (antes solo tomaba el
  2º número). Pack `120 dosis` / `200ds`. FPs Fluxamol→Alart y Aurituss 25/250→125/25
  ahora hard-reject. Tests matcher 33 pass.
- **Relink dry 500 (sesión)**: linked=9; 2 FPs inhalador documentados → fix arriba.
  **Aún no** relink write a ciegas.
- **Preunic scrape**: 8880 products, 0 linked (beauty), full images.

## 2026-08-01 (knop + mercadofarma scrapes + relink) — Grok

- **Knop scrape prod success**: 1651 written, 1651 prices, 0 errors.
  - images **1651/1651**; linked=0 (natural/homeopático → grey only, fail-closed OK).
- **MercadoFarma scrape success**: 4970 written, 4963 prices, 7 quarantine, **776 linked**, 0 errors.
  - images **4784/4970**; attrs 4966.
- **Curie re-scrape**: 4604 written, 4598 imgs, 2895 linked.
- **Dr. Simi re-scrape**: 1294 written, ~1292 imgs, 571 linked.
- **Farmaloop re-scrape**: 4860 written, success (imgs via COALESCE update).
- **Cadenas con fotos**: knop, mercadofarma, curie, dr_simi, CV parcial. Faltan farmex/salcobrand/ahumada re-scrape pesado.
- **Relink**: dry-run 500 → linked=9 grey=83 none=408 (0 hard FPs).
  Write `--limit 200` → linked=0 grey=34 none=166.
- **Web** `/farmacias` agrupado por ciudad + Google Maps lat/lng.
- Logs: `cli-logs/2026-08-01-scrape-knop.txt`, `…-scrape-mercadofarma.txt`

## 2026-08-01 (Coquimbo + Google Places) — Grok

- **Foco producto: Región de Coquimbo** (La Serena, Coquimbo, Ovalle, …).
- **Places via gcloud**: proyecto `tablero-iner-maps`, clave server
  `Tablero INER server` (`places-backend`). Key solo en env runtime
  (`GOOGLE_MAPS_API_KEY` desde `gcloud services api-keys get-key-string`).
  Nunca en git/vault/frontend.
- CLI: `discover-places --region coquimbo`, `import-places --from-json …`
  (`src/places_discovery.py`, `places_import.py`). Docs: `docs/places-coquimbo.md`.
- **Import prod**: ~174 locales `type=physical`, `region=Coquimbo`,
  `rut=gp:<place_id>` (idempotente). Ciudades: La Serena 51, Coquimbo 42,
  Ovalle 35, Illapel 18, + Salamanca/Los Vilos/Vicuña/…
- **API**: `GET /api/v1/products/pharmacies?region=Coquimbo&city=`
- **Web**: hero Coquimbo-first, `/farmacias` directorio, PriceTable default
  ciudad Coquimbo si hay datos locales.
- Precios online siguen siendo **nacionales** (scrapers); directorio físico es
  capa de ubicación regional.


### Relink dry-run (sample 80, 2026-08-01 noche)
- Resultado: linked=4 grey=17 none=59 — fail-closed funciona.
- GREY sospechoso bloqueado (no auto-link): Gaviscon → pañuelo elite.
- LINKs vistos: pregabalina, lorazepam, giabri pack-aware.
- Todavía no se corre relink write en prod.
## 2026-08-01 (Claude session limit → Grok takeover) — Grok

Claude main hit **session limit** (~22:41, reset 3:20am America/Santiago).
Agentes muertos: UI, Preunic (conector sí quedó en disco), images (mid-schema).
Knop conector OK; main Claude había cableado MercadoFarma.

### Grok cerró al cortarse
- **Matcher fail-closed** (defectos a/b): pack_volume_ml, conc mg/mL, cosmética,
  isMedicine, barcode EAN only, compact CH. Suite matcher+FP documentados.
- **Knop + Preunic cableados** en `registry.py` (10 cadenas). Preunic = Empathy.co,
  beauty/drugstore, `isMedicine=false` hoy. Tests unitarios Preunic.
- **image_url**: columna ya en **prod** (0/54.819 filas pobladas — scrapers no
  re-corridos). `price_writer` INSERT/UPDATE COALESCE. API gateway search +
  comparisons expone `imageUrl`. Prisma schema tiene el campo.
- Suite scraper: **319 passed** (`--ignore=test_dr_simi`).
- **No re-scrape prod** esta pasada (db-f1-micro). Poblar imágenes en próximo
  scrape natural o uno por cadena cuando bajen escritores.
- `relink` full sigue prohibido.

### Conteo prod al handoff
farmex 22104 · salcobrand 12258 · cruz_verde 7699 · farmaloop 4860 ·
curie 4604 · ahumada 2000 · dr_simi 1294 · total 54819 · image_url filled 0.

## 2026-08-01 (catálogo + identidad) — Claude

- **Catálogo importado desde tu-farmacia**: 34.166 medicamentos, 35.309 nombres,
  586 principios activos, 34.052 con código de barras. Origen: la tabla
  `products` del sistema de gestión `tu-farmacia-prod`, sacada con
  `gcloud sql export` a GCS — la instancia viva nunca se tocó (ni su red ni sus
  usuarios). Importador: `workers/ingestion/src/tufarmacia_importer.py`.
  Se importan los 34k, no solo los 1.550 `active='t'`: `active` significa "la
  farmacia lo tiene en stock", no "el medicamento existe".
- **20.612 productos vinculados por código de barras exacto.** Un EAN compartido
  es identidad exacta, sin heurística.
- **3.725 grupos comparables** (mismo EAN en 2+ cadenas), contra 2.618 antes.
- **Matching por nombre NO ejecutado**: produce falsos positivos inaceptables
  (leche de fórmula ↔ guantes de nitrilo a 0.92). Detalle y evidencia en
  `docs/coordinacion-agentes.md`, sección para Grok.
- **Precios inventados eliminados de producción.** Había 6 fuentes: portada,
  contador del hero, categorías, lista de cadenas, `/buscar` + `/comparar` +
  `/medicamentos/[id]`, `/alertas`, el autocompletado del buscador, las rutas
  `/api/v1/medications/*` y el `sitemap.xml` (que le daba a Google 40 URLs de
  precios falsos para indexar).
- **Comparación real en el gateway**: `/api/v1/products/comparisons` agrupa por
  EAN y ordena por ahorro; `/comparisons/:barcode` da el detalle. La web tiene
  `/precios` y `/precios/[barcode]`.
- Columna `pharmacy_products.attributes` (jsonb) + extracción de señales de
  identidad en los 4 conectores: Cruz Verde `c_activeIngredient`/`c_dose`/
  `c_format`/`c_isMedProduct`, Salcobrand breadcrumb lvl3 + `options_text`,
  Dr. Simi RefId + categorías, Shopify `product_type`.
- Índices: trigram sobre `raw_name`, `barcode` parcial, `medication_id`,
  `(pharmacy_product_id, recorded_at DESC)`, GIN sobre `medications.barcodes`.
- **Bug corregido**: `shopify_connector.parse_product` calculaba `attributes` y
  nunca lo pasaba al constructor — todos los productos Shopify llegaban con
  `attributes = NULL`. Lo detectó el agente de tests.
- Tests: 173 pasan.

## 2026-08-01

- **Scrapers reescritos: 1 cadena viva → 7.** El conector VTEX cubría cruz_verde,
  salcobrand y ahumada. Las tres dejaron VTEX: sus endpoints
  `<account>.vtexcommercestable.com.br` devuelven **404**. La ingesta de precios
  estaba muerta desde entonces.
- Plataforma real de cada sitio (verificado en vivo, 2026-08-01):

  | Cadena | Plataforma | Cómo se obtiene | Conector |
  |---|---|---|---|
  | Cruz Verde | Salesforce Commerce Cloud | OCAPI `beta.cruzverde.cl/s/Chile/dw/shop/v19_1` + `client_id` del bundle Angular | `ocapi_connector` |
  | Salcobrand | Spree + Algolia | índice `sb_variant_production`, app `GM3RP06HJG` (key restringida por Referer) | `algolia_connector` |
  | Ahumada | Salesforce Commerce Cloud | sitemap + JSON-LD `schema.org/Product` de cada ficha | `jsonld_connector` |
  | Dr. Simi | VTEX (`farmaciasdeldrsimicl`) | `www.drsimi.cl/api/catalog_system/pub/products/search` | `vtex_connector` |
  | Farmex | Shopify | `/products.json` | `shopify_connector` |
  | Farmacias Curie | Shopify | `/products.json` | `shopify_connector` |
  | Farmaloop | Next.js | sitemap + `/_next/data/<buildId>/products/<slug>.json` | `farmaloop_connector` |

- **Por qué sitemap y no paginación**: `robots.txt` de Cruz Verde y Ahumada
  prohíbe cualquier URL con `start`, lo que descarta paginar `product_search` y
  `Search-UpdateGrid`. Ambos publican sitemap; esa es la vía permitida.
- `registry.py` es ahora la única fuente de verdad: CLI, scheduler y seeding de
  farmacias leen de ahí. Agregar cadena = una entrada.
- Precios `$0` de Farmex se descartan: son listados placeholder (Cenabast /
  seguro) que ensuciarían el ranking "más barato".
- Algolia corta en 1000 resultados por query, así que Salcobrand se recorre
  particionado por `taxonomies` y las facetas >1000 se subdividen por letra.
- CLI nuevo: `scrape-all`, `sync-pharmacies`, `list-chains`, flag `--fast`
  (Cruz Verde por búsqueda en vez de catálogo completo).
- Verificado: 97 tests pasan; dry-run en vivo devuelve precios reales de las 7
  cadenas. `farmaciasdoctorsimi.cl` se omite: misma cadena que `drsimi.cl`.
- Próximo paso: correr `sync-pharmacies` + `scrape-all` contra la DB real y
  exponer los precios nuevos en `apps/web`.

## 2026-05-03

- Setup CLAUDE.md proyecto + integración vault Obsidian compartido.
- Estado actual: monorepo Turborepo, `apps/web` deploy Vercel activo, `services/api-gateway` NestJS+Prisma activo.
- Cambios sin commit detectados al setup: edits en `apps/web`, `apps/admin`, `services/api-gateway`. Revisar antes de próximo commit.
- Próximo paso: continuar trabajo en curso (search/admin/payments según estado git).
- Commit setup: `b04e6b6` pushed `master`. Vercel auto-deploy disparado (verificar dashboard — CLI no instalado).

## 2026-08-01 (ingesta producción)

- **Arquitectura:** `docs/architecture-ingestion.md` — health fail-closed, matching,
  historial change-only, anomalías, ética.
- **Código nuevo:** `product_identity.py`, `anomaly.py`; matcher multi-señal;
  `PriceWriter` change-only + quarantine; `scheduler` → `scraping_jobs` + umbrales.
- **UA:** `FarmaciaCompareBot/1.0 (+https://farmaciacompare.cl/bot; …)`.
- **Tests:** 111 passed (sin playwright).
- **Carga real DB (3 cadenas success):**
  - farmex 22 104 scraped → 22 091 price rows (10 quarantine floor)
  - curie 4 604 → 4 599 (5 quarantine)
  - salcobrand 10 119 (Algolia 429 en letter sweep final; backoff añadido)
- **linked=0** en todos: `medications`/`medication_names` vacíos — falta seed ISP.
  Correcto no inventar identidad.
- Algolia: retry/backoff en 429 + delay de página 800–1800 ms.

## 2026-08-01 (producción arriba) — Claude

- **Web**: https://farmacia-compare-web.vercel.app — `/precios` sirve precios
  reales scrapeados.
- **API**: https://api-gateway-446315435132.southamerica-west1.run.app en Cloud
  Run, revisión `api-gateway-00004-62k`, conectada a Cloud SQL por socket
  `/cloudsql/...` (la base nunca se expone a internet).
- Módulo `products` nuevo en el gateway: `/api/v1/products/search` y
  `/api/v1/products/coverage`, que leen `pharmacy_products` directo. Así hay
  precios buscables sin depender del catálogo `medications`, que sigue vacío.
  La búsqueda descarta `source='quarantine'`: un precio que el detector de
  anomalías rechazó no puede aparecer como oferta.
- Página `/precios` en `apps/web` (server component, revalidate 300s). No se
  tocaron las páginas que usan `demo-data`.
- `scripts/deploy-api-gateway.sh` deja build+deploy en un comando y saca la
  credencial de `.env.production`.
- Verificado en producción: "paracetamol" muestra el mismo Algiafin 120 mg/5 mL a
  $3.680 en Dr. Simi y $2.502 en Farmex.

### Bugs de deploy adicionales

8. Cloud Run moría con `Cannot find module '@nestjs/core'`: con pnpm las
   dependencias del servicio viven en `services/api-gateway/node_modules`, no en
   el root. El runner ahora conserva la estructura del monorepo y arranca desde
   `services/api-gateway/dist/main.js`.
9. Prisma moría con `Error loading shared library libssl.so.1.1`: el engine musl
   por defecto espera OpenSSL 1.1 y `node:20-alpine` trae OpenSSL 3. Se agregó
   `binaryTargets = ["native", "linux-musl-openssl-3.0.x"]` y `apk add openssl`.

## 2026-08-01 (infra GCP + producción) — Claude

- **Proyecto nuevo `farmacia-compare-prod`**. No se tocó `tu-farmacia-prod`: ahí
  corre `tu-farmacia-db` sirviendo el sitio vivo `tu-farmacia.cl`.
- Cloud SQL `farmacia-compare-db` (POSTGRES_15, `db-f1-micro`, 10 GB auto-grow,
  `southamerica-west1`/Santiago). Red autorizada: solo la IP del capitán.
- Schema aplicado con `prisma db push` (no hay carpeta `migrations/`).
  `sync-pharmacies` creó las 7 farmacias `type='online'`.
- **Farmex cargado**: 22.106 productos, 22.094 precios, 10 en cuarentena por
  anomalía, 0 errores. Resto de cadenas en curso.
- `.env` sigue apuntando al Postgres local; producción vive en `.env.production`
  (gitignored). No se pisan.
- `.gitignore` ampliado a `.env.*` — `.env.production` no estaba cubierto y
  contiene la contraseña de Cloud SQL.
- Runbook completo: `docs/infra-gcloud.md`. Reparto con Grok:
  `docs/coordinacion-agentes.md`.

### Bugs de build corregidos (el Dockerfile nunca había corrido en CI)

1. `pnpm-lock.yaml` tenía **dos documentos YAML concatenados** (fragmento de
   `pnpm self-install` prepended) → `ERR_PNPM_BROKEN_LOCKFILE` en todo install.
   Commiteado así desde `d31860d`.
2. Faltaba `.gcloudignore`: `gcloud builds submit` ignora `.dockerignore` y subía
   `node_modules` + `services/price-service/target`.
3. `--frozen-lockfile` exige los `package.json` de todos los importers del
   lockfile — faltaban los de `apps/*`.
4. `packages/config` no tiene `node_modules` (solo tsconfigs) → `COPY` fallaba.
5. El runner no copiaba `services/api-gateway/node_modules`; pnpm resuelve por
   symlinks propios de cada paquete.
6. El Dockerfile no compilaba `@farmacia/database` ni `@farmacia/shared-types`
   antes del gateway → `nest build` con 27 errores `TS2307`.
7. `main.ts` ahora escucha en `process.env.PORT` con bind `0.0.0.0` (requisito de
   Cloud Run) y acepta `CORS_ORIGINS`.

### Pendiente

- Deploy a Cloud Run + wiring de `apps/web` (hoy lee `demo-data`, no la DB).
- **`medication_names` vacía** → productos sin `medication_id`, o sea sin
  comparación cruzada entre farmacias. Falta catálogo real del ISP.
  `scripts/seed.mjs` NO sirve: genera precios inventados con historial falso.

## 2026-08-01 (infra local)

- **Docker Desktop 4.84 / engine 29.6.2** instalado via winget; CLI en PATH de usuario.
- **Poetry 2.4.1 + uv 0.12.1** en user Scripts PATH.
- Stack local: `docker compose -f infra/docker/docker-compose.yml up -d postgres redis` (healthy).
- `DATABASE_URL` canónico: `localhost:5432` (antes 5433 en root/.env y price-service).
- Scripts: `scripts/dev-env.ps1`, `scripts/setup-local.ps1 -SyncPharmacies`.
- Prisma schema push OK (14 tablas). `sync-pharmacies`: 7 cadenas. 97 tests scraper OK.
- Dry-run Salcobrand en vivo: precios reales.


## 2026-08-01 (ISP open data gratis)

- Fuentes oficiales gratis (datos.gob.cl / ISP):
  - bioequiv: 1555 registros (principio activo + marca + F-xxxx)
  - venta_directa: 2428 OTC
  - proteccion_datos: 66
  - + isp_sample alias → **4097 medications**, **8194 medication_names**
- CLI: `ingest list-sources` / `fetch-official` / `import-official --also-sample`
- Cache: `workers/ingestion/data/official/` (TTL 7d)
- Tests importer: 7 passed
- Relink full catalog en curso (41k pharmacy_products × 8k names — lento; matcher estricto)


