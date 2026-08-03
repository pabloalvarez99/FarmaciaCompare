import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';
import { categoryBlurb, categoryLabel } from '@/lib/categories';
import {
  formatCLP,
  getCategories,
  getComparisons,
  getCoverage,
  comparisonHref,
  type ComparisonGroup,
} from '@/lib/api-products';
import {
  freshnessLabel,
  hasPackMismatch,
  isOutOfStock,
  newestTimestamp,
  shortPharmacy,
} from '@/lib/pharmacy';
import { ComparisonGroupCard } from '@/components/prices/ComparisonGroupCard';
import { Price, SpreadBar } from '@/components/prices/PriceBits';
import { ProductThumb } from '@/components/prices/ProductThumb';

// Everything on this page comes from scraped prices. Nothing is illustrative:
// showing invented figures on a price comparator would be the one lie the
// product cannot afford.
export const revalidate = 300;

const POPULAR_SEARCHES = [
  'Paracetamol',
  'Losartán',
  'Omeprazol',
  'Metformina',
  'Atorvastatina',
];

/**
 * The three ways two listings are decided to be the same product, said the way
 * a person would say them.
 *
 * They used to be exposed as "Medicamentos / Belleza e higiene / Código de
 * barras" — a list that mixes what you are shopping for with how we matched it,
 * and asks the reader to care about the second. Here the evidence is the
 * subject, because on a health site the honest answer to "how do you know it is
 * the same box?" is the product.
 */
const EVIDENCE = [
  {
    title: 'Publican el mismo código de barras',
    body: 'Las dos farmacias declaran el mismo código. Es literalmente la misma caja, sin interpretación de por medio.',
    href: '/comparar?via=barcode',
    cta: 'Ver coincidencias exactas',
  },
  {
    title: 'Es el mismo remedio del registro sanitario',
    body: 'Cruz Verde, Salcobrand y Dr. Simi no publican código de barras. Los cruzamos contra el registro del ISP: mismo principio activo, misma concentración, misma presentación.',
    href: '/comparar',
    cta: 'Ver medicamentos',
  },
  {
    title: 'Coinciden marca, tamaño y descripción',
    body: 'Shampoo, pañales, cremas: no tienen registro ni código de barras. Los agrupamos por lo que publica cada tienda, y sólo cuando las tres cosas calzan. Muchos quedan sin comparar, y preferimos eso a juntar dos productos distintos.',
    href: '/comparar?via=derivado',
    cta: 'Ver belleza, higiene y bebé',
  },
] as const;

/**
 * The largest price gap we can vouch for right now.
 *
 * Two groups get skipped rather than headlined, and both for the same reason —
 * the front page is the one screen where the number has to survive being read
 * at 48px with no context:
 *
 * - listings that mix a multipack with a single unit, where the difference is
 *   real arithmetic on two different things;
 * - a cheapest offer that is out of stock, which would send the first-time
 *   visitor to a shop that cannot sell it.
 *
 * The detail pages handle both cases with a warning. The front page does not
 * get to explain itself, so it picks something that needs no explanation.
 */
function pickHeadline(groups: ComparisonGroup[]): ComparisonGroup | null {
  for (const group of groups) {
    const offers = [...(group.offers ?? [])].sort((a, b) => a.price - b.price);
    if (offers.length < 2 || group.saving <= 0) continue;
    if (isOutOfStock(offers[0].stockStatus)) continue;
    if (hasPackMismatch(offers.map((o) => o.productName))) continue;
    return group;
  }
  return null;
}

