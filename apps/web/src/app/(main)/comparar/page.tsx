import { Suspense } from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import {
  formatCLP,
  getComparisons,
  isLiveDataConfigured,
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
 * Default: catalog (groupBy=medication). Barcode is a secondary advanced path.
 */
export default function CompararPage({ searchParams }: Props) {
  const query = (searchParams.q ?? '').trim();
  const via = (searchParams.via ?? 'medication').trim().toLowerCase();
  const groupBy = via === 'barcode' ? 'barcode' : 'medication';
  const minSaving = parseMinSaving(searchParams.minSaving);
  const isBarcode = groupBy === 'barcode';

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-5">
        <h1 className="display text-3xl font-bold text-gray-900">
          Dónde hay más diferencia de precio
        </h1>
        <p className="mt-1.5 text-gray-600">
          Mismo producto, distinta farmacia. Ordenado por cuánto ahorras.
        </p>
      </header>

      <form action="/comparar" method="get" className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="search"
            name="q"
            defaultValue={query}
            placeholder="Buscar: losartán, ozempic, metformina…"
            className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none"
            aria-label="Buscar medicamento"
          />
          {isBarcode && <input type="hidden" name="via" value="barcode" />}
          {minSaving > 0 && (
            <input type="hidden" name="minSaving" value={String(minSaving)} />
          )}
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition-colors hover:bg-blue-700"
          >
            Buscar
          </button>
        </div>
      </form>

      <nav
        aria-label="Ahorro mínimo"
        className="mb-3 flex flex-wrap items-center gap-2"
      >
        <span className="text-sm text-gray-500">Ahorro:</span>
        {MIN_SAVING_CHIPS.map((chip) => {
          const active = minSaving === chip.value;
          return (
            <Link
              key={chip.value}
              href={compararHref({
                q: query || undefined,
                via: groupBy,
                minSaving: chip.value,
              })}
              className={`rounded-full px-3.5 py-1.5 text-sm transition-colors ${
                active
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {chip.label}
            </Link>
          );
        })}
      </nav>

      {/* Advanced: exact barcode — secondary, not equal to primary catalog path */}
      <p className="mb-5 text-xs text-gray-500">
        {isBarcode ? (
          <>
            Viendo solo coincidencia exacta por código de barras.{' '}
            <Link
              href={compararHref({
                q: query || undefined,
                minSaving,
              })}
              className="text-blue-600 hover:underline"
            >
              Volver a la vista habitual
            </Link>
          </>
        ) : (
          <Link
            href={compararHref({
              q: query || undefined,
              via: 'barcode',
              minSaving,
            })}
            className="text-gray-500 underline-offset-2 hover:text-gray-700 hover:underline"
          >
            Código de barras exacto
          </Link>
        )}
      </p>

      {query && (
        <p className="mb-5 text-sm text-gray-600">
          Buscando{' '}
          <strong className="font-semibold text-gray-900">“{query}”</strong>
          {' · '}
          <Link
            href={compararHref({
              via: groupBy,
              minSaving,
            })}
            className="text-blue-600 hover:underline"
          >
            limpiar
          </Link>
        </p>
      )}

      {!query && (
        <div className="mb-5 flex flex-wrap gap-2">
          {SUGGESTIONS.map((term) => (
            <Link
              key={term}
              href={compararHref({
                q: term,
                via: groupBy,
                minSaving,
              })}
              className="rounded-full bg-gray-100 px-3.5 py-1.5 text-sm text-gray-700 transition-colors hover:bg-blue-50 hover:text-blue-700"
            >
              {term}
            </Link>
          ))}
        </div>
      )}

      <Suspense
        key={`${groupBy}|${query}|${minSaving}`}
        fallback={<ResultsSkeleton />}
      >
        <Results query={query} groupBy={groupBy} minSaving={minSaving} />
      </Suspense>

      <p className="mt-10 border-t border-gray-200 pt-4 text-xs leading-relaxed text-gray-500">
        Los precios son referenciales de tiendas online. Verifica siempre en la
        farmacia antes de comprar.
        {isBarcode && (
          <>
            {' '}
            Esta vista solo muestra coincidencias con el mismo código de barras;
            no incluye cadenas que no lo publican.
          </>
        )}
      </p>
    </div>
  );
}

async function Results({
  query,
  groupBy,
  minSaving,
}: {
  query: string;
  groupBy: 'barcode' | 'medication';
  minSaving: number;
}) {
  if (!isLiveDataConfigured()) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-amber-900">
        <p className="font-semibold">No podemos consultar los precios ahora.</p>
        <p className="mt-1.5 text-sm">
          Intenta de nuevo en unos minutos.
        </p>
      </div>
    );
  }

  const groups = await getComparisons(query, DEFAULT_LIMIT, minSaving, groupBy);

  if (groups.length === 0) {
    const lowerChip = [...MIN_SAVING_CHIPS]
      .reverse()
      .find((c) => c.value < minSaving);

    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center">
        <p className="text-lg font-semibold text-gray-900">
          {query
            ? `No encontramos “${query}” con varias farmacias`
            : minSaving > 0
              ? `Sin diferencias de ${MIN_SAVING_CHIPS.find((c) => c.value === minSaving)?.label ?? formatCLP(minSaving)}`
              : 'Aún no hay comparaciones disponibles'}
        </p>
        <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
          {minSaving > 0
            ? 'Prueba un filtro de ahorro más bajo, o quítalo.'
            : query
              ? 'Prueba con menos palabras o el nombre del principio activo.'
              : 'Vuelve más tarde; estamos cargando más precios.'}
        </p>
        {minSaving > 0 && lowerChip && (
          <p className="mt-4">
            <Link
              href={compararHref({
                q: query || undefined,
                via: groupBy,
                minSaving: lowerChip.value,
              })}
              className="text-sm font-medium text-blue-600 hover:underline"
            >
              Ver con filtro “{lowerChip.label}” →
            </Link>
          </p>
        )}
        {query && (
          <p className="mt-3">
            <Link
              href={`/precios?q=${encodeURIComponent(query)}`}
              className="text-sm font-medium text-blue-600 hover:underline"
            >
              Buscar en todos los precios →
            </Link>
          </p>
        )}
      </div>
    );
  }

  const largestSaving = Math.max(...groups.map((g) => g.saving ?? 0));

  return (
    <>
      <p className="mb-3 text-sm text-gray-600">
        <strong className="figure font-semibold text-gray-900">
          {groups.length.toLocaleString('es-CL')}
        </strong>{' '}
        {groups.length === 1 ? 'resultado' : 'resultados'}
        {minSaving > 0 && (
          <>
            {' '}
            con ahorro ≥{' '}
            <span className="figure font-medium text-gray-800">
              {formatCLP(minSaving)}
            </span>
          </>
        )}
        {largestSaving > 0 && (
          <>
            {' · '}
            mayor ahorro:{' '}
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
