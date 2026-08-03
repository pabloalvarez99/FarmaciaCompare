# Plan maestro — de comparador de farmacia a SoloTodo de salud

Documento de arquitectura y hoja de ruta. Leé `CLAUDE.md` primero: ahí están las
reglas que no se negocian. Acá está **cómo** llegar.

Última actualización: 2026-08-02.

---

## 1. El problema arquitectónico de fondo

Hoy el modelo canónico es `medications`. Alcanzaba cuando el alcance eran
medicamentos. Con suplementos, dermocosmética, cosmética e higiene adentro, hay
que generalizar — y el modo de hacerlo determina todo lo demás.

### El modelo de SoloTodo, traducido

| SoloTodo | Nosotros hoy | Qué es |
|---|---|---|
| `Category` | *no existe* | Televisor, Notebook… → Medicamento, Suplemento, Cosmética… |
| `Product` | `medications` | La entidad canónica. Un producto del mundo real. |
| `Entity` | `pharmacy_products` | Un listado de una tienda, apuntando a un `Product`. |
| `EntityHistory` | `prices` | Precio y stock en el tiempo. |

Los specs de SoloTodo son **por categoría**: un televisor tiene pulgadas y panel,
un notebook tiene RAM y CPU. Filtrar por atributo, no por texto, es lo que hace
que el sitio se sienta de otra liga.

### La decisión: generalizar `medications`, no crear una tabla paralela

**Recomendación: renombrar la tabla a `products` y `medication_id` a
`product_id`.** Postgres arrastra las FK solo con `ALTER TABLE RENAME`; los
~31.000 vínculos existentes sobreviven intactos. El costo es churn de código, no
de datos.

El motivo de hacerlo ahora y no después: `medications` conteniendo shampoo es una
mentira que confunde a todo el que llegue. Con 42.042 filas la migración es
trivial; con 500.000 y seis meses más de código encima, ya no.

**Hacerlo como tarea dedicada de un solo agente, nunca mezclado con features.**

```prisma
model Product {
  // …lo que ya existe…
  categoryId   String   @map("category_id")
  // Specs propios de la categoría. Medicamento usa las columnas dedicadas que ya
  // existen (activeIngredient, dosage, pharmaceuticalForm); el resto de las
  // categorías vive acá para no llenar la tabla de columnas nulas.
  specs        Json?
  @@map("products")
}
```

Los medicamentos conservan sus columnas dedicadas porque son la categoría más
grande y sus atributos ya están indexados y probados. Es un híbrido deliberado,
no una inconsistencia.

---

## 2. Categorías y su llave de identidad

**Esta tabla es el corazón del proyecto.** La llave de identidad es el conjunto
mínimo de atributos que determina unívocamente un producto. Dos listados con la
misma llave son el mismo producto; con llave distinta, no lo son.

| Categoría | Llave de identidad | Fuente de catálogo |
|---|---|---|
| **Medicamento** | principio activo + concentración + forma + unidades del envase | Registro ISP (arriba-abajo) |
| **Suplemento** | marca + ingrediente principal + dosis por porción + unidades | ISP parcial + derivado |
| **Dermocosmética** | marca + línea + variante + volumen | Derivado (abajo-arriba) |
| **Cosmética** | marca + línea + tono/variante + volumen | Derivado |
| **Higiene** | marca + línea + formato + cantidad | Derivado |
| **Bebé (fórmula)** | marca + etapa + formato + peso | Derivado |
| **Dispositivo** | marca + modelo | Derivado |

**El EAN gana siempre que exista.** Es identidad exacta, sin heurística. Las
llaves de arriba son el plan B para las cadenas que no publican código de barras
(Cruz Verde, Salcobrand, Dr. Simi, Preunic).

### Dos formas de construir catálogo, y cuándo usar cada una

**Arriba-abajo (registro oficial).** Existe para medicamentos: el registro
sanitario del ISP, 46.434 productos. Se importa y los listados se emparejan
contra él. Ya está hecho.

**Abajo-arriba (derivado de los listados).** Para cosmética, higiene y la mayoría
de suplementos **no hay registro oficial**. El catálogo hay que *derivarlo*:

1. Agrupar listados por **EAN exacto** → cada grupo es un producto canónico
   candidato, con evidencia fuerte.
2. Los listados sin EAN se agrupan por **llave normalizada de la categoría**.
3. **Promover a producto canónico solo los grupos con evidencia suficiente**:
   visto en ≥2 cadenas, o con EAN, o con marca reconocida.
4. Lo que no alcanza el umbral queda como listado suelto, visible en búsqueda
   pero sin agrupar. **Nunca inventar un producto canónico para forzar una
   comparación.**

Seguro por construcción: un grupo solo nace cuando la evidencia lo sostiene.

---

## 3. Clasificación: de qué categoría es cada producto

Las cadenas ya nos lo dicen, cada una a su manera, y está todo guardado en
`pharmacy_products.attributes`:

