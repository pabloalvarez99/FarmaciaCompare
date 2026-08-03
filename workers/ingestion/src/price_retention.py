"""Retention policy for the `prices` table.

    cd workers/ingestion
    export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production | cut -d= -f2-)
    export PYTHONIOENCODING=utf-8

    ../scraper/.venv/Scripts/python.exe -m src.price_retention            # dry-run
    ../scraper/.venv/Scripts/python.exe -m src.price_retention --apply    # borra

**Dry-run es el modo por defecto.** Borrar filas de `prices` es irreversible, así
que escribir exige `--apply` explícito. Es la única desviación deliberada
respecto de `recompute_catalog.py`, donde el flag va al revés porque ahí lo peor
que puede pasar es reescribir un `normalized_name`.

**Y es irreversible del todo, no solo por fila.** Verificado el 2026-08-03 en
revisión independiente:

    gcloud sql instances describe farmacia-compare-db --project farmacia-compare-prod
    settings.backupConfiguration.enabled              = False
    settings.backupConfiguration.pointInTimeRecovery  = (vacío / desactivado)

La instancia **no tiene backups automáticos ni PITR**. No hay a qué volver: ni
por fila, ni por tabla, ni por instancia. Antes de que alguien corra `--apply`
por primera vez, lo primero no es leer este docstring — es prender los backups.

---

## Por qué existe, y por qué hace tan poco

Re-medido en producción el **2026-08-03 02:07 UTC**, con los 9 schedulers
corriendo. Los números de la versión anterior de este docstring (77.411 filas,
2.710 de cambio, 163 de cuarentena) eran de 8 horas antes y quedaron cortos;
estos los reemplazan.

    prices                     79.227 filas, 29,7 MiB (11,3 heap + 18,3 índices)
    base completa              157 MiB de un disco de 10 GB con auto-crecimiento
    393 bytes por fila (incluyendo los tres índices)
    74.825 productos con alguna fila; 72.851 (92 %) tienen UNA sola

`prices` **no es la tabla más grande de la base**: `pharmacy_products` pesa
69 MB y `medication_names` 33 MB. Es la tercera.

**El dato que más condiciona todo lo demás: la tabla tiene 28 horas de vida.**
`min(recorded_at)` es 2026-08-01 21:23 UTC. No existe una sola fila con más de
7 días, así que la Regla 2 no tiene qué compactar y la Regla 1 no tiene qué
podar hasta el 2026-08-09 como muy pronto. Cualquier proyección hecha sobre esta
ventana es una extrapolación de un día, no una tendencia, y hay que leerla así.

Descompuestas por lo que realmente son:

    74.825  primera fila de su producto  (el backfill inicial, se paga una vez)
     4.402  filas de cambio              (la tasa de crecimiento de verdad)
       201  cuarentena, en 48 productos

`PriceWriter` solo inserta cuando el precio, el `original_price` o el
`stock_status` cambian. Sobre 312.808 ítems scrapeados el 2026-08-02 se
escribieron 4.142 filas de cambio: **1,3 %**. El resto sale por `unchanged`.

## Lo que las 4.142 filas/día realmente son

Desglosadas por cadena, últimas 24 h, solo filas de cambio:

    Dr. Simi     2.545      Curie        121
    Cruz Verde   1.056      Salcobrand    57
    Ahumada        205      Farmaloop     28
    Farmex         130      Preunic / MercadoFarma / Knop  0

**El 90 % de la tasa es una oscilación, no historial.** Corregido el 2026-08-03
en revisión independiente: la versión anterior decía que 1.249 productos de
Dr. Simi «alternan entre exactamente **dos** precios». Es falso —  solo 85
productos de Dr. Simi tienen exactamente dos precios distintos; 1.174 tienen
**tres**. La afirmación correcta, y la que importa, es más amplia: **1.253 de los
1.261 productos de Dr. Simi con historial vuelven a un precio que ya habían
tenido**. Contando igual en todas las cadenas son 2.054 productos y 6.115 de las
6.821 filas de cambio de la tabla — el 90 %, no el 61 %.

**Y la oscilación es INTERDIARIA, no intradía.** Este es el hallazgo que cambia
la conclusión sobre la Regla 2. Muestra real de un producto de Dr. Simi con
cuatro filas:

    1040  original=NULL   2026-08-01 21:45
     874  original=NULL   2026-08-02 07:40
    1040  original=NULL   2026-08-03 01:40
     780  original=1040   2026-08-03 07:40

Una fila por día, salvo el último. La Regla 2 agrupa por `(producto, día local)`
y **no puede tocar filas que no comparten día**: contra este patrón no borra
nada. Ver la nota de «Lo que la Regla 2 realmente recupera», más abajo.

Una muestra de Cruz Verde deja ver la otra variante, la que sí es intradía:

    2245  original_price=4490   ← precio con promoción
    4490  original_price=NULL   ← precio de lista
    2245  original_price=4490
    4490  original_price=NULL

El scraper a veces toma la promoción y a veces la lista, y `PriceWriter` hace lo
correcto: ve un precio distinto y escribe. En Dr. Simi el mismo patrón con razón
media 1,19 (1040 ↔ 874). De las 3.816 filas de cambio de precio de la tabla,
**3.758 (85 %) vienen de esos 1.551 productos**. El movimiento de precio real,
sin la oscilación, son ~50 filas/día.

Esto importa para la política de dos maneras. Primero: no hay que borrar nada
para ahorrar espacio que no falta, y menos cuando lo que se borraría es en su
mayoría ruido de un bug que sigue escribiendo — arreglar el conector baja la
pendiente 7× y es reversible, borrar filas no. Segundo, y más importante: **el
"bug de flapping" que la versión anterior de este archivo listaba como riesgo
hipotético ya está ocurriendo**, acotado a dos cadenas. No es teoría. Se reporta
en los conectores; acá no se toca.

## Proyección

Con la tasa medida tal cual está hoy — 4.142 filas/día × 393 B = **1,55 MiB/día**:

    horizonte      filas nuevas     prices        base       disco de 10 GB
    3 meses           +377.000      171 MiB      298 MiB     2,9 %
    6 meses           +754.000      313 MiB      440 MiB     4,3 %
    12 meses        +1.512.000      597 MiB      724 MiB     7,1 %

A esa tasa el disco aguanta del orden de **13 a 17 años**. Si además se arregla
la oscilación (~570 filas/día: 50 de precio + 370 de stock + 147 de cuarentena),
son 12 meses a 235 MiB de base — 2,3 %.

**El disco de 10 GB no se llena — crece.** Verificado el 2026-08-03:

    settings.storageAutoResize      = True
    settings.storageAutoResizeLimit = 0      ← 0 significa SIN techo
    settings.dataDiskType           = PD_SSD

Toda la tabla de arriba está bien pero mide la cosa equivocada. Cloud SQL sube
el disco solo cuando se acerca al límite, sin techo configurado, así que
«quedarse sin disco» no es un modo de falla de esta instancia. Y el disco de
Cloud SQL **no se puede achicar nunca**: una vez que creció, borrar filas no
devuelve un peso. El costo de dejar crecer `prices` es unos centavos de PD_SSD
al mes; el costo de borrar mal es historial que no vuelve. La asimetría va toda
para el mismo lado.

## Lo que la Regla 2 realmente recupera — medido, no estimado

Forzando la compactación sobre **todos** los días que existen en la tabla, no
solo los de más de 7 días:

    filas aceptadas                        81.846
    sobrevivientes tras compactar todo     81.608
    máximo borrable por la Regla 2            238   (0,29 %, ~91 KiB)

Y con `--compact-after-days 1` el planificador contra producción devolvió **70
filas**. La Regla 2 es un no-op estructural contra la forma real de estos datos:
la oscilación es interdiaria (arriba) y los días que sí tienen varias filas casi
siempre tienen tres o menos, que es exactamente lo que {mínimo, máximo, cierre}
conserva.

Consecuencia incómoda y hay que decirla: **la única regla segura no recupera
nada, y la única regla que recupera algo (la 3) es la que borra el historial que
la Fase 3 va a graficar.** No hay una tercera opción hoy.

Para calibrar, el mismo día, sin borrar un solo dato:

    idx_prices_latest                            6.104 kB  btree (pharmacy_product_id, recorded_at DESC)
    prices_pharmacy_product_id_recorded_at_idx   7.072 kB  btree (pharmacy_product_id, recorded_at DESC)

Son el **mismo índice dos veces** — definición idéntica, una de Prisma
(`schema.prisma`, `@@index`) y otra creada a mano. Tirar la duplicada recupera
7,07 MiB, el **23 % de la tabla**, contra los 91 KiB de la Regla 2: 77× más,
reversible (se recrea), y sin perder un dato. `prices_pkey` suma otros 6.232 kB
con `idx_scan = 0` — nunca sirvió una consulta, aunque hace falta para el
`DELETE ... WHERE id` de este módulo. Los índices son 19,9 MiB de los 30,8 MiB
de la tabla: **el 65 %**. Ahí está el espacio, no en las filas.

**La respuesta honesta es: hoy no hace falta borrar nada.** Con los defaults
contra la base de hoy este módulo planifica 0 filas, verificado. Lo que sí hace
falta es que la política exista, esté probada y esté agendada **en modo
informe**, para que el día que los números cambien la palanca ya esté puesta.

Por la misma razón este módulo **no** crea una tabla de rollup diario: una tabla
nueva, un backfill, una doble escritura y un cambio de API para ahorrar
fracciones de MB es peor negocio que la política misma. Si algún día hace falta,
la Regla 2 de acá abajo ya deja el histórico en forma de rollup (mínimo, máximo
y cierre por día) dentro de la propia tabla, que es el 90 % del beneficio sin
nada del costo.

## Cuándo sí — disparadores, no fechas

No se ejecuta `--apply` por calendario. Y **el disparador ya no es el disco**:
como el disco crece solo y sin techo (arriba), quedarse sin espacio no es un modo
de falla de esta instancia. El disparador tiene que ser lo que sí duele —
latencia de las consultas y tamaño del índice caliente.

Se revisa la política cuando se cumple uno de:

- `pg_total_relation_size('prices')` **> 500 MiB** (~1,3 M filas). A la tasa
  medida está a ~8 meses. No es «hay que borrar»: es «volver a medir, con la
  Fase 3 ya en producción y sabiendo si alguien lee el historial».
- La tasa de inserción supera **50.000 filas/día** (≈10× la de hoy) tres días
  seguidos. Eso es el flap generalizado, y ahí sí hay que actuar.

Y antes de cualquiera de las dos, tres cosas que no necesitan disparador porque
no borran nada:

1. **Prender los backups de Cloud SQL.** Hoy están apagados. Ninguna corrida con
   `--apply` debería existir antes que esto.
2. **Tirar el índice duplicado** (arriba): 7,07 MiB, ahora, reversible.
3. **Arreglar `check_price`** para que reciba el nombre del producto y
   `price_floor` deje de ser código muerto: corta la fuga de cuarentena de raíz,
   ~136 filas/día para siempre. Ver el punto 1 de la lista de abajo.

Orden cuando se dispare de verdad: Regla 1 primero — es la única que no borra
historial — con `--max-deletes 5000` en la primera corrida real. Regla 2 después,
sabiendo que hoy recuperaría ~91 KiB. Regla 3 nunca, salvo que el flap
generalizado sea la emergencia.

Lo que sí existe hoy es una fuga real y no acotada, y dos riesgos de cola:

1. **Quarantine se reescribe para siempre.** Los productos con más filas de la
   tabla son agujas, jeringas y bajalenguas de Curie, Farmex, Farmaloop y
   Dr. Simi a 90-130 CLP, con 7 a 12 filas cada uno y **todas** de cuarentena:
   `anomaly.py` los rechaza contra el piso de 200 CLP en *cada* corrida, y cada
   rechazo inserta una fila con `source='quarantine'`. Re-medido el 2026-08-03:
   **264 filas, 53 productos, ~136/día, y 52 de esos 53 nunca tuvieron un precio
   aceptado** (antes decía 201 / 48 / 119 / 47 de 48; la fuga crece, la forma no
   cambia). Los peores son cinco agujas de Curie con 13 filas cada una en 38 h.
   Esas filas no se muestran en ninguna parte — las consultas de
   `products.service.ts` que tocan `prices` filtran `source <> 'quarantine'`, y
   `HAS_USABLE_PRICE` exige al menos una fila aceptada — y crecen sin techo.

   Es poco volumen (17 MiB/año) pero es la única fuga que **no** está atada a
   ningún dato real: no es historial, es el mismo rechazo repetido. La causa raíz
   estaba en `anomaly.py` y no en esta política: `price_floor()` existía para
   bajar el piso a 15 CLP cuando el nombre dice "1 unidad" / "1 Aguja", pero
   `check_price()` nunca recibía el nombre y comparaba siempre contra
   `MIN_PLAUSIBLE_CLP` — era código muerto.

   **Corregido el 2026-08-03**: `check_price()` recibe el nombre y llama a
   `price_floor()`. Rescata 27 de los 53 productos en cuarentena (187 de 285
   filas): agujas a 90 CLP, bajalenguas a 60, toallitas a 30. Los otros 26
   siguen rechazados con razón — un `Atenolol 50 mg x 20 comprimidos` a 15 CLP
   es basura de scraping, no un producto barato. `ampolla` quedó fuera del
   patrón: es un envase, no una señal de precio bajo, y un zoledrónico a 50 CLP
   debe seguir rechazándose.
2. **El flapping, que ya empezó.** Hoy son 1.551 productos de dos cadenas
   (arriba). Si el mismo patrón apareciera en Farmex — 22.785 productos, 5
   corridas por día — serían ~110.000 filas/día, 43 MiB/día, y el disco se llena
   en unos 7 meses. Y en el peor caso, si la detección de cambio se rompiera del
   todo, cada corrida escribe cada ítem: con los **312.808 ítems/día** medidos en
   `scraping_jobs` son 123 MiB/día y el disco de 10 GB se llena en **menos de 3
   meses** — más rápido que los 5 meses que estimaba la versión anterior de este
   docstring, porque el throughput real es 1,75× el que se había supuesto.
   La política tiene que estar escrita, probada y lista *antes* de ese día — y
   por eso existen `--max-age-days` y, sobre todo, `--max-fetch`.
3. **Catálogo que crece.** Diez cadenas hoy; el alcance de `docs/PLAN.md` suma
   categorías y cadenas nuevas, y cada producto nuevo es al menos una fila.
   Duplicar el catálogo duplica la pendiente, no la cambia de orden.

## Las tres reglas

Se aplican en orden. Todas respetan el mismo invariante.

**Invariante — nunca se borra la última fila aceptada de un producto.**
Todo camino de lectura de la API resuelve el precio vigente como "la fila más
reciente con `source <> 'quarantine'`" (`idx_prices_latest`, y el guard
`HAS_USABLE_PRICE` de `products.service.ts`). Borrar esa fila no rompe una
consulta: hace que el producto **desaparezca en silencio** del buscador y de la
comparación. Por eso el conjunto protegido se calcula desde la base en cada
corrida y el planificador lo filtra, en vez de confiar en que las reglas "no
llegarían" a esa fila.

**Regla 1 — podar quarantine** (`--quarantine-days`, 30 por defecto).
Borra las filas `source='quarantine'` más viejas que el umbral, salvo la más
reciente de cada producto. No son ofertas: son precios que el detector de
anomalías rechazó, y la web nunca los muestra. Se conserva una por producto
porque es la única evidencia de que ese SKU sigue reportando un precio
implausible — es la señal que dice "acá hay un piso mal calibrado o una cadena
publicando basura". Y para los 34 productos que *solo* tienen filas de
quarantine, esa fila es lo único que registra que alguna vez tuvieron precio.
Borrarlas todas dejaría al producto sin rastro y haría invisible el bug.

**Regla 2 — compactar el intradía** (`--compact-after-days`, 7 por defecto).
Para cada (producto, día local) más viejo que el umbral, conserva tres filas: la
del precio mínimo, la del máximo y la última del día. Borra el resto.

Esto es el rollup diario — mínimo, máximo y cierre — hecho **en la propia tabla
`prices`**, sin tabla nueva, sin backfill, sin doble escritura y sin tocar la
API. El costo es que se pierde la apertura del día; no importa, porque el cierre
del día anterior *es* la apertura del siguiente, y `PriceWriter` solo escribe
cuando algo cambió. Únicamente el primer día de la historia de un producto
pierde su apertura.

Lo que sobrevive es el **conjunto** {mínimo, máximo, cierre}, así que el día
queda con tres filas solo cuando esas tres son filas distintas. Se colapsan a
menudo: con precios que suben en el día, el máximo y el cierre son la misma
fila y el día queda en dos. Con una sola fila, o con dos, no se borra nada.

Los empates se rompen por `recorded_at` y después por `id`, siempre a favor de
la más antigua, así que un día donde el precio no se movió pero sí el stock
conserva la primera y la última fila, que es donde está la transición.

**Ojo con lo que esa frase no dice.** Los sobrevivientes se eligen por `price` y
nada más, pero la fila lleva además `original_price`, `discount_pct`,
`stock_status` y `stock_quantity`. La garantía del párrafo anterior vale solo
cuando el precio *no* se movió en todo el día. En un día donde se mueven el
precio **y** el stock, una transición de stock intermedia se puede perder — la
regla no la ve. Hoy hay 673 filas de cambio que son solo de stock y el máximo
borrable por la Regla 2 en toda la tabla son 238 filas, así que la exposición
está acotada y es chica; pero es una pérdida real, no está en la promesa de
{mínimo, máximo, cierre}, y hay que saberlo antes de correr esto con la Fase 3
mostrando disponibilidad.

El día se calcula en `America/Santiago`, no en UTC. `recorded_at` es
`timestamp without time zone` y el servidor corre en UTC, así que el corte UTC
caería a las 20:00 hora de Chile y partiría cada tarde en dos "días".

**Regla 3 — corte duro por antigüedad** (`--max-age-days`, **apagada** por
defecto). Borra toda fila aceptada más vieja que N días, salvo la última de cada
producto. Está apagada porque el historial de precios es una feature planificada
(`docs/PLAN.md`, Fase 3) y con los números de arriba no hay nada que ganar
tirándolo. Es la palanca para el día del bug de flapping, no la política.

## Cómo escribe

Mismo patrón que `recompute_catalog.py`: la planificación es una función pura y
testeable, el fetch trae solo los candidatos, y los borrados salen por
`executemany` en lotes con un commit por lote. La base es una `db-f1-micro`
compartida con los scrapers: como máximo dos escritores concurrentes, así que
esto se agenda en un hueco del calendario (ver `docs/infra-gcloud.md`).

No hay fallback fila por fila como en `recompute_catalog._write`: ahí existe
porque un índice único puede rechazar un UPDATE, y un DELETE por clave primaria
no tiene ese modo de falla — nada referencia a `prices`.

Un DELETE deja tuplas muertas: autovacuum recupera el espacio para reusarlo pero
no achica el archivo. No se corre `VACUUM FULL` desde acá — toma un lock ACCESS
EXCLUSIVE sobre la tabla que la web está leyendo.

## Deliberadamente autónomo

No importa nada de `src.db` ni de ningún otro módulo del paquete: arma su propio
engine desde `DATABASE_URL`. Es el mismo criterio de `scripts/reap_stale_jobs.py`
y existe para que el archivo pueda viajar dentro de la imagen del scraper —
donde `workers/ingestion/src` no está — y correrse como script suelto en el
Cloud Run Job de mantenimiento.

**Eso todavía no pasó.** `workers/scraper/Dockerfile` copia `workers/scraper/src`
y `scripts/reap_stale_jobs.py`, y nada más: este archivo **no está en esa
imagen**. Y ningún scheduler lo invoca — `price_retention` no aparece en
`scheduler.py`, ni en los scripts de deploy, ni en Cloud Scheduler. O sea que la
recomendación de «agendarlo en modo informe» es una recomendación, no un hecho:
falta empaquetarlo (moverlo a `scripts/` y agregar un `COPY`, o correrlo desde la
imagen de ingestion, que sí lo lleva) y falta agendarlo. La corrida en seco tarda
0,7 s y no escribe, así que el costo de agendarla es cero.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime

from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Same batch size as recompute_catalog: one round trip per 500 rows keeps the
# db-f1-micro from feeling this while the scrapers are the other writer.
BATCH = 500

DEFAULT_QUARANTINE_DAYS = 30
DEFAULT_COMPACT_AFTER_DAYS = 7

# Ceiling on what a single rule loads into memory. Measured: a `PriceRow` costs
# 338 B in the interpreter, and the asyncpg result set is held alongside it while
# the list comprehension in `_fetch_rows` runs, so the real cost is roughly twice
# that. At this cap the worst rule peaks near 500 MiB on a job deployed with
# `--memory=2Gi` (scripts/deploy-scraper-job.sh).
#
# It exists because the fetch is what fails first, and it fails exactly when the
# module is needed. `--max-deletes` caps *deletes*, and it is applied after
# planning — by then the rows are already in RAM, so it is no protection at all
# against the flapping scenario this module was written for. At the measured
# throughput of 312.808 ítems/día a full flap puts more than 3 M rows past the
# 7-day threshold inside two weeks, which is where a 2 GiB job dies.
#
# Hitting the cap makes a run *partial*, never wrong: the rules are idempotent
# and the slice is taken oldest-first, so running again picks up where the last
# run stopped. That is the behaviour you want at 3 a.m. with a full disk.
DEFAULT_MAX_FETCH = 250_000

LOCAL_TZ = "America/Santiago"


@dataclass(frozen=True)
class PriceRow:
    """One `prices` row, with its local calendar day already resolved."""

    id: str
    pharmacy_product_id: str
    day: date
    price: int
    recorded_at: datetime


# ---------------------------------------------------------------- planning


def plan_intraday_compaction(
    rows: list[PriceRow], protected_ids: frozenset[str] = frozenset()
) -> list[PriceRow]:
    """Rows to delete so each (product, day) keeps min, max and close.

    `rows` may arrive in any order; the tie-breaks are applied here so the plan
    does not depend on how the database happened to return them.

    A row in `protected_ids` is never returned, whatever the rule says. That set
    is the current latest accepted row per product — the one the API reads as
    "the price" — and it is checked here rather than assumed away, because the
    day's closing row and the product's latest row only coincide as long as
    nobody edits the SQL.
    """
    by_day: dict[tuple[str, date], list[PriceRow]] = {}
    for row in rows:
        by_day.setdefault((row.pharmacy_product_id, row.day), []).append(row)

    doomed: list[PriceRow] = []
    for group in by_day.values():
        ordered = sorted(group, key=lambda r: (r.recorded_at, r.id))
        keep = {
            # Cheapest row of the day; ties go to the earliest, then lowest id.
            min(ordered, key=lambda r: (r.price, r.recorded_at, r.id)).id,
            # Dearest row, same tie-breaks. Expressed as a `min` over a negated
            # price rather than a `max`, so that "earliest wins the tie" stays a
            # plain ascending comparison on `recorded_at` itself. The earlier
            # version negated the timestamp via `datetime.timestamp()`, which
            # reinterprets these naive UTC values through the machine's local
            # zone and therefore mis-orders rows recorded within an hour of a
            # Chilean DST transition. Negating the integer price is exact and
            # carries no timezone assumption at all.
            min(ordered, key=lambda r: (-r.price, r.recorded_at, r.id)).id,
            # Close of the day.
            ordered[-1].id,
        }
        doomed.extend(r for r in ordered if r.id not in keep)

    return [r for r in doomed if r.id not in protected_ids]


def plan_full_prune(
    rows: list[PriceRow], protected_ids: frozenset[str] = frozenset()
) -> list[PriceRow]:
    """Rows to delete outright — everything handed in that is not protected.

    Used by the quarantine rule and by the hard age cutoff. The scoping (which
    rows are old enough, which source) belongs to the query; the only decision
    left here is the invariant, and it lives in one place for both rules.
    """
    return [r for r in rows if r.id not in protected_ids]


def summarize(rows: list[PriceRow]) -> dict:
    """Counts and date range for a plan, for the dry-run report."""
    if not rows:
        return {"rows": 0, "products": 0, "first": None, "last": None, "days": {}}
    per_day: dict[date, int] = {}
    for r in rows:
        per_day[r.day] = per_day.get(r.day, 0) + 1
    moments = [r.recorded_at for r in rows]
    return {
        "rows": len(rows),
        "products": len({r.pharmacy_product_id for r in rows}),
        "first": min(moments),
        "last": max(moments),
        "days": dict(sorted(per_day.items())),
    }


# ---------------------------------------------------------------- queries

# `recorded_at` is `timestamp without time zone` holding UTC (PriceWriter
# inserts a bare NOW() and the server runs in UTC). `NOW() AT TIME ZONE 'UTC'`
# gives a naive UTC value to compare against, so the cutoff does not silently
# move if the session time zone ever changes.
_AGE_CUTOFF = "(NOW() AT TIME ZONE 'UTC') - make_interval(days => :days)"

_LOCAL_DAY = f"((recorded_at AT TIME ZONE 'UTC') AT TIME ZONE '{LOCAL_TZ}')::date"

# Only days that hold more than one row can lose one, so the fetch skips the
# rest. That is what keeps this cheap: today it returns 0 rows out of 79.227, and
# it stays proportional to price volatility rather than to history.
#
# The cap is applied to `busy` — whole (product, day) groups — and never to the
# rows. Capping rows would cut a day in half, and then min/max/close would be
# computed from a *partial* day: the rule would happily delete the day's real
# minimum because the surviving slice never contained it. Slicing by whole days
# keeps every plan identical to the plan an uncapped run would have produced for
# those days. Oldest day first, so repeated runs converge.
SELECT_COMPACTION_CANDIDATES = f"""
    WITH scoped AS (
        SELECT id, pharmacy_product_id, price, recorded_at,
               {_LOCAL_DAY} AS day
        FROM prices
        WHERE source <> 'quarantine'
          AND recorded_at < {_AGE_CUTOFF}
    ), busy AS (
        SELECT pharmacy_product_id, day
        FROM scoped
        GROUP BY 1, 2
        HAVING count(*) > 1
        ORDER BY day, pharmacy_product_id
        LIMIT :max_fetch
    )
    SELECT s.id, s.pharmacy_product_id, s.day, s.price, s.recorded_at
    FROM scoped s
    JOIN busy b ON b.pharmacy_product_id = s.pharmacy_product_id
               AND b.day = s.day
