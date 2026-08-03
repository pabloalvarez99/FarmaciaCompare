import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';
import { CATEGORIES } from '@/lib/categories';
import { getComparisons, getCoverage } from '@/lib/api-products';
import { chainTint, shortPharmacy } from '@/lib/pharmacy';
import { ComparisonGroupCard } from '@/components/prices/ComparisonGroupCard';
import { COQUIMBO_CITIES, REGION_LABEL } from '@/lib/regions';

// Everything on this page comes from scraped prices. Nothing is illustrative:
// showing invented figures on a price comparator would be the one lie the
// product cannot afford.
export const revalidate = 300;

const POPULAR_SEARCHES = [
  'Paracetamol', 'Ibuprofeno', 'Losartán', 'Omeprazol',
  'Metformina', 'Amoxicilina', 'Atorvastatina', 'Clonazepam',
];

const FEATURES = [
  {
    title: 'Precios reales de las cadenas',
    description:
      'Sacamos los precios de cada sitio web. No inventamos números: ves lo que cobran online hoy.',
    icon: '🔄',
  },
  {
    title: 'También sin código de barras',
    description:
      'Comparamos por catálogo (mismo medicamento y presentación) en Cruz Verde, Salcobrand, Dr. Simi y otras, aunque no tengan EAN.',
    icon: '🏷️',
  },
  {
    title: REGION_LABEL,
    description: `${COQUIMBO_CITIES.slice(0, 5).join(', ')} y más. Precios online con foco local y directorio de farmacias físicas.`,
    icon: '📍',
  },
  {
    title: 'Gratis y sin cuenta',
    description: 'Escribe el medicamento, compara y listo. Las alertas de precio llegan más adelante.',
    icon: '✨',
  },
];