| Cadena | Campo | Ejemplo |
|---|---|---|
| Cruz Verde | `c_isMedProduct`, `primary_category_id` | `medicamentos` |
| Salcobrand | `taxonomies`, `product_categories.lvl0..3` | `Medicamentos > Dolor > Analgésico > Paracetamol` |
| Farmaloop | `productCategory`, `productSubCategory` | `Medicamentos` / `Control de Peso` |
| Shopify (Farmex, Curie) | `product_type` | `Dermocosmetica` |
| MercadoFarma | `product_type` | `medicamento` / `sin medicamento` |
| Knop | `product_type` + tags | `Medicamentos` |
| Ahumada | breadcrumb del detalle | `Medicamentos > …` |

**Falta una tabla de mapeo** categoría-de-cadena → categoría canónica. Trabajo
aburrido y de altísimo valor: sin eso, los 8.880 productos de Preunic y los 4.604
de Curie siguen siendo ruido en vez de catálogo.

Trampa ya pagada: en MercadoFarma el `product_type` es `medicamento` /
**`sin medicamento`**, y como el negativo contiene al positivo, un match ingenuo
por substring clasificó mal 2.162 de 4.970 productos. **Probar el negativo antes
que el positivo.**

---

## 4. El matcher tiene que ser por categoría

`DrugMatcher` asume semántica farmacológica: principio activo, concentración, vía
de administración, bioequivalencia. **Aplicarlo a cosmética produce falsos
positivos de otra naturaleza** — dos serums de la misma marca y volumen con
activos distintos no son el mismo producto.

```
ProductMatcher            (base: EAN exacto, gates comunes, zona gris)
├── MedicationMatcher     (el actual: dosis, forma, vía, combos)
├── SupplementMatcher     (ingrediente + dosis por porción + unidades)
├── CosmeticMatcher       (marca + línea + volumen; el activo NO es la llave)
└── HygieneMatcher        (marca + formato + cantidad)
```

**Gates que ya existen y hay que preservar en la base** — cada uno nació de un
falso positivo real en producción:

- **Clave ambigua nunca auto-vincula.** Si varios productos canónicos comparten
  el nombre normalizado, elegir uno es un sorteo. Hay 3.328 claves así.
- **Dosis y tamaño de envase deben coincidir** si ambos lados los declaran.
- **La vía de administración no es identidad** (`oftalmica`, `nasal`, `pomada`).
- **Un combo no colapsa sobre un componente.**

---

## 5. Hoja de ruta por fases

Cada fase tiene criterio de salida medible. **No se avanza con la anterior a
medias** — este proyecto ya pagó el costo de diagnósticos apurados.

### Fase 0 — Cerrar la deuda abierta

- [ ] Deduplicar el catálogo (25 filas para "clobetasol 0.05%" → 1)
- [ ] Auditoría adversarial de los ~31.000 vínculos ya escritos
- [ ] `relink` en escritura, **solo** con la auditoría aprobada
- [ ] Rotar y borrar las credenciales de prescribo del vault (`fm audit` verde)
- [ ] Retención de `prices` antes de que la tabla crezca sin control

**Salida:** `fm audit` verde, tasa de error de vínculos medida y publicada.

### Fase 1 — Generalizar el modelo

- [ ] Tabla `categories` con las 7 categorías
- [ ] `medications` → `products`, `medication_id` → `product_id`
- [ ] Columnas `category_id` y `specs` (jsonb)
- [ ] Tabla de mapeo categoría-de-cadena → canónica
- [ ] Clasificar los 77.021 productos existentes

**Salida:** todo producto scrapeado tiene categoría; conteo por categoría
publicado.

### Fase 2 — Catálogo abajo-arriba

- [ ] Agrupador por EAN para categorías sin registro
- [ ] Agrupador por llave normalizada, con umbral de evidencia
- [ ] Promoción de clusters a `products` canónicos
- [ ] Matchers por categoría

**Salida:** vinculación ≥70% en cada categoría, con muestra auditada.

### Fase 3 — La superficie SoloTodo

- [ ] Filtros por atributo, por categoría
- [ ] Ficha de producto: todas las tiendas, precio, stock, historial
- [ ] Gráfico de historial de precios
- [ ] Búsqueda con facetas

**Salida:** se puede filtrar "protector solar FPS 50+ de 200 mL" y ver todas las
tiendas que lo venden.

### Fase 4 — Retención y confianza

- [ ] Rollup diario de precios + política de retención
- [ ] Alertas de precio
- [ ] Directorio físico nacional (hoy solo Coquimbo, 174 farmacias)
- [ ] Página de transparencia: cuándo se actualizó cada cadena, cobertura real

---

## 6. Cómo hacer cada cosa

### Agregar una cadena nueva

