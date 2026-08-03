import { Suspense } from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import {
  formatCLP,
  getComparisons,
  isLiveDataConfigured,
  type MatchBasis,
} from '@/lib/api-products';
import { compararHref } from '@/lib/comparar-url';
import { ComparisonGroupCard } from '@/components/prices/ComparisonGroupCard';
import { ResultsSkeleton } from '@/components/prices/ResultsSkeleton';

export const metadata: Metadata = {
  title: 'Comparar precios entre cadenas — FarmaciaCompare',
  description:
    'Mismo producto, distinta farmacia. Ordenado por cuánto ahorras entre cadenas online de Chile.',
};

export const revalidate = 300;

interface Props {
  searchParams: { q?: string; via?: string; minSaving?: string };
}

const SUGGESTIONS = [
  'Lenalidomida',
  'Abiraterona',
  'Ozempic',
  'Losartán',
  'Paracetamol',
  'Omeprazol',
  'Atorvastatina',
  'Metformina',
];

/**
 * Suggestions for the derived view. The drug names above return nothing there:
 * that path only covers cosmetics, hygiene, baby care, dermocosmetics,
 * supplements and devices, and offering a chip that leads to an empty page is
 * worse than offering none.
 */
const DERIVED_SUGGESTIONS = [
  'Shampoo',
  'Pañales',
  'Protector solar',
  'Desodorante',
  'Serum',
  'Pasta dental',
  'Fórmula infantil',
  'Crema',
];

/** Filters that map 1:1 to the API `minSaving` query param (CLP). */
const MIN_SAVING_CHIPS = [
  { value: 0, label: 'Todos' },
  { value: 5_000, label: '+$5 mil' },
  { value: 20_000, label: '+$20 mil' },
  { value: 100_000, label: '+$100 mil' },
] as const;

const DEFAULT_LIMIT = 60;

function parseMinSaving(raw: string | undefined): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return 0;
  return Math.floor(n);
}

/**
 * Savings-ranked multi-chain comparisons.
 *
 * Three ways of deciding that two listings are the same product, exposed as
 * three views because they cover different halves of the catalogue and produce
 * different strengths of evidence.
 *
 * The labels name what you get, not how we got it. "Código de barras" was the
 * old third tab: it named our method, which is not a thing anyone shops for,
 * and it sat next to two tabs named after products — three options on two
 * different axes. The method is still stated, one line below, where it answers
 * the question a reader actually has.
 */
const VIA_LABEL = {
  medication: 'Medicamentos',
  derivado: 'Belleza, higiene y bebé',
  barcode: 'Producto idéntico',
} as const;

type Via = keyof typeof VIA_LABEL;

function parseVia(raw: string | undefined): Via {
  const value = (raw ?? '').trim().toLowerCase();
  if (value === 'barcode') return 'barcode';
  if (value === 'derivado' || value === 'derived') return 'derivado';
  return 'medication';
}

