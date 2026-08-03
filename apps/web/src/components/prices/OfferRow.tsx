import type { ComparisonOffer } from '@/lib/api-products';
import { formatCLP } from '@/lib/api-products';
import { freshnessLabel, isOutOfStock, shortPharmacy } from '@/lib/pharmacy';
import { ProductThumb } from './ProductThumb';
import { Price, StockBadge } from './PriceBits';

/** One pharmacy's offer on a comparison detail page. */
export function OfferRow({
  offer,
  delta,
  isCheapest,
  isDearest,
}: {
  offer: ComparisonOffer;
  delta: number;
  isCheapest: boolean;
  isDearest: boolean;
}) {
  const soldOut = isOutOfStock(offer.stockStatus);
  const updated = freshnessLabel(offer.recordedAt);
  const storeUrl = offer.website || null;

  const frame = isCheapest
    ? 'border-save bg-save-tint/50'
    : isDearest
      ? 'border-high/30 bg-card'
      : 'border-edge bg-card';

  const body = (
    <div className="flex gap-3 sm:gap-4">
      <ProductThumb
        src={offer.imageUrl}
        alt=""
        size={56}
        className={soldOut ? 'opacity-60' : ''}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-foreground">
              {shortPharmacy(offer.pharmacy)}
            </span>
            {isCheapest && (
              <span className="rounded bg-save px-1.5 py-0.5 text-xs font-semibold text-white">
                más barato
              </span>
            )}
            {isDearest && (
              <span className="rounded bg-high-tint px-1.5 py-0.5 text-xs font-semibold text-high">
                más caro
              </span>
            )}
          </div>

          <p className="mt-0.5 text-sm leading-snug text-muted-foreground">
            {offer.productName}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            <StockBadge status={offer.stockStatus} />
            {updated && (
              <span className="text-xs text-muted-foreground">{updated}</span>
            )}
            {storeUrl && (
              <span className="text-xs font-semibold text-foreground underline decoration-foreground/30 underline-offset-2">
                Ir a la farmacia ↗
              </span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-baseline gap-2 sm:flex-col sm:items-end sm:gap-0.5">
          <Price
            value={offer.price}
            className={`text-xl font-semibold ${soldOut ? 'text-muted-foreground' : 'text-foreground'}`}
          />
          {delta > 0 && (
            <span className="figure text-sm font-medium text-high">
              +{formatCLP(delta)}
            </span>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <li className={`rounded-xl border p-3 sm:p-4 ${frame}`}>
      {storeUrl ? (
        <a
          href={storeUrl}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="block rounded-lg transition-opacity hover:opacity-90"
          aria-label={`Ir a ${shortPharmacy(offer.pharmacy)}`}
        >
          {body}
        </a>
      ) : (
        body
      )}
    </li>
  );
}