1. **Reconocimiento antes que código.** Probar la plataforma, no adivinarla:
   ```bash
   curl -s -A "Mozilla/5.0" -L https://sitio.cl/ -o /tmp/s.html
   grep -o -i -E "vtex|shopify|Demandware|__NEXT_DATA__|algolia|woocommerce|jumpseller" /tmp/s.html | sort | uniq -c
   curl -s -L https://sitio.cl/robots.txt
   ```
   Huellas y qué implica cada una:
   - **Shopify** → `/products.json?limit=250&page=N`, catálogo completo sin auth
   - **VTEX** → `<dominio>/api/catalog_system/pub/products/search?_from=0&_to=49` (206)
   - **SFCC** → OCAPI con `client_id` del bundle, o sitemap + JSON-LD
   - **Next.js** → `_next/data/<buildId>/…json`, buildId del HTML de portada
   - **Algolia** → key restringida por Referer en el bundle JS
   - **WooCommerce** → `/wp-json/wc/store/products?per_page=100`
   - **Bolder** → `/products.json` con envelope propio (`total_pages`)
   - **Empathy.co** → API de browse propia
2. **Respetar `robots.txt`.** Si prohíbe, usar el sitemap que publica. Si no hay
   vía permitida, parar y decirlo.
3. Conector con la forma de los existentes: `@dataclass` de config, dict
   `CONFIGS`, subclase de `BaseScraper` con `parse_product`,
   `extract_attributes` y `scrape_products`.
4. Tests con fixtures capturadas en el reconocimiento, sin red.
5. **Reportar la entrada de `registry.py`, no editarla** si sos un subagente.

### Importar un catálogo nuevo

Seguir `workers/ingestion/src/isp_registry_importer.py`. Puntos críticos:

- **Deduplicar antes de insertar**, por registro sanitario y nombre normalizado.
  Un import que duplica rompe los vínculos ya escritos.
- **Reusar** `normalize_name`, `extract_dosage`, `extract_form`,
  `split_ingredients` de `tufarmacia_importer` — importarlas, no copiarlas.
  Tienen bugs ya corregidos que no querés reintroducir.
- Crear **dos** nombres por producto: el comercial y un alias genérico
  (`principio activo + dosis`). Ese alias es lo que empareja marca con genérico.
- `--dry-run` primero, siempre, y mostrar los números.

### Cambiar la normalización

Si tocás `normalize_name` o las funciones de extracción, las claves ya escritas
quedan viejas. **Correr `recompute_catalog.py`**, que recalcula en sitio —
re-importar duplicaría filas y dejaría huérfanos los vínculos.

Ese módulo ya resuelve lo difícil: escribe solo las filas que cambian, usa
`executemany` en lotes, y pre-resuelve las colisiones del índice único
`(medication_id, normalized_name)`.

### Verificar que un vínculo es correcto

```bash
cd workers/scraper
export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production | cut -d= -f2-)
export PYTHONIOENCODING=utf-8
python -m src.cli relink --dry-run --only-medicine --chain <cadena> --limit 300
```

Revisar **los LINK de menor confianza primero** — ahí viven los falsos
positivos. Un `linked` más alto solo es bueno si la muestra aguanta la mirada.

### Desplegar

```bash
./scripts/deploy-api-gateway.sh [TAG]
./scripts/deploy-scraper-job.sh [TAG]
vercel --prod --yes
```

**Verificar la revisión desplegada, no el exit code.** Ya pasó que el build decía
SUCCESS y Cloud Run seguía sirviendo la revisión vieja:

```bash
gcloud run services describe api-gateway --project=farmacia-compare-prod \
  --region=southamerica-west1 --format="value(status.latestReadyRevisionName)"
```

Y el orden importa: desplegar la web antes que la API deja al sitio pidiendo
campos que la API todavía no devuelve.

---

## 7. Métricas de salud del producto

| Métrica | Hoy | Meta |
|---|---|---|
| Productos con precio | 77.021 | crece con las cadenas |
| Cobertura de imagen | 99,5% | ≥98% |
| **Vinculación a catálogo** | **40%** | **≥70% por categoría** |
| **Tasa de error de vínculos** | **desconocida** | **<0,5%, medida** |
| Grupos comparables | 3.817 | ≥15.000 |
| Frescura de precios | 6-12 h por cadena | <24 h siempre |
| Categorías modeladas | 1 de 7 | 7 de 7 |

La fila que más importa es la **tasa de error**: hoy no la sabemos, y no se puede
mejorar lo que no se mide. Primera tarea del auditor.

---

## 8. Lo que NO vamos a hacer

- **Elasticsearch.** Con 77k productos, Postgres con GIN alcanza y sobra.
- **Vender ni intermediar.** Comparamos precios; la compra ocurre en la farmacia.
- **Consejo médico.** Mostramos precios y datos del registro sanitario. No
  recomendamos tratamientos ni sugerimos equivalencias terapéuticas.
- **Perfumería.** Otra categoría de compra, otros retailers, otra lógica de
  identidad. Si entra, entra por decisión explícita.
- **Scrapear saltando `robots.txt`.** Nunca, por ninguna razón.