export default function CompararPage({ searchParams }: Props) {
  const query = (searchParams.q ?? '').trim();
  const via = parseVia(searchParams.via);
  const groupBy = via === 'derivado' ? 'derived' : via;
  const minSaving = parseMinSaving(searchParams.minSaving);
  const isBarcode = via === 'barcode';
  const isDerived = via === 'derivado';

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-5">
        <h1 className="display text-3xl font-bold text-foreground">
          Dónde hay más diferencia de precio
        </h1>
        <p className="mt-1.5 text-muted-foreground">
          El mismo producto en varias farmacias, ordenado por cuánto cambia el precio
          entre la más barata y la más cara.
        </p>
      </header>

      <form action="/comparar" method="get" className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="search"
            name="q"
            defaultValue={query}
            placeholder={
              isDerived
                ? 'Buscar: shampoo, pañales, protector solar…'
                : 'Buscar: losartán, ozempic, metformina…'
            }
            className="flex-1 rounded-md border border-edge bg-card px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:border-foreground focus:outline-none"
            aria-label="Buscar producto"
          />
          {via !== 'medication' && <input type="hidden" name="via" value={via} />}
          {minSaving > 0 && (
            <input type="hidden" name="minSaving" value={String(minSaving)} />
          )}
          <button type="submit" className="btn-solid">
            Buscar
          </button>
        </div>
      </form>

      {/* Which evidence produced these groups. A tab rather than a hidden
          "advanced" link, because the three cover different halves of the
          catalogue: asking for shampoo in the medicines view returns nothing,
          and a reader has no way to guess why. */}
      <nav
        aria-label="Cómo se agrupan los productos"
        className="mb-3 flex flex-wrap items-center gap-2"
      >
        {(Object.keys(VIA_LABEL) as Via[]).map((option) => {
          const active = via === option;
          return (
            <Link
              key={option}
              href={compararHref({
                q: query || undefined,
                via: option,
                minSaving,
              })}
              aria-current={active ? 'page' : undefined}
              className={`chip ${active ? 'chip-on' : ''}`}
            >
              {VIA_LABEL[option]}
            </Link>
          );
        })}
      </nav>

      <nav
        aria-label="Diferencia mínima"
        className="mb-3 flex flex-wrap items-center gap-2"
      >
        <span className="text-sm text-muted-foreground">Diferencia mínima:</span>
        {MIN_SAVING_CHIPS.map((chip) => {
          const active = minSaving === chip.value;
          return (
            <Link
              key={chip.value}
              href={compararHref({
                q: query || undefined,
                via,
                minSaving: chip.value,
              })}
              aria-current={active ? 'page' : undefined}
              className={`chip ${active ? 'chip-on' : ''}`}
            >
              {chip.label}
            </Link>
          );
        })}
      </nav>

      {/* What each view is matching on, in one line. The derived one says it
          plainly: these groups come from how the shops describe the product,
          not from a code either of them published. */}
      <p className="mb-5 max-w-2xl text-sm text-muted-foreground">
        {isBarcode
          ? 'Las dos farmacias publican el mismo código de barras, así que es literalmente la misma caja. No aparecen acá las cadenas que no publican el código: Cruz Verde, Salcobrand y Dr. Simi.'
          : isDerived
            ? 'Cosmética, higiene, bebé, dermocosmética, suplementos y dispositivos. No existe un registro oficial para estas categorías y casi ninguna trae código de barras, así que los agrupamos por marca, tamaño y descripción.'
            : 'El mismo remedio del registro sanitario del ISP: mismo principio activo, misma concentración, misma presentación. Es la única vía que alcanza a Cruz Verde, Salcobrand y Dr. Simi, que no publican código de barras.'}
      </p>

      {query && (
        <p className="mb-5 text-sm text-muted-foreground">
          Buscando{' '}
          <strong className="font-semibold text-foreground">“{query}”</strong>
          {' · '}
          <Link
            href={compararHref({
              via,
              minSaving,
            })}
            className="link"
          >
            limpiar
          </Link>
        </p>
      )}

      {!query && (
        <div className="mb-5 flex flex-wrap gap-2">
          {(isDerived ? DERIVED_SUGGESTIONS : SUGGESTIONS).map((term) => (
            <Link
              key={term}
              href={compararHref({
                q: term,
                via,
                minSaving,
              })}
              className="chip"
            >
              {term}
            </Link>
          ))}
        </div>
      )}

      <Suspense
        key={`${via}|${query}|${minSaving}`}
        fallback={<ResultsSkeleton />}
      >
        <Results query={query} via={via} minSaving={minSaving} />
      </Suspense>

      <p className="mt-10 border-t border-edge pt-4 text-xs leading-relaxed text-muted-foreground">
        Los precios son los de las tiendas online y cambian durante el día. Confirma en
        la farmacia antes de comprar.
        {isDerived && (
          <>
            {' '}
            Un producto sólo se agrupa cuando marca, tamaño y descripción calzan, así
            que muchos listados quedan sin comparación — preferimos eso a juntar dos
            productos distintos.
          </>
        )}
      </p>
    </div>
  );
}

