import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { formatCLP, getComparisonByDerivedKey } from '@/lib/api-products';
import { ComparisonDetail } from '@/components/prices/ComparisonDetail';

export const revalidate = 300;

/**
 * The group is addressed by `?k=`, not by a path segment.
 *
 * The key is assembled from the brand each storefront published, so it can hold
 * any character — `/` included — and a path segment cannot carry that across
 * proxies that disagree about `%2F`. As a static segment under `/precios`, this
 * route also wins over `[barcode]` in Next's matcher, so the two never collide.
 */
interface Props {
  searchParams: { k?: string };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const group = await getComparisonByDerivedKey(searchParams.k ?? '');
  if (!group) return { title: 'Producto no encontrado — FarmaciaCompare' };

  const prices = (group.offers ?? []).map((o) => o.price).filter((p) => p > 0);
  const lowest = prices.length ? Math.min(...prices) : null;

  return {
    title: `${group.name} — precios comparados`,
    description: lowest
      ? `${group.name}: desde ${formatCLP(lowest)} comparando ${prices.length} farmacias online de Chile.`
      : `Compara el precio de ${group.name} entre farmacias online de Chile.`,
    // These pages are built from a heuristic identity, not from a registry.
    // They are worth showing to someone who clicked through from a listing; they
    // are not worth handing to Google as canonical product pages until the
    // grouping has more mileage.
    robots: { index: false, follow: true },
  };
}

/**
 * Derived-identity comparison: the identity is the product's own description —
 * brand, size and distinctive words — because cosmetics, hygiene and baby care
 * have no registry to match against and barely publish barcodes.
 */
export default async function DerivedComparisonPage({ searchParams }: Props) {
  const key = (searchParams.k ?? '').trim();
  const group = key ? await getComparisonByDerivedKey(key) : null;
  if (!group) notFound();

  const offers = [...(group.offers ?? [])]
    .filter((o) => o.price > 0)
    .sort((a, b) => a.price - b.price);
  if (offers.length === 0) notFound();

  const stem = group.brand ?? group.name.split(' ')[0];

  return (
    <ComparisonDetail
      group={group}
      offers={offers}
      backHref="/comparar?via=derivado"
      attribution={group.brand ?? undefined}
      basisNote="Agrupado por marca, tamaño y descripción: cosmética e higiene casi nunca traen código de barras y no existe un registro oficial para ellas en Chile. Revisa que los nombres describan el mismo producto."
      singleOfferNote="Hoy sólo una farmacia publica este producto con esta descripción, así que no hay nada que comparar todavía."
      relatedLinks={[
        {
          href: `/comparar?via=derivado&q=${encodeURIComponent(stem)}`,
          label: 'Ver comparaciones similares',
        },
        {
          href: `/precios?q=${encodeURIComponent(group.name.split(' ').slice(0, 2).join(' '))}`,
          label: 'Ver cada farmacia por separado',
        },
      ]}
    />
  );
}
