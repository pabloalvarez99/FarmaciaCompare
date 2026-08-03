import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { formatCLP, getComparison } from '@/lib/api-products';
import { ComparisonDetail } from '@/components/prices/ComparisonDetail';

export const revalidate = 300;

interface Props {
  params: { barcode: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const group = await getComparison(params.barcode);
  if (!group) return { title: 'Producto no encontrado — FarmaciaCompare' };

  const prices = (group.offers ?? []).map((o) => o.price).filter((p) => p > 0);
  const lowest = prices.length ? Math.min(...prices) : null;

  return {
    title: `${group.name} — precios comparados`,
    description: lowest
      ? `${group.name}: desde ${formatCLP(lowest)} comparando ${prices.length} precios en farmacias online de Chile.`
      : `Compara el precio de ${group.name} entre farmacias online de Chile.`,
  };
}

/**
 * Exact-identity comparison: every listing here carries the same EAN, which is
 * the strongest evidence the site has and the only one that needs no
 * interpretation.
 */
export default async function ComparisonPage({ params }: Props) {
  const group = await getComparison(params.barcode);
  if (!group) notFound();

  // The API orders by price, but this page's whole argument is "this one is the
  // cheapest", so it re-establishes the order itself rather than trusting it.
  const offers = [...(group.offers ?? [])]
    .filter((o) => o.price > 0)
    .sort((a, b) => a.price - b.price);
  if (offers.length === 0) notFound();

  const stem = group.name.split(' ').slice(0, 2).join(' ');

  return (
    <ComparisonDetail
      group={group}
      offers={offers}
      backHref="/comparar?via=barcode"
      attribution={
        group.barcode ? <span className="figure">{group.barcode}</span> : undefined
      }
      basisNote="Las dos farmacias publican este mismo código de barras, así que es la misma caja."
      singleOfferNote="Hoy sólo una farmacia publica este código de barras, así que no hay nada que comparar todavía."
      relatedLinks={[
        { href: `/precios?q=${encodeURIComponent(stem)}`, label: 'Ver productos similares' },
        { href: '/comparar', label: 'Mayores diferencias de precio' },
      ]}
    />
  );
}
