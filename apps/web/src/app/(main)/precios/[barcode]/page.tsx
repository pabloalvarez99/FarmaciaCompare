import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { formatCLP, getComparison } from '@/lib/api-products';
import {
  freshnessLabel,
  isOutOfStock,
  newestTimestamp,
  shortPharmacy,
} from '@/lib/pharmacy';
import { ProductThumb } from '@/components/prices/ProductThumb';
import { Price, SpreadBar } from '@/components/prices/PriceBits';
import { OfferRow } from '@/components/prices/OfferRow';
import { ChainPriceStrip } from '@/components/prices/ChainPriceStrip';

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
      ? `${group.name}: desde ${formatCLP(lowest)} comparando ${prices.length} ofertas en farmacias online de Chile.`
      : `Compara el precio de ${group.name} entre farmacias online de Chile.`,
  };
}

export default async function ComparisonPage({ params }: Props) {
  const group = await getComparison(params.barcode);
  if (!group) notFound();

  // The API orders by price, but this page's whole argument is "this one is the
  // cheapest", so it re-establishes the order itself rather than trusting it.
  const offers = [...(group.offers ?? [])]
    .filter((o) => o.price > 0)
    .sort((a, b) => a.price - b.price);
  if (offers.length === 0) notFound();

  const cheapest = offers[0];
  const dearest = offers[offers.length - 1];
  const saving = dearest.price - cheapest.price;
  const savingPct = dearest.price > 0 ? Math.round((saving / dearest.price) * 100) : 0;

  // The cheapest listing is not always one you can buy. When it is out of
  // stock, the cheapest *available* offer is the number that actually helps.
  const available = offers.filter((o) => !isOutOfStock(o.stockStatus));
  const bestAvailable = available[0];
  const cheapestIsGone = isOutOfStock(cheapest.stockStatus) && Boolean(bestAvailable);

  const chainCount = new Set(offers.map((o) => o.chain ?? o.pharmacy)).size;
  const updated = freshnessLabel(newestTimestamp(offers.map((o) => o.recordedAt)));
  const heroImage = offers.find((o) => o.imageUrl)?.imageUrl ?? null;

  /*
   * Same EAN, but one listing is a multi-pack: then the headline "saving" is
   * comparing one box against three and is not a saving at all.
   *
   * The test is a pack marker, not merely different wording — the chains phrase
   * the same product a dozen ways ("Algiafin Jarabe 60 mL" vs "Algiafin
   * Paracetamol 120 mg / 5 mL x 60 mL"), and warning on every one of those
   * would train people to ignore the warning that matters. `x1` and volumes
   * like "x 60 mL" are deliberately excluded.
   */
  const packMarker = /\b(pack|kit|combo|x\s?([2-9]|1[0-2])\b(?!\s*m?[lg]))/i;
  const packed = offers.filter((o) => packMarker.test(o.productName));
  const packMismatch = packed.length > 0 && packed.length < offers.length;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Link
        href="/comparar"
        className="inline-flex text-sm text-blue-600 transition-colors hover:text-blue-800 hover:underline"
      >
        ← Comparar precios
      </Link>

      <div className="mt-4 flex items-start gap-4">
        <ProductThumb src={heroImage} alt={group.name} size={88} />
        <div className="min-w-0">
          <h1 className="display text-2xl font-bold leading-tight text-gray-900">
            {group.name}
          </h1>
          <p className="mt-1.5 text-sm text-gray-500">
            {group.barcode && (
              <>
                <span className="figure">{group.barcode}</span> ·{' '}
              </>
            )}
            {offers.length} {offers.length === 1 ? 'oferta' : 'ofertas'} en {chainCount}{' '}
            {chainCount === 1 ? 'cadena' : 'cadenas'}
            {updated && <> · actualizado {updated}</>}
          </p>
        </div>
      </div>

      {/* The verdict, above everything else: what you pay at best, and what
          not checking would have cost you. */}
      <section className="mt-6 rounded-2xl border border-gray-200 bg-white p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div>
            <h2 className="label text-gray-500">Más barato</h2>
            <Price
              value={cheapest.price}
              className="mt-1 block text-4xl font-bold text-gray-900 sm:text-5xl"
            />
            <p className="mt-1 text-sm text-gray-600">
              en {shortPharmacy(cheapest.pharmacy)}
            </p>
          </div>

          {saving > 0 && (
            <div className="sm:text-right">
              <h2 className="label text-gray-500">Te ahorras</h2>
              <Price
                value={saving}
                className="mt-1 block text-3xl font-bold text-save sm:text-4xl"
              />
              <p className="mt-1 text-sm text-gray-600">
                {savingPct}% menos que en {shortPharmacy(dearest.pharmacy)} (
                {formatCLP(dearest.price)})
              </p>
            </div>
          )}
        </div>

        {saving > 0 && (
          <div className="mt-6">
            <SpreadBar
              prices={offers.map((o) => o.price)}
              large
              animate
              key={group.barcode}
            />
            <div className="mt-1.5 flex justify-between text-xs text-gray-500">
              <span>
                <span className="figure font-semibold text-gray-900">
                  {formatCLP(cheapest.price)}
                </span>{' '}
                mínimo
              </span>
              <span>
                máximo{' '}
                <span className="figure font-semibold text-high">
                  {formatCLP(dearest.price)}
                </span>
              </span>
            </div>
          </div>
        )}

        {offers.length === 1 && (
          <p className="mt-4 text-sm text-gray-600">
            Hoy solo una farmacia publica este código de barras, así que no hay nada que
            comparar todavía.
          </p>
        )}
      </section>

      {cheapestIsGone && (
        <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          El precio más bajo está <strong>sin stock</strong>. El más barato que sí puedes
          comprar es{' '}
          <strong className="figure">{formatCLP(bestAvailable.price)}</strong> en{' '}
          <strong>{shortPharmacy(bestAvailable.pharmacy)}</strong>.
        </p>
      )}

      {/* Sits directly under the headline saving, not in the footnotes: when one
          of these listings is a multi-pack the big number above overstates the
          gap, and that caveat is worthless if you read it after deciding. */}
      {packMismatch && saving > 0 && (
        <p className="mt-3 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
          Ojo: hay packs y unidades sueltas mezclados — el ahorro de arriba puede no ser
          real. Revisa el nombre de cada oferta.
        </p>
      )}

      <ChainPriceStrip offers={offers} />

      <h2 className="label mt-8 mb-3 text-gray-500">
        Todas las ofertas, de menor a mayor
      </h2>

      <ul className="space-y-2">
        {offers.map((offer, i) => (
          <OfferRow
            key={`${offer.chain ?? offer.pharmacy}-${offer.price}-${i}`}
            offer={offer}
            delta={offer.price - cheapest.price}
            isCheapest={i === 0}
            isDearest={offers.length > 2 && i === offers.length - 1}
          />
        ))}
      </ul>

      <p className="mt-8 border-t border-gray-200 pt-4 text-xs leading-relaxed text-gray-500">
        Mismo código de barras. Confirma precio y stock en la farmacia antes de comprar.
      </p>

      <p className="mt-6 flex flex-wrap gap-x-4 gap-y-2">
        <Link
          href={`/precios?q=${encodeURIComponent(group.name.split(' ').slice(0, 2).join(' '))}`}
          className="text-sm text-blue-600 hover:underline"
        >
          Ver productos similares →
        </Link>
        <Link href="/comparar" className="text-sm text-blue-600 hover:underline">
          Mayores diferencias →
        </Link>
      </p>
    </div>
  );
}
