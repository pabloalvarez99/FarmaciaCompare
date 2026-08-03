import Link from 'next/link';
import type { ComparisonGroup, ComparisonOffer } from '@/lib/api-products';
import { formatCLP } from '@/lib/api-products';
import {
  freshnessLabel,
  hasPackMismatch,
  isOutOfStock,
  newestTimestamp,
  shortPharmacy,
} from '@/lib/pharmacy';
import { ProductThumb } from './ProductThumb';
import { Price, SpreadBar } from './PriceBits';
import { OfferRow } from './OfferRow';
import { ChainPriceStrip } from './ChainPriceStrip';

/**
 * One product, every pharmacy that sells it, and where to buy it.
 *
 * The three comparison routes — EAN, catalog and derived identity — used to
 * carry three copies of this markup. They are the same page: only the evidence
 * differs, and the evidence is a sentence, not a layout. Three copies meant
 * three chances for the screens to disagree about something that matters, and
 * they already had: the out-of-stock warning, the pack check and the wording of
 * the footnote had each drifted.
 *
 * Everything that differs between the routes arrives as a prop.
 */
export interface ComparisonDetailProps {
  group: ComparisonGroup;
  /** Cheapest → dearest, already filtered to real prices. */
  offers: ComparisonOffer[];
  backHref: string;
  /** Attribution under the title: laboratory, brand or the barcode itself. */
  attribution?: React.ReactNode;
  /** Why these listings are considered the same product, in one sentence. */
  basisNote: string;
  /** What to say when only one pharmacy carries it today. */
  singleOfferNote: string;
  relatedLinks: { href: string; label: string }[];
}

export function ComparisonDetail({
  group,
  offers,
  backHref,
  attribution,
  basisNote,
  singleOfferNote,
  relatedLinks,
}: ComparisonDetailProps) {
  const cheapest = offers[0];
  const dearest = offers[offers.length - 1];

  // The offer someone can actually act on. When the cheapest listing is out of
  // stock, headlining it sends a person to a shop that cannot sell it — so the
  // verdict is built around the cheapest one that is available, and the
  // unavailable-but-cheaper listing is explained rather than quietly dropped.
  const available = offers.filter((o) => !isOutOfStock(o.stockStatus));
  const best = available[0] ?? cheapest;
  const cheapestIsGone = best !== cheapest;

  // The saving is measured from the price above it, not from the cheapest row
  // in the table. Those are the same number until the cheapest listing is out
  // of stock — and then quoting the gap to an unbuyable price under a headline
  // that says "más barato con stock" is two figures that do not belong to the
  // same purchase.
  const saving = dearest.price - best.price;
  const savingPct = dearest.price > 0 ? Math.round((saving / dearest.price) * 100) : 0;

  // Both ends of the range can sit in the same chain — one shop listing the
  // same product twice at very different prices. "76% menos que en Farmaloop"
  // while you are buying at Farmaloop reads as a mistake, so that case names
  // the price instead of the shop.
  const dearestIsSameShop = dearest.pharmacy === best.pharmacy;

  const chainCount = new Set(offers.map((o) => o.chain ?? o.pharmacy)).size;
  const updated = freshnessLabel(newestTimestamp(offers.map((o) => o.recordedAt)));
  const heroImage = offers.find((o) => o.imageUrl)?.imageUrl ?? null;
  const packMismatch = hasPackMismatch(offers.map((o) => o.productName));

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Link href={backHref} className="link text-sm">
        ← Volver a las comparaciones
      </Link>

      <div className="mt-4 flex items-start gap-4">
        <ProductThumb src={heroImage} alt={group.name} size={88} />
        <div className="min-w-0">
          <h1 className="display text-2xl font-bold leading-tight text-foreground">
            {group.name}
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {attribution && <>{attribution} · </>}
            {offers.length} {offers.length === 1 ? 'precio' : 'precios'} en {chainCount}{' '}
            {chainCount === 1 ? 'farmacia' : 'farmacias'}
            {updated && <> · {updated}</>}
          </p>
        </div>
      </div>

      {/* The verdict, above everything else: what you pay at best, where, and
          what not checking would have cost you. */}
      <section className="panel mt-6 p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="min-w-0">
            <h2 className="label text-muted-foreground">
              {cheapestIsGone ? 'Más barato con stock' : 'Más barato'}
            </h2>
            <Price
              value={best.price}
              className="mt-1 block text-4xl font-bold text-foreground sm:text-5xl"
            />
            <p className="mt-1 text-sm text-muted-foreground">
              en {shortPharmacy(best.pharmacy)}
            </p>
            {best.website && (
              <a
                href={best.website}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="btn-solid mt-3"
              >
                Ir a {shortPharmacy(best.pharmacy)} ↗
              </a>
            )}
          </div>

          {saving > 0 && (
            <div className="sm:text-right">
              <h2 className="label text-muted-foreground">Te ahorras</h2>
              <Price
                value={saving}
                className="mt-1 block text-3xl font-bold text-save sm:text-4xl"
              />
              <p className="mt-1 text-sm text-muted-foreground">
                {savingPct}% menos que{' '}
                {dearestIsSameShop
                  ? `el precio más alto de este producto (${formatCLP(dearest.price)})`
                  : `en ${shortPharmacy(dearest.pharmacy)} (${formatCLP(dearest.price)})`}
              </p>
            </div>
          )}
        </div>

        {saving > 0 && (
          <div className="mt-6">
            <SpreadBar prices={offers.map((o) => o.price)} large animate key={group.id} />
            <div className="mt-1.5 flex justify-between text-xs text-muted-foreground">
              <span>
                <span className="figure font-semibold text-foreground">
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
          <p className="mt-4 text-sm text-muted-foreground">{singleOfferNote}</p>
        )}
      </section>

      {cheapestIsGone && (
        <p className="mt-4 rounded-xl border border-high/30 bg-high-tint px-4 py-3 text-sm text-high">
          El precio más bajo del gráfico,{' '}
          <strong className="figure">{formatCLP(cheapest.price)}</strong> en{' '}
          <strong>{shortPharmacy(cheapest.pharmacy)}</strong>, está sin stock. Por eso
          arriba mostramos el más barato que sí puedes comprar hoy.
        </p>
      )}

      {/* Sits directly under the headline saving, not in the footnotes: when one
          of these listings is a multi-pack the big number above overstates the
          gap, and that caveat is worthless if you read it after deciding. */}
      {packMismatch && saving > 0 && (
        <p className="mt-3 rounded-xl border border-edge bg-muted px-4 py-3 text-sm text-foreground">
          Ojo: hay packs y unidades sueltas mezclados, así que la diferencia de arriba
          puede no ser real. Revisa el nombre de cada precio.
        </p>
      )}

      <ChainPriceStrip offers={offers} />

      <h2 className="label mb-3 mt-8 text-muted-foreground">
        Todas las farmacias, de más barata a más cara
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

      <p className="mt-8 border-t border-edge pt-4 text-xs leading-relaxed text-muted-foreground">
        {basisNote} Los precios cambian durante el día: confirma precio y stock en la
        farmacia antes de comprar. No damos consejo médico ni sugerimos reemplazos.
      </p>

      <p className="mt-6 flex flex-wrap gap-x-4 gap-y-2">
        {relatedLinks.map((link) => (
          <Link key={link.href} href={link.href} className="link text-sm">
            {link.label} →
          </Link>
        ))}
      </p>
    </div>
  );
}
