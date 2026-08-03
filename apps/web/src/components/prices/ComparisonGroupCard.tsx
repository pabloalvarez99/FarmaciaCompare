import Link from 'next/link';
import {
  comparisonHref,
  type ComparisonGroup,
} from '@/lib/api-products';
import { shortPharmacy } from '@/lib/pharmacy';
import { ProductThumb } from './ProductThumb';
import { Price, SpreadBar } from './PriceBits';

/**
 * One multi-chain comparison in a savings-ranked list (home + /comparar).
 * Hero answer in ~1s: how much you save, and where it's cheapest.
 */
export function ComparisonGroupCard({ group }: { group: ComparisonGroup }) {
  const href = comparisonHref(group);
  const offers = group.offers ?? [];
  const cheapest = offers[0];
  const image = offers.find((o) => o.imageUrl)?.imageUrl ?? null;

  const n = group.pharmacyCount;
  const pharmacyLabel = `${n} ${n === 1 ? 'farmacia' : 'farmacias'}`;
  const basisLabel =
    group.matchBasis === 'barcode'
      ? 'mismo código de barras'
      : group.matchBasis === 'medication'
        ? 'incluye cadenas sin código de barras'
        : null;

  const body = (
    <>
      <div className="flex items-start gap-3">
        <ProductThumb src={image} alt="" size={48} />
        <div className="min-w-0">
          <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-gray-900 sm:line-clamp-3">
            {group.name}
          </h3>
          {group.laboratory && (
            <p className="mt-0.5 truncate text-xs text-gray-500">{group.laboratory}</p>
          )}
        </div>
      </div>

      {/* Ahorro first — the one number people came for */}
      <div className="mt-3">
        <p className="label text-save">Ahorro</p>
        <Price
          value={group.saving}
          className="block text-xl font-bold text-save sm:text-2xl"
        />
        {group.savingPct > 0 && (
          <p className="mt-0.5 text-xs font-medium text-save">{group.savingPct}% menos</p>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className="text-xs text-gray-500">Desde</span>
        <Price
          value={group.lowestPrice}
          className="text-base font-semibold text-gray-900 sm:text-lg"
        />
        {cheapest && (
          <span className="truncate text-xs text-gray-500">
            en {shortPharmacy(cheapest.pharmacy)}
          </span>
        )}
      </div>

      <div className="mt-3">
        <SpreadBar prices={offers.map((o) => o.price)} />
      </div>

      <p className="mt-2 text-xs text-gray-400">
        {pharmacyLabel}
        {basisLabel ? ` · ${basisLabel}` : null}
      </p>
    </>
  );

  if (!href) {
    return (
      <div className="flex h-full flex-col rounded-xl border border-gray-200 bg-white p-4">
        {body}
      </div>
    );
  }

  return (
    <Link
      href={href}
      className="flex h-full flex-col rounded-xl border border-gray-200 bg-white p-4 transition-all hover:border-blue-300 hover:shadow-sm"
    >
      {body}
    </Link>
  );
}
