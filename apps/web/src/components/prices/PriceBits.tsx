import { chainTint, shortPharmacy, stockInfo } from '@/lib/pharmacy';

/**
 * The small, repeated pieces of price UI. All server components — none of them
 * needs state, so none of them costs the visitor a byte of JavaScript.
 *
 * They exist as one file because they only make sense together: a price, what
 * it was, who charges it, and whether you can actually buy it today.
 */

/**
 * A peso amount in the product's typographic voice: tabular digits so a column
 * of prices lines up digit for digit, and the currency symbol set small and
 * lifted so the magnitude lands first — you compare 209 against 413, not two
 * dollar signs.
 */
export function Price({
  value,
  className = '',
}: {
  value: number;
  className?: string;
}) {
  return (
    <span className={`figure whitespace-nowrap ${className}`}>
      <span className="figure-symbol">$</span>
      {value.toLocaleString('es-CL')}
    </span>
  );
}

/** The struck-through "before" price. Only rendered when it is a real drop. */
export function WasPrice({ value }: { value: number }) {
  return (
    <span className="text-sm text-gray-400 line-through">
      <span className="sr-only">Antes </span>${value.toLocaleString('es-CL')}
    </span>
  );
}

export function DiscountBadge({ percent }: { percent: number }) {
  return (
    <span className="rounded bg-save-tint px-1.5 py-0.5 text-xs font-semibold text-save">
      −{percent}%
    </span>
  );
}

const STOCK_CLASS = {
  ok: 'bg-save-tint text-save',
  low: 'bg-amber-50 text-amber-800',
  out: 'bg-high-tint text-high',
} as const;

export function StockBadge({ status }: { status: string | null | undefined }) {
  const { label, tone } = stockInfo(status);
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${STOCK_CLASS[tone]}`}
    >
      {label}
    </span>
  );
}

export function PharmacyChip({
  name,
  chain,
}: {
  name: string;
  chain?: string | null;
}) {
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-xs font-medium ${chainTint(chain)}`}
    >
      {shortPharmacy(name)}
    </span>
  );
}

/**
 * The price spread, drawn to scale.
 *
 * Track width is the highest price any pharmacy charges. The ink segment is
 * what you pay at the cheapest; the green remainder is, literally to scale, the
 * money you keep by not buying at the dearest. Intermediate offers are ticked
 * at their true position — without them a five-way comparison would read as a
 * two-way.
 */
export function SpreadBar({
  prices,
  large = false,
  animate = false,
}: {
  prices: number[];
  large?: boolean;
  animate?: boolean;
}) {
  const valid = prices.filter((p) => Number.isFinite(p) && p > 0);
  if (valid.length === 0) return null;

  const min = Math.min(...valid);
  const max = Math.max(...valid);
  if (max <= 0) return null;

  const floorPct = Math.min(100, (min / max) * 100);
  const ticks = Array.from(new Set(valid.filter((p) => p > min && p < max)));

  return (
    <div
      className={`spread-track rounded-full ${large ? 'spread-track--lg' : ''}`}
      role="img"
      aria-label={`El precio va de $${min.toLocaleString('es-CL')} a $${max.toLocaleString('es-CL')}`}
    >
      <div className="spread-floor" style={{ width: `${floorPct}%` }} />
      <div className={`spread-gap ${animate ? 'animate-spread' : ''}`} />
      {ticks.map((p) => (
        <span
          key={p}
          className="spread-tick"
          style={{ left: `${(p / max) * 100}%` }}
          aria-hidden
        />
      ))}
    </div>
  );
}