"""

# Rules 1 and 3 delete rows outright, with no per-group arithmetic, so here a
# plain row cap is exact: a truncated slice yields a truncated plan, never a
# wrong one. Oldest first, matching `--max-deletes`.
SELECT_STALE_QUARANTINE = f"""
    SELECT id, pharmacy_product_id, {_LOCAL_DAY} AS day, price, recorded_at
    FROM prices
    WHERE source = 'quarantine'
      AND recorded_at < {_AGE_CUTOFF}
    ORDER BY recorded_at, id
    LIMIT :max_fetch
"""

SELECT_OVER_MAX_AGE = f"""
    SELECT id, pharmacy_product_id, {_LOCAL_DAY} AS day, price, recorded_at
    FROM prices
    WHERE source <> 'quarantine'
      AND recorded_at < {_AGE_CUTOFF}
    ORDER BY recorded_at, id
    LIMIT :max_fetch
"""

# Bounded by the product count, not by history: ~74.500 ids today and it stays
# there. Cheap enough to recompute on every run, which is the point — the
# invariant is read from the database, never inferred.
SELECT_LATEST_ACCEPTED = """
    SELECT DISTINCT ON (pharmacy_product_id) id
    FROM prices
    WHERE source <> 'quarantine'
    ORDER BY pharmacy_product_id, recorded_at DESC, id