export default async function HomePage() {
  // Catalog grouping first: more multi-chain groups and the only path that
  // includes chains without EAN — where the largest real savings often live.
  // Seven, so the headline can be dropped and six cards still fill the grid.
  const [groups, coverage, categories] = await Promise.all([
    getComparisons('', 7, 0, 'medication'),
    getCoverage(),
    getCategories(),
  ]);

  const headline = pickHeadline(groups);
  const rest = groups.filter((g) => g.id !== headline?.id).slice(0, 6);

  const totalProducts = coverage.reduce((sum, c) => sum + c.productCount, 0);
  const activeChains = coverage.filter((c) => c.productCount > 0);

  // No <main> wrapper here: (main)/layout.tsx already provides it, and a
  // document may only have one.
  return (
    <>
      {/* Hero. The thesis is not a slogan about saving money, it is the
          largest gap on the site today, drawn to scale and named. */}
      <section className="mx-auto max-w-5xl px-4 pb-4 pt-10 sm:pt-14">
        <p className="label text-muted-foreground">
          Farmacias online de Chile · precios de hoy
        </p>
        <h1 className="display mt-3 max-w-2xl text-3xl font-bold leading-[1.1] tracking-tight text-foreground sm:text-4xl">
          El mismo producto no cuesta lo mismo en cada farmacia.
          <span className="block text-save">Acá ves cuánto cambia.</span>
        </h1>
        <p className="mt-4 max-w-xl text-muted-foreground">
          Buscamos tu producto en{' '}
          {activeChains.length > 0 ? (
            <span className="figure font-semibold text-foreground">
              {activeChains.length}
            </span>
          ) : (
            'todas las'
          )}{' '}
          cadenas online y te mostramos el precio de cada una, con la farmacia al
          lado. Sin cuenta y sin costo.
        </p>

        <div className="mt-6 max-w-xl">
          <SearchBar size="lg" destination="comparar" />
          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
            <span className="text-sm text-muted-foreground">Prueba con</span>
            {POPULAR_SEARCHES.map((term) => (
              <Link
                key={term}
                href={`/comparar?q=${encodeURIComponent(term)}`}
                className="text-sm font-medium text-foreground underline decoration-foreground/25 underline-offset-2 hover:decoration-foreground"
              >
                {term}
              </Link>
            ))}
          </div>
        </div>
      </section>

      {headline && <HeadlineGap group={headline} />}

      {/* The rest of the gaps. Same grouping as the headline, so the jump from
          one to the other is not a change of subject. */}
      {rest.length > 0 && (
        <section className="mx-auto max-w-5xl px-4 py-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="display text-2xl font-bold text-foreground">
                Otras diferencias grandes hoy
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Mismo remedio del registro sanitario, distinta farmacia.
              </p>
            </div>
            <Link href="/comparar" className="link text-sm">
              Ver todas →
            </Link>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {rest.map((group) => (
              <ComparisonGroupCard key={group.id} group={group} />
            ))}
          </div>
        </section>
      )}

      {groups.length === 0 && (
        <section className="mx-auto max-w-5xl px-4 py-10">
          <p className="panel border-dashed p-8 text-center text-sm text-muted-foreground">
            Ahora mismo no podemos armar comparaciones. Los precios de cada
            farmacia sí están en{' '}
            <Link href="/precios" className="link">
              buscar un producto
            </Link>
            .
          </p>
        </section>
      )}

      {/* Categories, with the counts the classifier actually produced. */}
      {categories.length > 0 && (
        <section className="mx-auto max-w-5xl border-t border-edge px-4 py-10">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <h2 className="display text-2xl font-bold text-foreground">
              Qué puedes comparar
            </h2>
            <Link href="/precios" className="link text-sm">
              Buscar en todo →
            </Link>
          </div>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {categories.map((cat) => {
              const blurb = categoryBlurb(cat.id);
              return (
                <li key={cat.id}>
                  <Link
                    href={`/precios?category=${encodeURIComponent(cat.id)}`}
                    className="panel flex h-full flex-col justify-between gap-3 p-4 transition-colors hover:border-foreground/30"
                  >
                    <div>
                      <p className="font-semibold text-foreground">
                        {categoryLabel(cat.id, cat.name)}
                      </p>
                      {blurb && (
                        <p className="mt-1 text-sm text-muted-foreground">{blurb}</p>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      <span className="figure font-semibold text-foreground">
                        {cat.productCount.toLocaleString('es-CL')}
                      </span>{' '}
                      productos en {cat.pharmacyCount}{' '}
                      {cat.pharmacyCount === 1 ? 'farmacia' : 'farmacias'}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
          {/* Said out loud, because leaving it out is how a comparator starts
              implying its coverage is complete. */}
          <p className="mt-4 text-sm text-muted-foreground">
            No todo producto queda clasificado. Los que ninguna cadena describe con
            claridad no entran en una categoría inventada: aparecen igual al buscar
            sin filtro.
          </p>
        </section>
      )}

      {/* How we know it is the same product. This is the hard part of the
          product, so it gets said plainly instead of hidden behind a tab. */}
      <section className="border-t border-edge bg-muted/40 py-12">
        <div className="mx-auto max-w-5xl px-4">
          <h2 className="display text-2xl font-bold text-foreground">
            Cómo sabemos que es el mismo producto
          </h2>
          <p className="mt-2 max-w-2xl text-muted-foreground">
            Cada farmacia le pone el nombre que quiere al mismo remedio. Juntar dos
            que no son iguales sería peor que no juntar nada, así que sólo
            comparamos cuando hay una de estas tres evidencias.
          </p>
          <ul className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
            {EVIDENCE.map((item) => (
              <li key={item.href} className="panel flex flex-col p-5">
                <h3 className="font-semibold leading-snug text-foreground">
                  {item.title}
                </h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
                  {item.body}
                </p>
                <Link href={item.href} className="link mt-4 text-sm">
                  {item.cta} →
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* Coverage. Neutral chips: the interface never looks like it is
          endorsing a chain. */}
      {activeChains.length > 0 && (
        <section className="mx-auto max-w-5xl px-4 py-12">
          <h2 className="display text-2xl font-bold text-foreground">
            Dónde miramos
          </h2>
          <p className="mt-2 text-muted-foreground">
            <span className="figure font-semibold text-foreground">
              {totalProducts.toLocaleString('es-CL')}
            </span>{' '}
            productos con precio, recogidos de las tiendas online de estas cadenas.
            Despachan a todo Chile; no es el stock de un local en particular.
          </p>
          <ul className="mt-5 flex flex-wrap gap-2">
            {activeChains.map((chain) => (
              <li
                key={chain.pharmacyId}
                className="rounded-full border border-edge bg-card px-3.5 py-1.5 text-sm text-foreground"
              >
                {shortPharmacy(chain.name)}{' '}
                <span className="figure text-muted-foreground">
                  {chain.productCount.toLocaleString('es-CL')}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-5 text-sm text-muted-foreground">
            ¿Buscas un local para ir a comprar?{' '}
            <Link href="/farmacias" className="link">
              Farmacias de la Región de Coquimbo
            </Link>
            .
          </p>
        </section>
      )}
    </>
  );
}

/**
 * The signature: today's widest price gap, drawn to scale.
 *
 * The track is as wide as the dearest price; the ink segment is what the
 * cheapest pharmacy charges, and the green remainder is the money you keep by
 * checking. It is the same drawing used on every card and every detail page,
 * given room to be read once.
 */
function HeadlineGap({ group }: { group: ComparisonGroup }) {
  const offers = [...(group.offers ?? [])].sort((a, b) => a.price - b.price);
  const cheapest = offers[0];
  const dearest = offers[offers.length - 1];
  const href = comparisonHref(group);
  const updated = freshnessLabel(newestTimestamp(offers.map((o) => o.recordedAt)));
  const image = offers.find((o) => o.imageUrl)?.imageUrl ?? null;

  return (
    <section className="mx-auto max-w-5xl px-4 pb-6">
      <article className="panel overflow-hidden">
        <div className="border-b border-edge bg-muted/50 px-5 py-3 sm:px-6">
          <p className="label text-save">La mayor diferencia de hoy</p>
        </div>

        <div className="p-5 sm:p-6">
          <div className="flex items-start gap-4">
            <ProductThumb src={image} alt="" size={56} />
            <div className="min-w-0">
              <h2 className="display text-lg font-bold leading-snug text-foreground sm:text-xl">
                {group.name}
              </h2>
              {group.laboratory && (
                <p className="mt-0.5 text-sm text-muted-foreground">
                  {group.laboratory}
                </p>
              )}
            </div>
          </div>

          <div className="mt-6 grid gap-6 sm:grid-cols-[1fr_auto] sm:items-end">
            <div className="min-w-0">
              <SpreadBar prices={offers.map((o) => o.price)} large animate />
              <dl className="mt-3 flex flex-wrap justify-between gap-x-6 gap-y-2">
                <div className="min-w-0">
                  <dt className="text-xs text-muted-foreground">
                    Más barato en {shortPharmacy(cheapest.pharmacy)}
                  </dt>
                  <dd>
                    <Price
                      value={cheapest.price}
                      className="text-xl font-bold text-foreground"
                    />
                  </dd>
                </div>
                <div className="min-w-0 sm:text-right">
                  <dt className="text-xs text-muted-foreground">
                    Más caro en {shortPharmacy(dearest.pharmacy)}
                  </dt>
                  <dd>
                    <Price
                      value={dearest.price}
                      className="text-xl font-semibold text-high"
                    />
                  </dd>
                </div>
              </dl>
            </div>

            <div className="shrink-0 border-t border-edge pt-4 sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0">
              <p className="label text-save">Diferencia</p>
              <Price
                value={group.saving}
                className="mt-1 block text-4xl font-bold leading-none text-save sm:text-5xl"
              />
              {group.savingPct > 0 && (
                <p className="mt-2 text-sm font-medium text-save">
                  {group.savingPct}% menos · {formatCLP(cheapest.price)} en vez de{' '}
                  {formatCLP(dearest.price)}
                </p>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-3">
            {href && (
              <Link href={href} className="btn-solid">
                Ver las {group.pharmacyCount} farmacias
              </Link>
            )}
            <p className="text-xs text-muted-foreground">
              Mismo remedio del registro sanitario
              {updated ? ` · ${updated}` : ''} · confirma en la farmacia antes de
              comprar
            </p>
          </div>
        </div>
      </article>
    </section>
  );
}
