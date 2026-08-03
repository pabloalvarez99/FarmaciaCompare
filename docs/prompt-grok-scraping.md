# Prompt para Grok — Scraping de precios de medicamentos en Chile

Copia todo lo que está bajo la línea. El reconocimiento ya está hecho y
verificado en vivo (2026-08-01): no dejes que Grok lo repita ni lo adivine.

---

## Contexto

Estoy construyendo **FarmaciaCompare**, una web pública para que cualquier
persona en Chile compare el precio del mismo medicamento entre todas las
farmacias online del país. El objetivo es simple y concreto: alguien busca
"paracetamol 500 mg", ve todas las farmacias que lo venden ordenadas por precio,
y sabe dónde comprarlo más barato hoy.

Stack existente: monorepo Turborepo + pnpm. `apps/web` en Next.js 14 (App
Router, Vercel), `services/api-gateway` en NestJS + Prisma sobre PostgreSQL,
`workers/scraper` en Python 3.12 (httpx, SQLAlchemy async, APScheduler, pytest).
Los scrapers escriben en las tablas `pharmacy_products` y `prices`.

## Lo que ya está resuelto — no lo vuelvas a investigar

Hice el reconocimiento de plataforma de cada sitio y verifiqué cada endpoint con
requests reales. Estos son los hechos, no hipótesis:

| Cadena | Plataforma real | Endpoint que funciona hoy | Estado |
|---|---|---|---|
| Cruz Verde | Salesforce Commerce Cloud | `GET https://beta.cruzverde.cl/s/Chile/dw/shop/v19_1/product_search?q=<term>&expand=prices,availability,images&client_id=c19ce24d-1677-4754-b9f7-c193997c5a92` y `/products/<id>` | 200 |
| Salcobrand | Spree + Algolia | `POST https://GM3RP06HJG-dsn.algolia.net/1/indexes/sb_variant_production/query`, headers `X-Algolia-API-Key: 0259fe250b3be4b1326eb85e47aa7d81`, `X-Algolia-Application-Id: GM3RP06HJG`, **`Referer: https://salcobrand.cl/`** (la key está restringida por referer; sin él responde 403) | 200 |
| Farmacias Ahumada | Salesforce Commerce Cloud | sitemap `https://www.farmaciasahumada.cl/sitemap_index.xml` + bloque JSON-LD `schema.org/Product` en cada ficha (`offers.price`, `offers.availability`) | 200 |
| Dr. Simi | VTEX, cuenta `farmaciasdeldrsimicl` | `GET https://www.drsimi.cl/api/catalog_system/pub/products/search?_from=0&_to=49` (responde 206) | 206 |
| Farmex | Shopify | `GET https://farmex.cl/products.json?limit=250&page=N` | 200 |
| Farmacias Curie | Shopify | `GET https://www.farmaciascurie.cl/products.json?limit=250&page=N` | 200 |
| Farmaloop | Next.js | homepage → `buildId`, luego `GET https://www.farmaloop.cl/_next/data/<buildId>/products/<slug>.json`; slugs desde `https://www.farmaloop.cl/sitemap.xml` | 200 |

Detalles que costaron trabajo descubrir y que debes respetar:

- **Cruz Verde, Salcobrand y Ahumada ya no son VTEX.** Sus hosts
  `<cuenta>.vtexcommercestable.com.br` devuelven **404**. Cualquier tutorial que
  diga lo contrario está desactualizado.
- `api.cruzverde.cl` responde `{"error":"La sesión ha expirado","errorCode":"INVALID_SESSION"}`
  sin sesión. No lo uses: la vía limpia es OCAPI con el `client_id` de arriba.
- **`robots.txt` de Cruz Verde y Ahumada prohíbe cualquier URL que lleve `start`**,
  lo que descarta paginar `product_search` y `Search-UpdateGrid`. Ambos publican
  sitemap explícitamente: esa es la vía permitida para recorrer el catálogo.