"""

SELECT_LATEST_QUARANTINE = """
    SELECT DISTINCT ON (pharmacy_product_id) id
    FROM prices
    WHERE source = 'quarantine'
    ORDER BY pharmacy_product_id, recorded_at DESC, id
"""

SELECT_TABLE_STATS = """
    SELECT count(*) AS rows,
           pg_total_relation_size('prices') AS total_bytes,
           min(recorded_at) AS first_seen,
           max(recorded_at) AS last_seen
    FROM prices
"""

DELETE_BY_ID = "DELETE FROM prices WHERE id = :id"


# ---------------------------------------------------------------- plumbing


def _session_factory() -> async_sessionmaker:
    """Build an engine straight from `DATABASE_URL`.

    Standalone on purpose — see the module docstring. `load_dotenv` never
    overrides an already-exported variable, so the `.env` fallback cannot
    quietly point a production run at a local database.
    """
    load_dotenv("../../.env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL no está definida. Desde workers/ingestion:\n"
            "  export DATABASE_URL=$(grep '^DATABASE_URL=' ../../.env.production "
            "| cut -d= -f2-)"
        )
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    return async_sessionmaker(create_async_engine(url, echo=False), expire_on_commit=False)


async def _fetch_rows(session, statement: str, params: dict) -> list[PriceRow]:
    result = await session.execute(text(statement), params)
    return [
        PriceRow(
            id=str(r[0]),
            pharmacy_product_id=str(r[1]),
            day=r[2],
            price=int(r[3]),
            recorded_at=r[4],
        )
        for r in result.fetchall()
    ]


async def _fetch_ids(session, statement: str) -> frozenset[str]:
    result = await session.execute(text(statement))
    return frozenset(str(r[0]) for r in result.fetchall())


async def _delete(session, rows: list[PriceRow], label: str) -> int:
    """Delete `rows` by primary key, in batches, one commit per batch.

    No row-by-row fallback: `recompute_catalog._write` needs one because a
    unique index can reject an UPDATE mid-batch, and a DELETE by primary key has
    no equivalent failure — nothing has a foreign key onto `prices`. If a batch
    does fail, it fails loudly and the remaining batches are not attempted.
    """
    stmt = text(DELETE_BY_ID)
    deleted = 0
    for start in range(0, len(rows), BATCH):
        chunk = rows[start : start + BATCH]
        await session.execute(stmt, [{"id": r.id} for r in chunk])
        await session.commit()
        deleted += len(chunk)
        logger.info(f"  {label}: {deleted}/{len(rows)} borradas")
    return deleted


# ---------------------------------------------------------------- reporting


def _report(label: str, plan: list[PriceRow], max_days_shown: int = 30) -> None:
    stats = summarize(plan)
    if not stats["rows"]:
        logger.info(f"{label}: 0 filas — nada que borrar")
        return
    logger.info(
        f"{label}: {stats['rows']} filas en {stats['products']} productos, "
        f"rango {stats['first']:%Y-%m-%d %H:%M} .. {stats['last']:%Y-%m-%d %H:%M} (UTC)"
    )
    days = list(stats["days"].items())
    for day, count in days[:max_days_shown]:
        logger.info(f"    {day}  {count}")
    if len(days) > max_days_shown:
        logger.info(f"    … y {len(days) - max_days_shown} días más")


def _warn_if_capped(loaded: int, cap: int, label: str, unit: str) -> int:
    """Say so, loudly, when a rule loaded exactly its ceiling.

    Returns 1 so the caller can OR it into `stats["fetch_capped"]`. A capped run
    is a correct partial pass, not a failure: every rule takes its slice
    oldest-first and is idempotent, so the fix is to run again, not to raise the
    cap blindly. Silence here would be the bad outcome — the operator would read
    "TOTAL a borrar: N" and believe N was the whole backlog.
    """
    if loaded < cap:
        return 0
    logger.warning(
        f"{label}: se alcanzó el techo de --max-fetch={cap} {unit}. "
        f"Esta corrida es un pase PARCIAL sobre lo más antiguo; volvé a "
        f"correrla hasta que el aviso no aparezca."
    )
    return 1


def _assert_invariant(plan: list[PriceRow], protected: frozenset[str], label: str) -> None:
    """Refuse to go on if a plan somehow contains a live latest price.

    The planners already filter these out. This is the second lock on the same
    door, and it is here because the failure mode is silent: the product simply
    stops appearing on the site, and nothing raises.
    """
    trespass = [r.id for r in plan if r.id in protected]
    if trespass:
        raise RuntimeError(
            f"{label}: el plan incluye {len(trespass)} filas protegidas "
            f"(último precio vigente de su producto). Abortado sin escribir. "
            f"Primeras: {trespass[:5]}"
        )


# ---------------------------------------------------------------- entrypoint


async def run_retention(
    *,
    apply: bool = False,
    quarantine_days: int = DEFAULT_QUARANTINE_DAYS,
    compact_after_days: int = DEFAULT_COMPACT_AFTER_DAYS,
    max_age_days: int | None = None,
    max_deletes: int | None = None,
    max_fetch: int = DEFAULT_MAX_FETCH,
) -> dict[str, int]:
    stats = {
        "quarantine_planned": 0,
        "compaction_planned": 0,
        "max_age_planned": 0,
        "planned_total": 0,
        "deleted": 0,
        # 1 when some rule loaded exactly `max_fetch` units and the run is
        # therefore a partial pass. Not an error — a signal to run again.
        "fetch_capped": 0,
    }

    async with _session_factory()() as session:
        before = (await session.execute(text(SELECT_TABLE_STATS))).fetchone()
        total_rows, total_bytes = int(before[0]), int(before[1])
        per_row = total_bytes / total_rows if total_rows else 0
        # `min`/`max` are NULL on an empty table, and `f"{None:%Y-%m-%d}"`
        # raises TypeError — so the span is only formatted when there is one.
        span = (
            f"{before[2]:%Y-%m-%d} .. {before[3]:%Y-%m-%d}"
            if before[2] and before[3]
            else "sin filas"
        )
        logger.info(
            f"prices: {total_rows} filas, {total_bytes / 1024 / 1024:.1f} MB "
            f"({per_row:.0f} B/fila con índices), {span}"
        )

        latest_accepted = await _fetch_ids(session, SELECT_LATEST_ACCEPTED)
        latest_quarantine = await _fetch_ids(session, SELECT_LATEST_QUARANTINE)
        logger.info(
            f"protegidas: {len(latest_accepted)} últimos precios vigentes, "
            f"{len(latest_quarantine)} últimas cuarentenas"
        )

        # Regla 1 — quarantine.
        stale = await _fetch_rows(
            session,
            SELECT_STALE_QUARANTINE,
            {"days": quarantine_days, "max_fetch": max_fetch},
        )
        quarantine_protected = latest_quarantine | latest_accepted
        quarantine_plan = plan_full_prune(stale, quarantine_protected)
        # Checked against the *quarantine* protected set, not `latest_accepted`.
        # The two are disjoint by construction — the queries partition on
        # `source` — so asserting against `latest_accepted` alone could never
        # fire, and the rule's real invariant (one quarantine row survives per
        # product) would have had no second lock at all.
        _assert_invariant(quarantine_plan, quarantine_protected, "quarantine")
        _report(f"Regla 1 · quarantine >{quarantine_days}d", quarantine_plan)
        stats["fetch_capped"] |= _warn_if_capped(
            len(stale), max_fetch, "Regla 1", "filas de cuarentena"
        )

        # Regla 2 — compactación intradía.
        candidates = await _fetch_rows(
            session,
            SELECT_COMPACTION_CANDIDATES,
            {"days": compact_after_days, "max_fetch": max_fetch},
        )
        busy_days = len({(r.pharmacy_product_id, r.day) for r in candidates})
        logger.info(
            f"Regla 2 · candidatas leídas: {len(candidates)} filas en "
            f"{busy_days} (producto, día) con más de una fila y más de "
            f"{compact_after_days} días de antigüedad"
        )
        compaction_plan = plan_intraday_compaction(candidates, latest_accepted)
        _assert_invariant(compaction_plan, latest_accepted, "compaction")
        _report(f"Regla 2 · intradía >{compact_after_days}d", compaction_plan)
        # The cap is on whole (producto, día) groups here, so that is what is
        # compared — see SELECT_COMPACTION_CANDIDATES for why rows would be wrong.
        stats["fetch_capped"] |= _warn_if_capped(
            busy_days, max_fetch, "Regla 2", "grupos (producto, día)"
        )

        # Regla 3 — corte duro, apagado salvo que se pida.
        max_age_plan: list[PriceRow] = []
        if max_age_days is not None:
            old = await _fetch_rows(
                session,
                SELECT_OVER_MAX_AGE,
                {"days": max_age_days, "max_fetch": max_fetch},
            )
            max_age_plan = plan_full_prune(old, latest_accepted)
            _assert_invariant(max_age_plan, latest_accepted, "max-age")
            _report(f"Regla 3 · corte duro >{max_age_days}d", max_age_plan)
            stats["fetch_capped"] |= _warn_if_capped(
                len(old), max_fetch, "Regla 3", "filas"
            )
        else:
            logger.info("Regla 3 · corte duro: apagada (sin --max-age-days)")

        stats["quarantine_planned"] = len(quarantine_plan)
        stats["compaction_planned"] = len(compaction_plan)
        stats["max_age_planned"] = len(max_age_plan)

        plan = quarantine_plan + compaction_plan + max_age_plan
        # A row can be reached by more than one rule; delete it once.
        seen: set[str] = set()
        plan = [r for r in plan if not (r.id in seen or seen.add(r.id))]
        stats["planned_total"] = len(plan)

        if max_deletes is not None and len(plan) > max_deletes:
            plan.sort(key=lambda r: (r.recorded_at, r.id))
            logger.warning(
                f"--max-deletes={max_deletes}: el plan tiene {stats['planned_total']} "
                f"filas, se recortan a las {max_deletes} más antiguas"
            )
            plan = plan[:max_deletes]

        pct = 100 * len(plan) / total_rows if total_rows else 0
        logger.info(
            f"TOTAL a borrar: {len(plan)} de {total_rows} filas ({pct:.2f} %), "
            f"~{len(plan) * per_row / 1024 / 1024:.2f} MB"
        )

        if not apply:
            logger.info(
                "dry-run: no se borró nada. Para ejecutar, repetir con --apply."
            )
            return stats

        if not plan:
            return stats

        logger.warning(f"--apply: borrando {len(plan)} filas de prices")
        stats["deleted"] = await _delete(session, plan, "prices")

        after = (await session.execute(text(SELECT_TABLE_STATS))).fetchone()
        logger.info(
            f"prices ahora: {after[0]} filas "
            f"({int(after[1]) / 1024 / 1024:.1f} MB en disco; el archivo no se "
            f"achica hasta que autovacuum reuse el espacio)"
        )

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Política de retención de `prices`. Por defecto solo informa; "
            "borrar exige --apply."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo informar. Es el comportamiento por defecto; el flag existe "
        "para poder escribirlo explícitamente en un scheduler.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Borrar de verdad. Sin esto no se escribe nada.",
    )
    parser.add_argument(
        "--quarantine-days",
        type=int,
        default=DEFAULT_QUARANTINE_DAYS,
        help="Regla 1: antigüedad desde la que se poda quarantine "
        f"(default {DEFAULT_QUARANTINE_DAYS}). Siempre sobrevive la más "
        "reciente de cada producto.",
    )
    parser.add_argument(
        "--compact-after-days",
        type=int,
        default=DEFAULT_COMPACT_AFTER_DAYS,
        help="Regla 2: antigüedad desde la que el intradía se reduce a mínimo, "
        f"máximo y cierre del día (default {DEFAULT_COMPACT_AFTER_DAYS}).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Regla 3: corte duro. Borra toda fila aceptada más vieja que N "
        "días salvo la última de cada producto. Apagada por defecto.",
    )
    parser.add_argument(
        "--max-deletes",
        type=int,
        default=None,
        help="Techo de filas a borrar en esta corrida, las más antiguas "
        "primero. Acota el daño de la primera ejecución real.",
    )
    parser.add_argument(
        "--max-fetch",
        type=int,
        default=DEFAULT_MAX_FETCH,
        help="Techo de lo que cada regla carga en memoria "
        f"(default {DEFAULT_MAX_FETCH}). Distinto de --max-deletes, que "
        "recorta el plan cuando las filas ya están en RAM. Al alcanzarlo la "
        "corrida es un pase parcial sobre lo más antiguo y lo avisa.",
    )
    args = parser.parse_args()

    if args.dry_run and args.apply:
        parser.error("--dry-run y --apply se contradicen; elegí uno")
    for name in ("quarantine_days", "compact_after_days", "max_age_days"):
        value = getattr(args, name)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} tiene que ser >= 1")
    for name in ("max_deletes", "max_fetch"):
        value = getattr(args, name)
        if value is not None and value < 1:
            parser.error(f"--{name.replace('_', '-')} tiene que ser >= 1")

    stats = asyncio.run(
        run_retention(
            apply=args.apply,
            quarantine_days=args.quarantine_days,
            compact_after_days=args.compact_after_days,
            max_age_days=args.max_age_days,
            max_deletes=args.max_deletes,
            max_fetch=args.max_fetch,
        )
    )
    logger.info(f"Listo: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
