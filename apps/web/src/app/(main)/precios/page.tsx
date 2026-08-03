import { Suspense } from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import {
  formatCLP,
  getCategories,
  getCoverage,
  isLiveDataConfigured,
  searchProducts,
  type PharmacyCoverage,
} from '@/lib/api-products';
import { categoryLabel } from '@/lib/categories';
import {
  hasActiveFilters,
  parsePrecios,
  preciosHref,
  type PreciosState,
} from '@/lib/precios-url';
import { shortPharmacy } from '@/lib/pharmacy';
import { ProductCard } from '@/components/prices/ProductCard';
import { ResultsSkeleton } from '@/components/prices/ResultsSkeleton';

export const metadata: Metadata = {
  title: 'Buscar un producto — FarmaciaCompare',
  description:
    'Medicamentos, suplementos, dermocosmética, cosmética, higiene y cuidado del bebé. Precios recogidos de Cruz Verde, Salcobrand, Farmacias Ahumada, Dr. Simi, Farmex, Preunic, MercadoFarma, Farmacias Curie, Knop y Farmaloop.',
};

interface Props {
  searchParams: {
    q?: string;
    page?: string;
    category?: string;
    chain?: string;
    inStock?: string;
    sort?: string;
    minPrice?: string;
    maxPrice?: string;
  };
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

const SORT_LABEL: Record<string, string> = {
  name: 'Nombre',
  price_asc: 'Precio: de menor a mayor',
  price_desc: 'Precio: de mayor a menor',
};

function SuggestionChips({ terms }: { terms: string[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {terms.map((term) => (
        <Link key={term} href={`/precios?q=${encodeURIComponent(term)}`} className="chip">
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
  const state = parsePrecios(searchParams);
  const filtered = hasActiveFilters(state);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6">
        <h1 className="display text-3xl font-bold text-foreground">
          Buscar un producto
        </h1>
        <p className="mt-1.5 max-w-2xl text-muted-foreground">
          Cada fila es un producto en una farmacia, con lo que cuesta ahí. Si lo
          vende más de una, la fila abre la comparación.
        </p>
        <p className="mt-2">
          <Link href="/comparar" className="link text-sm">
            Ver las mayores diferencias de precio →
          </Link>
        </p>
      </header>

      {/* A plain GET form, so search and filters keep working with JavaScript
          off and every combination is a shareable, indexable URL. */}
      <form action="/precios" method="get" className="mb-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            type="search"
            name="q"
            defaultValue={state.q}
            placeholder="Buscar: paracetamol, shampoo, protector solar…"
            className="flex-1 rounded-md border border-edge bg-card px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:border-foreground focus:outline-none"
            aria-label="Buscar producto"
          />
          <button type="submit" className="btn-solid">
            Buscar
          </button>
        </div>
        {/* Carried as a hidden field so searching again keeps the chosen
            category instead of silently dropping back to everything. */}
        {state.category && (
          <input type="hidden" name="category" value={state.category} />
        )}

        <Suspense fallback={null}>
          <FilterPanel state={state} open={filtered} />
        </Suspense>
      </form>

      <Suspense fallback={null}>
        <CategoryFilter state={state} />
      </Suspense>

      <Suspense fallback={null}>
        <ActiveFilters state={state} />
      </Suspense>

      {/* Keyed so a new search remounts the boundary and shows the skeleton
          again instead of leaving the previous results on screen. */}
      <Suspense
        key={`${state.q}|${state.page}|${state.category}|${state.chain}|${state.inStock}|${state.sort}|${state.minPrice}|${state.maxPrice}`}
        fallback={<ResultsSkeleton />}
      >
        <Results state={state} />
      </Suspense>

      <p className="mt-10 border-t border-edge pt-4 text-xs leading-relaxed text-muted-foreground">
        Cada tarjeta es un producto tal como lo publica esa farmacia. Los precios
        cambian durante el día: confirma en la farmacia antes de comprar. Ver también{' '}
        <Link href="/comparar" className="link">
          las mayores diferencias de precio
        </Link>
        .
      </p>
    </div>
  );
}

/**
 * Chain, stock, price range and order.
 *
 * All four were already implemented in the gateway and unreachable from the
 * site, so the listing could be narrowed by category and by nothing else. They
 * live inside the search form as real fields — no JavaScript, one submit — and
 * inside a `<details>` that opens itself whenever something is filtering, so a
 * narrowed result set never looks like an empty catalogue.
 */
async function FilterPanel({ state, open }: { state: PreciosState; open: boolean }) {
  const coverage = await getCoverage();
  const chains = coverage.filter((c) => c.productCount > 0 && c.chain);
  if (chains.length === 0) return null;

  const field =
    'w-full rounded-md border border-edge bg-card px-3 py-2 text-sm text-foreground focus:border-foreground focus:outline-none';

  return (
    <details open={open} className="panel mt-3 px-4 py-3">
      <summary className="cursor-pointer select-none text-sm font-semibold text-foreground marker:text-muted-foreground">
        Filtrar y ordenar
      </summary>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label
            htmlFor="filter-chain"
            className="label mb-1.5 block text-muted-foreground"
          >
            Farmacia
          </label>
          <select id="filter-chain" name="chain" defaultValue={state.chain} className={field}>
            <option value="">Todas</option>
            {chains.map((c: PharmacyCoverage) => (
              <option key={c.pharmacyId} value={c.chain ?? ''}>
                {shortPharmacy(c.name)} ({c.productCount.toLocaleString('es-CL')})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="filter-sort"
            className="label mb-1.5 block text-muted-foreground"
          >
            Ordenar por
          </label>
          <select id="filter-sort" name="sort" defaultValue={state.sort} className={field}>
            {Object.entries(SORT_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>

        <fieldset className="min-w-0">
          <legend className="label mb-1.5 text-muted-foreground">Precio (CLP)</legend>
          <div className="flex items-center gap-2">
            <input
              type="text"
              inputMode="numeric"
              name="minPrice"
              defaultValue={state.minPrice ?? ''}
              placeholder="Desde"
              aria-label="Precio desde"
              className={field}
            />
            <span aria-hidden className="text-muted-foreground">
              –
            </span>
            <input
              type="text"
              inputMode="numeric"
              name="maxPrice"
              defaultValue={state.maxPrice ?? ''}
              placeholder="Hasta"
              aria-label="Precio hasta"
              className={field}
            />
          </div>
        </fieldset>

        <div className="flex flex-col justify-end gap-3">
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              name="inStock"
              value="true"
              defaultChecked={state.inStock}
              className="h-4 w-4 rounded border-edge accent-[hsl(var(--ink))]"
            />
            Sólo con stock
          </label>
          <button type="submit" className="btn-quiet w-full">
            Aplicar
          </button>
        </div>
      </div>
    </details>
  );
}

/** One line saying what is narrowing the list, and how to undo it. */
async function ActiveFilters({ state }: { state: PreciosState }) {
  if (!state.q && !hasActiveFilters(state)) return null;

  const bits: string[] = [];
  if (state.chain) {
    // Named the way the chain names itself, not by its slug: `cruz_verde` is
    // our identifier, "Cruz Verde" is the shop the reader knows.
    const coverage = await getCoverage();
    const match = coverage.find((c) => c.chain === state.chain);
    bits.push(`en ${match ? shortPharmacy(match.name) : state.chain}`);
  }
  if (state.inStock) bits.push('sólo con stock');
  if (typeof state.minPrice === 'number') bits.push(`desde ${formatCLP(state.minPrice)}`);
  if (typeof state.maxPrice === 'number') bits.push(`hasta ${formatCLP(state.maxPrice)}`);
  if (state.sort !== 'name') bits.push(SORT_LABEL[state.sort].toLowerCase());

  return (
    <p className="mb-5 text-sm text-muted-foreground">
      {state.q && (
        <>
          Buscando <strong className="font-semibold text-foreground">“{state.q}”</strong>
        </>
      )}
      {state.q && bits.length > 0 && ' · '}
      {bits.join(' · ')}
      {' · '}
      <Link href="/precios" className="link">
        limpiar
      </Link>
    </p>
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
async function CategoryFilter({ state }: { state: PreciosState }) {
  const categories = await getCategories();
  if (categories.length === 0) return null;

  return (
    <nav aria-label="Filtrar por categoría" className="mb-5 flex flex-wrap gap-2">
      <Link
        href={preciosHref(state, { category: '' })}
        aria-current={!state.category ? 'page' : undefined}
        className={`chip ${!state.category ? 'chip-on' : ''}`}
      >
        Todo
      </Link>
      {categories.map((c) => {
        const active = state.category === c.id;
        return (
          <Link
            key={c.id}
            href={preciosHref(state, { category: active ? '' : c.id })}
            aria-current={active ? 'page' : undefined}
            className={`chip ${active ? 'chip-on' : ''}`}
          >
            {categoryLabel(c.id, c.name)}
            <span className={`figure ${active ? 'text-white/70' : 'text-muted-foreground'}`}>
              {c.productCount.toLocaleString('es-CL')}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

async function Results({ state }: { state: PreciosState }) {
  const configured = isLiveDataConfigured();
  const [data, coverage] = await Promise.all([
    searchProducts(state.q, state.page, 30, {
      category: state.category || undefined,
      chain: state.chain || undefined,
      inStock: state.inStock,
      minPrice: state.minPrice,
      maxPrice: state.maxPrice,
      sort: state.sort,
    }),
    getCoverage(),
  ]);

  const totalProducts = coverage.reduce((sum, c) => sum + c.productCount, 0);
  const activeChains = coverage.filter((c) => c.productCount > 0);

  if (!configured) {
    return (
      <div className="panel border-high/30 bg-high-tint p-6 text-high">
        <p className="font-semibold">No podemos consultar los precios ahora.</p>
        <p className="mt-1.5 text-sm">
          Este despliegue no tiene a dónde pedirlos. Preferimos decirlo antes que
          mostrar precios inventados.
        </p>
      </div>
    );
  }

  if (data.results.length === 0) {
    const filtered = hasActiveFilters(state);
    return (
      <div className="panel border-dashed p-10 text-center">
        <p className="text-lg font-semibold text-foreground">
          {state.q ? `Sin resultados para “${state.q}”` : 'Sin resultados'}
        </p>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
          {filtered
            ? 'Ningún producto cumple con todos los filtros. Prueba quitando uno.'
            : state.q
              ? 'Buscamos por el nombre tal como lo publica cada farmacia. Prueba con el principio activo (paracetamol) en vez de la marca, o con menos palabras.'
              : 'Los scrapers todavía no han entregado precios para esta consulta.'}
        </p>
        {filtered && (
          <p className="mt-4">
            <Link
              href={preciosHref(state, {
                category: '',
                chain: '',
                inStock: false,
                sort: 'name',
                minPrice: undefined,
                maxPrice: undefined,
              })}
              className="link text-sm"
            >
              Buscar “{state.q || 'todo'}” sin filtros →
            </Link>
          </p>
        )}
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
      {!state.q && !hasActiveFilters(state) && (
        <div className="mb-6 space-y-4">
          <SuggestionChips terms={SUGGESTIONS} />
          {activeChains.length > 0 && (
            <section>
              <h2 className="label mb-2 text-muted-foreground">
                Cobertura por farmacia · {totalProducts.toLocaleString('es-CL')} productos
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {activeChains.map((c) => (
                  <span
                    key={c.pharmacyId}
                    className="rounded-full border border-edge bg-card px-3 py-1 text-sm text-muted-foreground"
                  >
                    {shortPharmacy(c.name)}{' '}
                    <span className="figure font-semibold text-foreground">
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
        <p className="text-sm text-muted-foreground">
          <strong className="figure font-semibold text-foreground">
            {data.total.toLocaleString('es-CL')}
          </strong>{' '}
          {data.total === 1 ? 'resultado' : 'resultados'}
        </p>
        {data.totalPages > 1 && (
          <p className="text-sm text-muted-foreground">
            Página {state.page.toLocaleString('es-CL')} de{' '}
            {data.totalPages.toLocaleString('es-CL')}
          </p>
        )}
      </div>

      <ul className="divide-y divide-edge overflow-hidden rounded-xl border border-edge bg-card">
        {data.results.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </ul>

      {data.totalPages > 1 && (
        <nav
          className="mt-6 flex flex-wrap items-center justify-center gap-1.5"
          aria-label="Paginación de resultados"
        >
          {state.page > 1 ? (
            <Link
              href={preciosHref(state, { page: state.page - 1 })}
              rel="prev"
              className="chip"
            >
              ← Anterior
            </Link>
          ) : (
            <span className="chip opacity-40">← Anterior</span>
          )}

          <span className="hidden items-center gap-1.5 sm:flex">
            {pageWindow(state.page, data.totalPages).map((n, i) =>
              n === 'gap' ? (
                <span key={`gap-${i}`} className="px-1 text-sm text-muted-foreground">
                  …
                </span>
              ) : n === state.page ? (
                <span key={n} aria-current="page" className="chip chip-on figure">
                  {n}
                </span>
              ) : (
                <Link
                  key={n}
                  href={preciosHref(state, { page: n })}
                  className="chip figure"
                >
                  {n}
                </Link>
              ),
            )}
          </span>

          {state.page < data.totalPages ? (
            <Link
              href={preciosHref(state, { page: state.page + 1 })}
              rel="next"
              className="chip"
            >
              Siguiente →
            </Link>
          ) : (
            <span className="chip opacity-40">Siguiente →</span>
          )}
        </nav>
      )}
    </>
  );
}
