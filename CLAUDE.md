# CLAUDE.md — reglas del proyecto

Este archivo se lee **antes que nada**. Define qué estamos construyendo, con qué
estándar, y las reglas que no se negocian.

---

## 1. Qué estamos construyendo

**Un comparador de precios de salud y bienestar para Chile, con la calidad de
[solotodo.cl](https://www.solotodo.cl).**

SoloTodo es el estándar porque resolvió lo difícil: no es "buscador que revisa
varias tiendas", es **"este producto exacto, en todas partes donde se vende"**.
Un LG OLED de 55" es una entidad, y todas las tiendas que lo venden cuelgan de
ella con su precio, su stock y su historial. Eso exige tres cosas que casi nadie
hace bien:

1. **Resolución de identidad de producto.** Saber que dos listados de tiendas
   distintas son el mismo producto físico — y saber cuándo *no* lo son.
2. **Atributos estructurados por categoría.** Un televisor tiene pulgadas y
   panel; un medicamento tiene principio activo, concentración y forma
   farmacéutica; un suplemento tiene ingrediente, porción y unidades. Filtrar
   por atributo, no por texto.
3. **Historial y disponibilidad.** El precio de hoy y el de la semana pasada, y
   si realmente se puede comprar.

Ese es el nivel al que apuntamos. Todo lo demás es consecuencia.

### Para quién y por qué importa

Datos reales de nuestra base: el mismo Ozempic 4mg/3mL vale **$209.990** en una
cadena y **$413.800** en otra. La misma Abiraterona tiene **$290.000** de
diferencia. Para alguien que paga de su bolsillo un tratamiento crónico, eso es
el mercado del mes.

No estamos haciendo un directorio. Estamos haciendo la herramienta con la que
alguien decide dónde gastar plata que le duele.

---

## 2. Alcance

Todo lo que se vende en el canal farmacia y bienestar en Chile:

| Categoría | Ejemplos | Estado |
|---|---|---|
| **Medicamentos** | con y sin receta, bioequivalentes, magistrales | núcleo, en producción |
| **Suplementos** | vitaminas, minerales, proteínas, deportivos | datos ya scrapeados, sin modelar |
| **Dermocosmética** | protector solar, serums, tratamiento facial | datos ya scrapeados, sin modelar |
| **Cosmética** | maquillaje, cuidado capilar | datos ya scrapeados, sin modelar |
| **Higiene y cuidado personal** | pañales, desodorantes, cuidado íntimo, bucal | datos ya scrapeados, sin modelar |
| **Cuidado del bebé** | fórmula, mamaderas, higiene infantil | parcial |
| **Dispositivos y accesorios** | presión, glucosa, mascarillas, órtesis | parcial |

**Perfumería: fuera de alcance por ahora.** Es otra categoría de compra, con
otros retailers y otra lógica de identidad (concentración, tamaño, batch). Si
entra alguna vez, entra como decisión explícita, no por arrastre.

### Consecuencia importante del alcance ampliado

Durante el desarrollo inicial tratamos todo lo no-medicamento como **ruido a
filtrar**: desodorantes de Farmex, los serums de The Ordinary en Curie, los
8.880 productos de belleza de Preunic. Con el alcance nuevo eso **ya no es
ruido, es catálogo**.

`attributes.isMedicine` deja de ser un filtro de exclusión y pasa a ser **una
dimensión de categoría**. El código que hoy descarta por `isMedicine=false` hay
que revisarlo caso por caso: en el matcher sigue siendo un gate de seguridad
válido, en la UI es una faceta.

---

## 3. Las reglas que no se rompen

### 3.1 Ningún precio inventado llega a producción

Nunca. Ni de ejemplo, ni de placeholder, ni "mientras tanto". Este sitio ya tuvo
datos de demo y costó sacarlos de **seis** lugares distintos, incluido un
`sitemap.xml` que le entregaba a Google 40 URLs de precios falsos para indexar.

`scripts/seed.mjs` genera precios inventados con 30 días de historial falso.
**Nunca correrlo contra producción.**

Si un dato no está, la pantalla dice que no está. Un vacío honesto es
infinitamente mejor que un número inventado.

### 3.2 Un vínculo equivocado es peor que ningún vínculo

Si dos productos distintos quedan unidos bajo la misma entidad, la web le
muestra a alguien el precio de un producto que no es el suyo. En salud eso no es
un bug cosmético.

Casos reales que ya bloqueamos, todos con evidencia en
`docs/coordinacion-agentes.md`:

- `Blissel Estriol 5 mg` enlazado a `estriol 0.5 mg` — error de potencia **10×**
- Tres insulinas distintas (lispro, degludec, NPH) colapsadas en
  `insulina 100 ui ml` — farmacológicamente distintas, mismo alias
- Nistatina suspensión oral enlazada al óvulo vaginal — otra vía
- Leche de fórmula enlazada a guantes de nitrilo, porque ambos decían "polvo"
- Dos soluciones oftálmicas al 0,1% que son fármacos diferentes

**El `relink` en modo escritura no se corre sin revisión humana de la muestra.**
`--dry-run` siempre primero.

### 3.3 Respetar robots.txt, siempre

Si un sitio no se puede scrapear sin violarlo, se para y se dice. No se rodea.
Cruz Verde y Ahumada prohíben cualquier URL con `start`, y por eso usamos sus
sitemaps — que ellos mismos publican.

User-Agent identificable (`FarmaciaCompareBot/1.0` con URL de contacto),
concurrencia acotada, delay entre lotes. Estamos leyendo el negocio de otro: se
hace con respeto o no se hace.

### 3.4 Verificar antes de afirmar

Un build que compila no es un servicio que arranca. Un `exit 0` no prueba que el
efecto ocurrió — en este proyecto un script reportó éxito sin hacer nada porque
se escribió en `/tmp` y el Python de Windows nunca encontró el archivo.

Antes de decir "listo": correr el comando, mirar la salida, mostrarla.

### 3.5 Sin secretos en git ni en el vault

Credenciales en `.env.production` (gitignored). Nunca imprimirlas, nunca
commitearlas, nunca escribirlas en `D:\obsidian-mind`. Se archiva el **puntero**,
jamás el valor.

---

## 4. El problema central: identidad de producto

Es el 80% de la dificultad y el 100% de lo que separa este proyecto de un
buscador cualquiera. Vale la pena entenderlo antes de tocar nada.

**El modelo:** una entidad canónica (`medications` hoy) y N listados de tienda
(`pharmacy_products`) que apuntan a ella. Comparar precios = agrupar listados
bajo la misma entidad.

**Las señales, en orden de confianza:**

1. **EAN / código de barras compartido** — identidad exacta, sin heurística. Es
   como se vincularon los ~31.000 vínculos seguros que hay hoy. Pero solo 6 de
   10 cadenas lo publican: Cruz Verde, Salcobrand y Dr. Simi **no**.
2. **Atributos estructurados de la tienda** — Cruz Verde expone
   `c_activeIngredient`, `c_dose`, `c_format`; Salcobrand da el breadcrumb con
   el principio activo y `options_text` con la presentación. Se guardan en
   `pharmacy_products.attributes` (jsonb).
3. **Nombre normalizado + reglas duras** — último recurso, con gates
   fail-closed. Nunca por similitud sola.

**Los gates que existen en `matcher.py` y por qué:**

- **Clave ambigua nunca auto-vincula.** Si un `normalized_name` lo comparten
  varios medicamentos, elegir uno es un sorteo. Hay 3.328 claves así.
- **Dosis y tamaño de envase deben coincidir** si ambos lados los declaran.
  120 mL no es 300 mL.
- **Vía de administración no es identidad.** `oftalmica`, `nasal`, `pomada`
  describen *cómo* se administra, nunca *cuál* es el fármaco.
- **Un combo no colapsa sobre un componente.** `Sacubitrilo / Valsartán` no es
  valsartán.

**Para las categorías nuevas la llave cambia.** Un cosmético no tiene principio
activo: se identifica por marca + línea + formato + volumen. Un suplemento por
marca + ingrediente + dosis por porción + cantidad. **No reusar el matcher de
medicamentos sin adaptarlo** — sus reglas asumen semántica farmacológica.

---

## 5. Estándar de calidad de la interfaz

El referente es SoloTodo: **denso, rápido, legible**. Mucha información sin
sensación de ruido.

- **El ahorro es la historia.** Lo más valioso en pantalla es "esto cuesta X acá
  y Y allá". El diseño gira en torno a esa comparación.
- **La farmacia siempre visible junto al precio.** Un precio sin atribución no
  sirve para decidir.
- **Móvil primero.** La mayoría entra desde el teléfono con datos móviles.
- **Accesible de verdad.** Contraste real, foco visible, `alt`, marcado
  semántico. Parte del público son personas mayores administrando recetas
  crónicas.
- **Español de Chile.** Precios en CLP con punto de miles (`$12.990`).
- Nada de `next/image` para fotos de producto: vienen de diez CDNs distintos.

---

## 6. Arquitectura

**Monorepo** Turborepo + pnpm 9, Node ≥20.

| Pieza | Qué es | Estado |
|---|---|---|
| `apps/web` | Next.js 14 App Router, Tailwind. Deploy Vercel | activo |
| `services/api-gateway` | NestJS + Prisma. Deploy Cloud Run | activo |
| `workers/scraper` | Python. Conectores por plataforma, matcher, anomalías | activo |
| `workers/ingestion` | Python. Importadores de catálogo (ISP, tu-farmacia) | activo |
| `packages/database` | Prisma schema — fuente de verdad del modelo | activo |
| `apps/admin`, `apps/dashboard` | paneles internos | baja prioridad |
| `mobile/`, `services/price-service` | pausados | no expandir sin pedido |

**Infraestructura:** GCP `farmacia-compare-prod`, región `southamerica-west1`.
Cloud SQL POSTGRES_15 (`db-f1-micro` — **máximo 2 escritores concurrentes**),
Cloud Run para la API y para el job de scraping, Cloud Scheduler para la
cadencia. Runbook completo en `docs/infra-gcloud.md`.

`registry.py` es la **fuente única** de cadenas: agregar una es una entrada ahí,
y el CLI, el scheduler y el seeding la toman solos.

---

## 7. Cómo trabajar

**Medir antes de opinar.** Este proyecto tuvo varios diagnósticos equivocados
que se corrigieron solo al contar filas. "El matcher es muy estricto" resultó
ser "el catálogo no tiene esos productos" — 504 de 600 sin candidato.

**Root cause sobre parche.** Leer el error exacto, encontrar la causa, arreglar
una vez. Sin `try/except` silenciador ni `as any` evasivo.

**Subagentes con fronteras estrictas.** Dos agentes editando el mismo archivo se
pisan. Cada uno con archivos propios y lista de prohibidos. Nadie toca
`registry.py` salvo el dueño: si un agente agrega una cadena, reporta la línea y
la wirea el hilo principal. Los agentes de tests escriben solo en `tests/`; si
encuentran un bug lo reportan, no lo arreglan.

**Exigir evidencia, no afirmaciones.** "Mostrame el conteo antes y después, la
fila de `scraping_jobs` con `status='success'`, el `curl -I` devolviendo 200."

**Documentar.** `bitacora.md` para el porqué de cada cambio significativo, y el
second brain (`D:\obsidian-mind`) según la Regla 0 del capitán.

### Comandos

```bash
# Tests
cd workers/scraper && .venv/Scripts/python.exe -m pytest tests -q --ignore=tests/test_dr_simi.py
cd workers/ingestion && ../scraper/.venv/Scripts/python.exe -m pytest tests -q

# Scrapers contra producción
cd workers/scraper
export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production | cut -d= -f2-)
export PYTHONIOENCODING=utf-8        # sin esto, imprimir '→' revienta en consola Windows
python -m src.cli scrape <cadena>
python -m src.cli relink --dry-run --only-medicine --chain <cadena> --limit 300

# Deploys (idempotentes)
./scripts/deploy-api-gateway.sh [TAG]
./scripts/deploy-scraper-job.sh [TAG]
```

---

## 8. Estado actual

**En producción:**
- Web: https://farmacia-compare-web.vercel.app
- API: https://api-gateway-446315435132.southamerica-west1.run.app

| Métrica | Valor |
|---|---|
| Productos scrapeados | **77.748** en 10 cadenas |
| Vinculados a catálogo | 36.469 (47%) |
| Con categoría | 54.608 (70%) |
| **Tasa de error de vínculos** | **0%** (auditada) |
| Catálogo de medicamentos | 42.042 (ISP + tu-farmacia) |
| Grupos comparables por EAN | 3.815 |
| **Grupos comparables por catálogo** | **4.975** |
| Farmacias físicas | 174 (Coquimbo) |
| Tests | 465 scraper + 105 gateway + 344 ingestion |
| Con imagen | 99,5% — *no es prioridad, ver §9* |

**Cadenas:** Farmex, Salcobrand, Cruz Verde, Preunic, Ahumada, MercadoFarma,
Farmaloop, Curie, Knop, Dr. Simi.

---

## 9. La prioridad: producto y precio, no la foto

**Lo único que hace valioso a este sitio es saber qué producto es y cuánto
cuesta en cada cadena.** Todo el esfuerzo va ahí:

1. **Cobertura** — más productos scrapeados, más cadenas, catálogo más completo
2. **Precio fresco y correcto** — que el número que mostramos sea el que cobra
   la farmacia hoy
3. **Identidad** — que dos listados del mismo producto se encuentren, y que dos
   productos distintos **nunca** se confundan

**Las imágenes no son prioridad.** Están al 99,5% porque las cadenas las
publican junto al precio y salen gratis en el mismo scrape. Nadie debe invertir
tiempo en mejorarlas, buscarlas en otra fuente, ni normalizarlas: una foto
faltante cuesta estética, un precio equivocado cuesta plata de alguien que está
comprando un remedio.

Si una imagen falta, se muestra el producto sin ella. No se bloquea, no se
reintenta, no se busca en otro lado.

**Corolario para decidir en qué trabajar:** ante dos tareas, gana la que suma
productos, precios o vínculos correctos. Lo demás espera.

---

## 9. Hacia el nivel SoloTodo — lo que falta

En orden de valor:

1. **Cerrar la resolución de identidad.** 40% vinculado no alcanza. Depende de
   deduplicar el catálogo (hay 25 filas para "clobetasol 0.05%") y de enriquecer
   con composición completa desde la ficha de detalle del ISP.
2. **Modelar las categorías nuevas.** Esquema de atributos por categoría y su
   propia lógica de identidad. Es lo que convierte 8.880 productos de Preunic de
   ruido en catálogo.
3. **Filtros por atributo.** La marca de SoloTodo. Requiere el punto 2.
4. **Historial de precios visible.** Los datos están en `prices`; falta
   graficarlos y falta política de retención antes de que la tabla explote.
5. **Alertas de precio.** Hoy la pantalla dice honestamente que no existen.
6. **Cobertura nacional del directorio físico.** Hoy solo Coquimbo.

---

## 10. Trampas ya pagadas — no redescubrirlas

Están documentadas con detalle en `docs/infra-gcloud.md`,
`docs/coordinacion-agentes.md` y `docs/prompt-grok-scraping.md`. Las que más
cuestan si se olvidan:

- **Dos parsers de precio distintos.** `parse_price` lee "." como separador de
  miles (`$12.990` → 12990); `parse_machine_price` lo lee como decimal
  (`"1004.0"` → 1004). Confundirlos infla precios **×10 en silencio**.
- **Cruz Verde, Salcobrand y Ahumada ya no son VTEX.** Sus hosts
  `<cuenta>.vtexcommercestable.com.br` dan 404.
- **Algolia solo deja alcanzar 1000 hits por query** y su key está restringida
  por Referer.
- **Un precio `$0` no es una oferta** — son listados placeholder.
- **`gcloud builds submit` ignora `.dockerignore`** y usa `.gcloudignore`.
- **Con SQLAlchemy `text()`, un `CAST(:param AS jsonb)` sin la clave en el dict**
  lanza `InvalidRequestError` y rompe **todas** las escrituras en silencio.
- **`/tmp` de Git Bash y el de Python-Windows son lugares distintos.**
- **`tail` bufferea**: un background con `| tail -N` no muestra nada hasta
  terminar. Verificar contra la base, no contra el log.