export default async function HomePage() {
  // Catalog grouping first: more multi-chain groups and the only path that
  // includes chains without EAN — where the largest real savings often live.
  const [featured, coverage] = await Promise.all([
    getComparisons('', 6, 0, 'medication'),
    getCoverage(),
  ]);

  const totalProducts = coverage.reduce((sum, c) => sum + c.productCount, 0);
  const activeChains = coverage.filter((c) => c.productCount > 0);

  // No <main> wrapper here: (main)/layout.tsx already provides it, and a
  // document may only have one.
  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-b from-blue-50 via-white to-white">
        {/* No region eyebrow here: (main)/layout.tsx already sets the same line
            immediately above, and saying it twice in 60px reads as a bug. */}
        <div className="mx-auto max-w-3xl px-4 py-16 text-center sm:py-20">
          <h1 className="display mb-4 text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            Escribe un medicamento y mira{' '}
            <span className="text-blue-600">dónde sale más barato</span>
          </h1>
          <p className="mb-8 text-lg text-gray-600 sm:text-xl">
            Precios reales de cadenas online que despachan a domicilio. Foco en la{' '}
            {REGION_LABEL}: La Serena, Coquimbo y Ovalle.
          </p>

          <SearchBar size="lg" destination="comparar" />

          {/* Search is the fast path; these buttons skip typing. Primary =
              multi-chain savings; secondary = full listing browser. */}
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/comparar"
              className="rounded-lg bg-blue-600 px-6 py-2.5 font-medium text-white transition-colors hover:bg-blue-700"
            >
              Comparar precios
            </Link>
            <Link
              href="/precios"
              className="rounded-lg border border-gray-300 bg-white px-6 py-2.5 font-medium text-gray-700 transition-colors hover:bg-gray-50"
            >
              Buscar listados
            </Link>
          </div>

          <p className="mt-5 text-sm text-gray-500">
            {totalProducts > 0 ? (
              <>
                <span className="figure font-semibold text-gray-700">
                  {totalProducts.toLocaleString('es-CL')}
                </span>{' '}
                productos · {activeChains.length} cadenas online · precios actualizados hoy
              </>
            ) : (
              'Cargando precios…'
            )}
          </p>
        </div>
      </section>

      {/* Biggest price gaps — the product's whole argument, shown with real
          numbers before any marketing copy. Catalog path on purpose. */}
      <section className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h2 className="display text-2xl font-bold text-gray-900">
              Dónde hay más diferencia de precio
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Mismo producto del catálogo, distinta cadena — incluye cadenas sin código de
              barras.
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1 sm:flex-row sm:items-center sm:gap-3">
            <Link
              href="/comparar?minSaving=100000"
              className="text-sm font-medium text-save hover:underline"
            >
              Ahorro ≥ $100.000
            </Link>
            <Link
              href="/comparar"
              className="text-sm font-medium text-blue-600 hover:underline"
            >
              Ver todos →
            </Link>
          </div>
        </div>

        {featured.length === 0 ? (
          <p className="rounded-xl border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
            Todavía no hay comparaciones disponibles. Los precios individuales sí están en{' '}
            <Link href="/precios" className="text-blue-600 hover:underline">
              /precios
            </Link>
            .
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featured.map((group) => (
              <ComparisonGroupCard key={group.id} group={group} />
            ))}
          </div>
        )}
      </section>

      {/* Categories */}
      <section className="mx-auto max-w-5xl border-t px-4 py-10">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Buscar por categoría</h2>
          <Link href="/precios" className="text-sm text-blue-600 hover:underline">
            Ver todos →
          </Link>
        </div>
        {/* Categories are search shortcuts. They carry no counts or prices:
            those would need the medication catalog, which is not populated. */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {CATEGORIES.map((cat) => (
            <Link
              key={cat.id}
              href={`/precios?q=${encodeURIComponent(cat.label)}`}
              className="flex flex-col items-center gap-2 rounded-xl border bg-white p-4 text-center transition-all hover:border-blue-300 hover:shadow-sm"
            >
              <span className="text-2xl">{cat.emoji}</span>
              <p className="text-xs font-semibold leading-tight text-gray-800">{cat.label}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Popular searches */}
      <section className="mx-auto max-w-5xl border-t px-4 py-8">
        <h2 className="label mb-4 text-gray-400">Búsquedas populares</h2>
        <div className="flex flex-wrap gap-2">
          {POPULAR_SEARCHES.map((term) => (
            <Link
              key={term}
              href={`/comparar?q=${encodeURIComponent(term)}`}
              className="rounded-full bg-gray-100 px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-blue-50 hover:text-blue-700"
            >
              {term}
            </Link>
          ))}
        </div>
      </section>

      {/* Chains — online national scrapers; framing is Coquimbo-first */}
      <section className="mx-auto max-w-5xl px-4 py-8">
        <h2 className="label mb-2 text-gray-400">Cadenas online comparadas</h2>
        <p className="mb-4 text-sm text-gray-500">
          Precios recolectados de e-commerce que entregan a domicilio (cobertura nacional).
          Para locales físicos en la región, visita el{' '}
          <Link href="/farmacias" className="text-blue-600 hover:underline">
            directorio de farmacias
          </Link>
          .
        </p>
        {/* Listed from live coverage, so a chain only shows up once its
            scraper has actually delivered products. */}
        <div className="flex flex-wrap gap-2">
          {activeChains.map((chain) => (
            <span
              key={chain.pharmacyId}
              className={`rounded-full border px-4 py-2 text-sm font-medium ${chainTint(chain.chain)}`}
            >
              {shortPharmacy(chain.name)}{' '}
              <span className="figure opacity-70">
                {chain.productCount.toLocaleString('es-CL')}
              </span>
            </span>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-16">
        <div className="mx-auto max-w-5xl px-4">
          <h2 className="display mb-10 text-center text-2xl font-bold text-gray-900">
            ¿Por qué usar FarmaciaCompare?
          </h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {FEATURES.map((feature) => (
              <div key={feature.title} className="rounded-xl border border-gray-200 bg-white p-6">
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="mb-2 mt-3 font-semibold text-gray-900">{feature.title}</h3>
                <p className="text-sm leading-relaxed text-gray-500">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA — points at the working feature first. An account buys nothing
          today, so asking for one before showing the data would be backwards. */}
      <section className="mx-auto max-w-3xl px-4 py-16 text-center">
        <h2 className="display mb-3 text-2xl font-bold text-gray-900">
          Ahorra en medicamentos en la {REGION_LABEL}
        </h2>
        <p className="mb-6 text-gray-500">
          Compara {totalProducts > 0 ? `${totalProducts.toLocaleString('es-CL')} productos` : 'los precios'}{' '}
          de {activeChains.length || 'varias'} cadenas online sin crear una cuenta.
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link
            href="/comparar"
            className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white transition-colors hover:bg-blue-700"
          >
            Comparar precios
          </Link>
          <Link
            href="/registro"
            className="rounded-lg border border-gray-300 px-6 py-3 font-medium text-gray-700 transition-colors hover:bg-gray-50"
          >
            Crear cuenta gratis
          </Link>
        </div>
      </section>
    </>
  );
}
