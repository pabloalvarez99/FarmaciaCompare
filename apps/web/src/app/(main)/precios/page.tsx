import { Suspense } from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import {
  getCategories,
  getCoverage,
  isLiveDataConfigured,
  searchProducts,
} from '@/lib/api-products';
import { shortPharmacy } from '@/lib/pharmacy';
import { ProductCard } from '@/components/prices/ProductCard';
import { ResultsSkeleton } from '@/components/prices/ResultsSkeleton';

export const metadata: Metadata = {
  title: 'Precios reales de salud y bienestar — FarmaciaCompare',
  description:
    'Medicamentos, suplementos, dermocosmética, cosmética, higiene y cuidado del bebé. Precios recolectados directamente de Cruz Verde, Salcobrand, Farmacias Ahumada, Dr. Simi, Farmex, Preunic, MercadoFarma, Farmacias Curie, Knop y Farmaloop.',
};

interface Props {
  searchParams: { q?: string; page?: string; category?: string };
}

// Medicines first — they are still the largest category and the reason most
// people arrive — but the tail shows the catalogue is wider than that.
const SUGGESTIONS = [
  'Paracetamol',
  'Ibuprofeno',
  'Omeprazol',
  'Losartán',
  'Protector solar',
  'Vitamina D',
  'Shampoo',
  'Pañales',
];

function SuggestionChips({ terms }: { terms: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {terms.map((term) => (
        <Link
          key={term}
          href={`/precios?q=${encodeURIComponent(term)}`}
          className="rounded-full bg-gray-100 px-3.5 py-1.5 text-sm text-gray-700 transition-colors hover:bg-blue-50 hover:text-blue-700"
        >
          {term}
        </Link>
      ))}
    </div>
  );
}

/**
 * Page numbers to render around the current one. A 103-page result set cannot
 * show every page, and "‹ ›" alone makes page 60 unreachable in one move, so
 * the first and last are always offered plus a window of neighbours.
 */
function pageWindow(page: number, totalPages: number): (number | 'gap')[] {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i + 1);
  }

  const around = new Set<number>([1, totalPages, page]);
  for (const n of [page - 1, page + 1]) {
    if (n >= 1 && n <= totalPages) around.add(n);
  }

  const sorted = [...around].sort((a, b) => a - b);
  const out: (number | 'gap')[] = [];
  let previous = 0;
  for (const n of sorted) {
    if (previous && n - previous > 1) out.push('gap');
    out.push(n);
    previous = n;
  }
  return out;
}

/**
 * The listing shell renders instantly — heading, search box — and the part that
 * waits on the API streams in behind a skeleton. Typing a search should never
 * leave the visitor on a blank screen while a Cloud Run instance wakes up.
 */
export default function PreciosPage({ searchParams }: Props) {
  const query = (searchParams.q ?? '').trim();
  const page = Math.max(1, parseInt(searchParams.page ?? '1', 10) || 1);
  const category = (searchParams.category ?? '').trim();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="display text-3xl font-bold text-gray-900">Todos los listados</h1>
        <p className="mt-1.5 text-gray-600">
          Cada fila es un producto en una farmacia. Si se puede comparar entre cadenas, toca
          la fila.
        </p>
        <p className="mt-2">
          <Link
            href="/comparar"
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            Ver mayores diferencias de precio →
          </Link>
        </p>
      </header>

      {/* A plain GET form, so search keeps working with JavaScript off and every
          result page is a shareable, indexable URL. */}
      <form action="/precios" method="get" className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="search"
            name="q"
            defaultValue={query}
            placeholder="Buscar producto: paracetamol, shampoo, protector solar…"
            className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none"
            aria-label="Buscar producto"
          />
          <button
            type="submit"
            className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition-colors hover:bg-blue-700"
          >
            Buscar
          </button>
        </div>
        {/* Carried as a hidden field so searching again keeps the chosen
            category instead of silently dropping back to everything. */}
        {category && <input type="hidden" name="category" value={category} />}
      </form>

      <Suspense fallback={null}>
        <CategoryFilter active={category} query={query} />
      </Suspense>

      {query && (
        <p className="mb-6 text-sm text-gray-600">
          Buscando <strong className="font-semibold text-gray-900">“{query}”</strong>
          {' · '}
          <Link href="/precios" className="text-blue-600 hover:underline">
            limpiar búsqueda
          </Link>
        </p>
      )}

      {/* Keyed so a new search remounts the boundary and shows the skeleton
          again instead of leaving the previous results on screen. */}
      <Suspense key={`${query}|${page}|${category}`} fallback={<ResultsSkeleton />}>
        <Results query={query} page={page} category={category} />
      </Suspense>

      <p className="mt-10 border-t border-gray-200 pt-4 text-xs leading-relaxed text-gray-500">
        Cada tarjeta es un producto tal como lo publica esa farmacia. Si tiene código de
        barras o está vinculado al catálogo, abre la comparación entre cadenas (incluye
        Cruz Verde, Salcobrand y Dr. Simi vía catálogo). Ver también{' '}
        <Link href="/comparar" className="text-blue-600 hover:underline">
          mayores diferencias de precio
        </Link>
        . Los precios cambian durante el día: confirma en la farmacia antes de comprar.
      </p>
    </div>
  );
}

/**
 * The category chips, fetched so the list and its counts never drift from what
 * the classifier actually produced.
 *
 * There is no "sin categoría" chip on purpose: a null category means no chain
 * evidence was good enough to place the listing, and offering it as a bucket
 * would present ignorance as a classification. Those products stay reachable —
 * they show up whenever no category is selected.
 */
