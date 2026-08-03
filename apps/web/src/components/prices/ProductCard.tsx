import Link from 'next/link';
import type { ScrapedProductResult } from '@/lib/api-products';
import { discountPercent, freshnessLabel, isOutOfStock } from '@/lib/pharmacy';
import { ProductThumb } from './ProductThumb';
import { DiscountBadge, PharmacyChip, Price, StockBadge, WasPrice } from './PriceBits';

/**
 * One scraped offer in the /precios listing.
 *
 * Deliberately not a table row. A table forces every column to exist at every
 * width, which on a phone means either a horizontally scrolling page or type
 * too small to read a price in. This is a flex card that reflows: image and
 * copy stack against the price on desktop, and the price drops under the copy
 * on narrow screens without anything overflowing.
 *
 * Prefer barcode (exact EAN identity) when present; otherwise medicationId so
 * chains without EAN still open a multi-chain comparison when linked.
 */
export function ProductCard({ product }: { product: ScrapedProductResult }) {
  const barcode = product.barcode?.trim();
  const medicationId = product.medicationId?.trim();
  const href = barcode
    ? `/precios/${encodeURIComponent(barcode)}`
    : medicationId
      ? `/precios/medicamento/${encodeURIComponent(medicationId)}`
      : null;

  const lab = product.laboratory ?? product.brand;
  const percent = discountPercent(product.price, product.originalPrice, product.discountPct);
  const soldOut = isOutOfStock(product.stockStatus);
  const updated = freshnessLabel(product.recordedAt);

  const body = (
    <div className="flex gap-3 p-3 sm:gap-4 sm:p-4">
      <ProductThumb
        src={product.imageUrl}
        alt=""
        size={72}
        className={soldOut ? 'opacity-60' : ''}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <p className="font-medium leading-snug text-gray-900">{product.name}</p>
          {lab && <p className="mt-0.5 truncate text-sm text-gray-500">{lab}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <PharmacyChip name={product.pharmacy.name} chain={product.pharmacy.chain} />
            <StockBadge status={product.stockStatus} />
            {updated && <span className="text-xs text-gray-400">{updated}</span>}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-baseline gap-x-2 gap-y-1 sm:flex-col sm:items-end sm:gap-1">
          <Price
            value={product.price}
            className={`text-xl font-semibold ${soldOut ? 'text-gray-400' : 'text-gray-900'}`}
          />
          {percent !== null && (
            <span className="flex items-center gap-2">
              {product.originalPrice ? <WasPrice value={product.originalPrice} /> : null}
              <DiscountBadge percent={percent} />
            </span>
          )}
          {href && (
            <span className="text-xs font-medium text-blue-600">Comparar precios →</span>
          )}
        </div>
      </div>
    </div>
  );

  if (!href) {
    return <li className="bg-white">{body}</li>;
  }

  return (
    <li className="bg-white transition-colors hover:bg-blue-50/40">
      <Link href={href} className="block focus-visible:relative">
        {body}
      </Link>
    </li>
  );
}
