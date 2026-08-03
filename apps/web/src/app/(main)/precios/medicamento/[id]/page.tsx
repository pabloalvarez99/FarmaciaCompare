import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { formatCLP, getComparisonByMedication } from '@/lib/api-products';
import { ComparisonDetail } from '@/components/prices/ComparisonDetail';

export const revalidate = 300;

interface Props {
  params: { id: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const group = await getComparisonByMedication(params.id);
  if (!group) return { title: 'Producto no encontrado — FarmaciaCompare' };

  const prices = (group.offers ?? []).map((o) => o.price).filter((p) => p > 0);
  const lowest = prices.length ? Math.min(...prices) : null;

  return {
    title: `${group.name} — precios comparados`,
    description: lowest
      ? `${group.name}: desde ${formatCLP(lowest)} comparando ${prices.length} farmacias online de Chile.`
      : `Compara el precio de ${group.name} entre farmacias online de Chile.`,
  };
}

/**
 * Catalog-linked comparison. The identity is medications.id — the only way Cruz
 * Verde, Salcobrand and Dr. Simi join a group, because those chains publish no
 * EAN, and therefore the path where the largest real gaps tend to show up.
 */
export default async function MedicationComparisonPage({ params }: Props) {
  const group = await getComparisonByMedication(params.id);
  if (!group) notFound();

  const offers = [...(group.offers ?? [])]
    .filter((o) => o.price > 0)
    .sort((a, b) => a.price - b.price);
  if (offers.length === 0) notFound();

  const stem = group.name.split(' ').slice(0, 2).join(' ');

  return (
    <ComparisonDetail
      group={group}
      offers={offers}
      backHref="/comparar"
      attribution={group.laboratory ?? undefined}
      basisNote="Agrupado contra el registro sanitario del ISP: mismo principio activo, misma concentración y misma presentación, aunque cada farmacia le ponga otro nombre."
      singleOfferNote="Hoy sólo una farmacia tiene este producto vinculado al catálogo, así que no hay nada que comparar todavía."
      relatedLinks={[
        { href: `/comparar?q=${encodeURIComponent(stem)}`, label: 'Ver comparaciones similares' },
        { href: `/precios?q=${encodeURIComponent(stem)}`, label: 'Ver cada farmacia por separado' },
      ]}
    />
  );
}