async function CategoryFilter({ active, query }: { active: string; query: string }) {
  const categories = await getCategories();
  if (categories.length === 0) return null;

  const href = (id: string) => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (id) params.set('category', id);
    const qs = params.toString();
    return `/precios${qs ? `?${qs}` : ''}`;
  };

  const chip = (isActive: boolean) =>
    `rounded-full px-3.5 py-1.5 text-sm transition-colors ${
      isActive
        ? 'bg-blue-600 text-white'
        : 'bg-gray-100 text-gray-700 hover:bg-blue-50 hover:text-blue-700'
    }`;

  return (
    <nav aria-label="Filtrar por categoría" className="mb-5 flex flex-wrap gap-2">
      <Link href={href('')} className={chip(!active)}>
        Todo
      </Link>
      {categories.map((c) => (
        <Link key={c.id} href={href(c.id)} className={chip(active === c.id)}>
          {c.name}
          <span className={active === c.id ? 'ml-1.5 text-blue-100' : 'ml-1.5 text-gray-400'}>
            {c.productCount.toLocaleString('es-CL')}
          </span>
        </Link>
      ))}
    </nav>
  );
}

async function Results({
  query,
  page,
  category,
}: {
  query: string;
  page: number;
  category: string;
}) {
  const configured = isLiveDataConfigured();
  const [data, coverage] = await Promise.all([
    searchProducts(query, page, 30, category || undefined),
    getCoverage(),
  ]);

  const totalProducts = coverage.reduce((sum, c) => sum + c.productCount, 0);
  const activeChains = coverage.filter((c) => c.productCount > 0);

  const pageHref = (n: number) => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (category) params.set('category', category);
    if (n > 1) params.set('page', String(n));
    const qs = params.toString();
    return `/precios${qs ? `?${qs}` : ''}`;
  };

  if (!configured) {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-amber-900">
        <p className="font-semibold">No podemos consultar los precios ahora.</p>
        <p className="mt-1.5 text-sm">
          Falta configurar <code className="font-mono">NEXT_PUBLIC_API_URL</code> en este
          despliegue, así que la página no tiene de dónde leer los datos. Preferimos decirlo
          antes que mostrar precios inventados.
        </p>
      </div>
    );
  }

  if (data.results.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center">
        <p className="text-lg font-semibold text-gray-900">
          {query ? `Sin resultados para “${query}”` : 'Todavía no hay productos cargados'}
        </p>
        <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
          {query
            ? 'Buscamos por el nombre tal como lo publica cada farmacia. Prueba con el principio activo (paracetamol) en vez de la marca, o con menos palabras.'
            : 'Los scrapers todavía no han entregado precios para esta consulta.'}
        </p>
        <div className="mt-5 flex justify-center">
          <SuggestionChips terms={SUGGESTIONS.slice(0, 5)} />
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Suggestions and coverage only when nothing has been searched: once you
          have a query, the results are what you came for and should not sit
          below a fold of metadata. */}
      {!query && (
        <div className="mb-6 space-y-4">
          <SuggestionChips terms={SUGGESTIONS} />
          {activeChains.length > 0 && (
            <section>
              <h2 className="label mb-2 text-gray-500">
                Cobertura por farmacia · {totalProducts.toLocaleString('es-CL')} productos
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {activeChains.map((c) => (
                  <span
                    key={c.pharmacyId}
                    className="rounded-full border border-gray-200 bg-white px-3 py-1 text-sm text-gray-600"
                  >
                    {shortPharmacy(c.name)}{' '}
                    <span className="figure font-semibold text-gray-900">
                      {c.productCount.toLocaleString('es-CL')}
                    </span>
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-sm text-gray-600">
          <strong className="figure font-semibold text-gray-900">
            {data.total.toLocaleString('es-CL')}
          </strong>{' '}
          {data.total === 1 ? 'resultado' : 'resultados'}
        </p>
        {data.totalPages > 1 && (
          <p className="text-sm text-gray-500">
            Página {page.toLocaleString('es-CL')} de{' '}
            {data.totalPages.toLocaleString('es-CL')}
          </p>
        )}
      </div>

      <ul className="divide-y divide-gray-100 overflow-hidden rounded-xl border border-gray-200 bg-white">
        {data.results.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </ul>

      {data.totalPages > 1 && (
        <nav
          className="mt-6 flex flex-wrap items-center justify-center gap-1.5"
          aria-label="Paginación de resultados"
        >
          {page > 1 ? (
            <Link
              href={pageHref(page - 1)}
              rel="prev"
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
            >
              ← Anterior
            </Link>
          ) : (
            <span className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-300">
              ← Anterior
            </span>
          )}

          <span className="hidden items-center gap-1.5 sm:flex">
            {pageWindow(page, data.totalPages).map((n, i) =>
              n === 'gap' ? (
                <span key={`gap-${i}`} className="px-1 text-sm text-gray-400">
                  …
                </span>
              ) : n === page ? (
                <span
                  key={n}
                  aria-current="page"
                  className="figure rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-semibold text-white"
                >
                  {n}
                </span>
              ) : (
                <Link
                  key={n}
                  href={pageHref(n)}
                  className="figure rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
                >
                  {n}
                </Link>
              ),
            )}
          </span>

          {page < data.totalPages ? (
            <Link
              href={pageHref(page + 1)}
              rel="next"
              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 transition-colors hover:border-blue-300 hover:text-blue-700"
            >
              Siguiente →
            </Link>
          ) : (
            <span className="rounded-lg border border-gray-200 px-3 py-1.5 text-sm text-gray-300">
              Siguiente →
            </span>
          )}
        </nav>
      )}
    </>
  );
}
