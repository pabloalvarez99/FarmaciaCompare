import type { ComparisonOffer } from '@/lib/api-products';
import { isOutOfStock, shortPharmacy } from '@/lib/pharmacy';
import { Price } from './PriceBits';

/**
 * Compact horizontal scan of every chain's price — sits above the full offer
 * list so on mobile you see the spread without scrolling each row.
 * Expects offers already sorted cheapest → dearest.
 */
export function ChainPriceStrip({
  offers,
}: {
  offers: ComparisonOffer[];
}) {
  if (offers.length < 2) return null;

  const cheapest = offers[0]?.price ?? 0;

  return (
    <div className="mt-6 -mx-1">
      <p className="label mb-2 px-1 text-gray-400">En cada farmacia</p>
      <ul
        className="flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:thin]"
        aria-label="Precios en cada farmacia"
      >
        {offers.map((offer, i) => {
          const soldOut = isOutOfStock(offer.stockStatus);
          const isCheapest = i === 0;
          const isDearest = i === offers.length - 1 && offers.length > 2;

          return (
            <li
              key={`${offer.chain ?? offer.pharmacy}-${offer.price}-${i}`}
              className={`shrink-0 rounded-lg border px-3 py-2 ${
                isCheapest
                  ? 'border-save bg-save-tint/40'
                  : isDearest
                    ? 'border-high/25 bg-white'
                    : 'border-gray-200 bg-white'
              } ${soldOut ? 'opacity-60' : ''}`}
            >
              <p className="max-w-[7.5rem] truncate text-xs font-medium text-gray-700">
                {shortPharmacy(offer.pharmacy)}
              </p>
              <Price
                value={offer.price}
                className={`mt-0.5 block text-sm font-semibold ${
                  soldOut ? 'text-gray-400' : isCheapest ? 'text-save' : 'text-gray-900'
                }`}
              />
              {offer.price > cheapest && (
                <p className="figure mt-0.5 text-[11px] text-high">
                  +${(offer.price - cheapest).toLocaleString('es-CL')}
                </p>
              )}
              {isCheapest && (
                <p className="mt-0.5 text-[11px] font-medium text-save">más barato</p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