async function Results({
  query,
  via,
  minSaving,
}: {
  query: string;
  via: Via;
  minSaving: number;
}) {
  // `via` is the URL word, `groupBy` the API word. They differ for the derived
  // view (`derivado` reads as Spanish in a URL a person may share; the API
  // parameter is English like every other one), so the mapping lives here and
  // nowhere else.
  const groupBy: MatchBasis = via === 'derivado' ? 'derived' : via;
  if (!isLiveDataConfigured()) {
    return (
      <div className="panel border-high/30 bg-high-tint p-6 text-high">
        <p className="font-semibold">No podemos consultar los precios ahora.</p>
        <p className="mt-1.5 text-sm">Intenta de nuevo en unos minutos.</p>
      </div>
    );
  }

  const groups = await getComparisons(query, DEFAULT_LIMIT, minSaving, groupBy);

  if (groups.length === 0) {
    const lowerChip = [...MIN_SAVING_CHIPS]
      .reverse()
      .find((c) => c.value < minSaving);

    return (
      <div className="panel border-dashed p-10 text-center">
        <p className="text-lg font-semibold text-foreground">
          {query
            ? `No encontramos “${query}” en más de una farmacia`
            : minSaving > 0
              ? `Sin diferencias de ${MIN_SAVING_CHIPS.find((c) => c.value === minSaving)?.label ?? formatCLP(minSaving)}`
              : 'Aún no hay comparaciones disponibles'}
        </p>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          {minSaving > 0
            ? 'Prueba con una diferencia mínima más baja, o quítala.'
            : query
              ? via === 'derivado'
                ? 'Prueba con menos palabras, o con la marca (Dove, CeraVe, Huggies). Esta vista cubre belleza, higiene, bebé, suplementos y dispositivos.'
                : via === 'barcode'
                  ? 'Puede que las farmacias que lo venden no publiquen su código de barras. Prueba en Medicamentos, que también las alcanza.'
                  : 'Prueba con menos palabras o con el nombre del principio activo.'
              : 'Vuelve más tarde; estamos cargando más precios.'}
        </p>
        {minSaving > 0 && lowerChip && (
          <p className="mt-4">
            <Link
              href={compararHref({
                q: query || undefined,
                via,
                minSaving: lowerChip.value,
              })}
              className="link text-sm"
            >
              Ver con “{lowerChip.label}” →
            </Link>
          </p>
        )}
        {query && via === 'barcode' && (
          <p className="mt-3">
            <Link
              href={compararHref({ q: query, via: 'medication', minSaving })}
              className="link text-sm"
            >
              Buscar “{query}” en Medicamentos →
            </Link>
          </p>
        )}
        {query && (
          <p className="mt-3">
            <Link href={`/precios?q=${encodeURIComponent(query)}`} className="link text-sm">
              Ver cada farmacia por separado →
            </Link>
          </p>
        )}
      </div>
    );
  }

  const largestSaving = Math.max(...groups.map((g) => g.saving ?? 0));

  return (
    <>
      <p className="mb-3 text-sm text-muted-foreground">
        <strong className="figure font-semibold text-foreground">
          {groups.length.toLocaleString('es-CL')}
        </strong>{' '}
        {groups.length === 1 ? 'producto' : 'productos'}
        {minSaving > 0 && (
          <>
            {' '}
            con diferencia ≥{' '}
            <span className="figure font-medium text-foreground">
              {formatCLP(minSaving)}
            </span>
          </>
        )}
        {largestSaving > 0 && (
          <>
            {' · '}
            la mayor:{' '}
            <strong className="figure font-semibold text-save">
              {formatCLP(largestSaving)}
            </strong>
          </>
        )}
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {groups.map((group) => (
          <ComparisonGroupCard key={group.id} group={group} />
        ))}
      </div>
    </>
  );
}