- **Algolia corta en 1000 resultados alcanzables por query.** Salcobrand tiene
  ~13.000 productos, así que hay que particionar por la faceta `taxonomies` y
  subdividir por letra las facetas con más de 1000 hits (`Belleza` tiene 3631).
  La faceta se lee con `{"params":"query=&hitsPerPage=0&facets=[\"taxonomies\"]&maxValuesPerFacet=100"}`;
  el endpoint `/facets/taxonomies/query` responde 400 porque el atributo no es
  searchable.
- **El `buildId` de Farmaloop rota en cada deploy.** Léelo del HTML de la
  portada, nunca lo hardcodees.
- **Cuidado con los precios decimales.** Algolia devuelve el descuento como
  `"1004.0"` y Shopify el precio como `"7439"`. Un parser chileno que trata el
  punto como separador de miles convierte `1004.0` en `10040`. Necesitas dos
  parsers distintos: uno para texto de página (`$12.990` → `12990`) y otro para
  números de API (`float` → `int`).
- **Farmex publica variantes con precio `$0`** (listados Cenabast / seguro). No
  son ofertas reales y arruinan el ranking de "más barato": descártalas.
- `farmaciasdoctorsimi.cl` es la misma cadena que `drsimi.cl` con otro frontend.
  Scrapear ambos duplica productos.

## Lo que quiero de ti

Piensa a fondo antes de escribir código. Quiero un diseño de nivel producción,
no un script que funcione una vez. Entrega, en este orden:

1. **Plan de arquitectura** de la capa de ingesta: cómo se recorre cada fuente,
   cada cuánto, qué pasa cuando una cambia de plataforma sin avisar, y cómo el
   sistema se entera de que un scraper se rompió en vez de escribir datos vacíos
   en silencio.

2. **El problema difícil de verdad: la identidad del producto.** Comparar
   precios exige saber que "Kitadol (B) Paracetamol 500mg 24 Comprimidos" de
   Salcobrand y "Xumadol Paracetamol 1000 mg 20 Comprimidos" de Cruz Verde son
   dos productos distintos, mientras que el mismo paracetamol vendido en dos
   cadenas es uno solo. Los nombres no coinciden, las presentaciones se escriben
   de diez formas y solo algunas fuentes traen EAN. Diseña el matching: qué
   señales usar y en qué orden de confianza, cómo normalizar dosis y
   presentación, dónde poner el umbral, y qué hacer con lo que queda en la zona
   gris. Un match equivocado le muestra al usuario un precio que no corresponde
   a lo que va a comprar: es el peor error posible en este producto.

3. **Modelo de datos de precios** que soporte historial (queremos gráficos de
   evolución y alertas de baja de precio), sin que la tabla crezca sin control
   cuando 7 cadenas × decenas de miles de productos se escriben varias veces al
   día.

4. **Detección de anomalías**: cómo distinguir una oferta real de un error de
   parseo o de un cambio de markup del sitio. Si un medicamento pasa de $12.990
   a $129, el sistema tiene que sospechar antes de publicarlo.

5. **Código Python 3.12** para los conectores, con `async`/`await`, tipado, y
   tests con pytest que no dependan de la red (fixtures con payloads reales).
   Una clase base común y un conector por plataforma, no siete scripts copiados.

6. **Ética y aspectos legales**: qué es defendible y qué no. Los precios son
   hechos públicos y compararlos beneficia al consumidor, pero quiero rate
   limiting real, respeto a `robots.txt`, User-Agent identificable, y cero carga
   innecesaria sobre los sitios. Dime explícitamente dónde está el límite y qué
   no deberíamos hacer aunque técnicamente se pueda.

## Cómo quiero que respondas

- Español. Términos técnicos, nombres de API y mensajes de error en su idioma
  original.
- Decisiones con su razón. Si descartas una alternativa, dime por qué en una
  línea; no quiero un catálogo de opciones.
- Si algo de lo que te di arriba te parece equivocado, dilo y justifícalo. Lo
  verifiqué, pero los sitios cambian.
- Nada de código de relleno ni `TODO: implementar después`.
