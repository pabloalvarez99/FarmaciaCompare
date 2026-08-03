/**
 * Presentation helpers shared by every screen that renders scraped prices.
 *
 * These used to be copy-pasted per page (`.replace(' (Online)', '')`, the stock
 * label map, the discount maths), which is how two screens end up disagreeing
 * about what "poco stock" is called.
 */

/** `Farmex (Online)` → `Farmex`. The suffix is a DB detail, not a brand. */
export function shortPharmacy(name: string | null | undefined): string {
  return (name ?? '').replace(/\s*\(online\)\s*$/i, '').trim();
}

export type StockTone = 'ok' | 'low' | 'out';

export interface StockInfo {
  label: string;
  tone: StockTone;
}

/**
 * Stock is only ever three states in the DB. Anything else the scrapers invent
 * is passed through verbatim rather than silently relabelled as "con stock":
 * on a price comparator, claiming availability you did not observe is the kind
 * of small lie that sends someone across town for nothing.
 */
export function stockInfo(status: string | null | undefined): StockInfo {
  switch (status) {
    case 'out_of_stock':
      return { label: 'Sin stock', tone: 'out' };
    case 'low_stock':
      return { label: 'Poco stock', tone: 'low' };
    case 'in_stock':
    case null:
    case undefined:
      return { label: 'Con stock', tone: 'ok' };
    default:
      return { label: status, tone: 'ok' };
  }
}

export function isOutOfStock(status: string | null | undefined): boolean {
  return status === 'out_of_stock';
}

/**
 * Percentage off, preferring the value the pharmacy publishes. Falls back to
 * the two prices when the scraper did not capture one, and returns null when
 * there is no real discount — so a "0%" badge can never render.
 */
export function discountPercent(
  price: number,
  originalPrice: number | null | undefined,
  published?: number | null,
): number | null {
  if (published && published > 0) return Math.round(published);
  if (!originalPrice || originalPrice <= price) return null;
  const pct = Math.round(((originalPrice - price) / originalPrice) * 100);
  return pct > 0 ? pct : null;
}

/**
 * Timestamps arrive in two shapes: Prisma serialises with a `Z`, the raw SQL
 * used by the comparison endpoints does not. Both are UTC, so an absent zone is
 * assumed UTC — parsing those as local time would shift every price four hours.
 */
export function parseTimestamp(raw: string | null | undefined): Date | null {
  if (!raw) return null;
  const zoned = /(?:z|[+-]\d{2}:?\d{2})$/i.test(raw);
  const date = new Date(zoned ? raw : `${raw}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Human freshness for a price, in es-CL. `null` when the date is unusable. */
export function freshnessLabel(raw: string | null | undefined): string | null {
  const date = parseTimestamp(raw);
  if (!date) return null;

  const minutes = Math.round((Date.now() - date.getTime()) / 60_000);
  if (minutes < 2) return 'recién actualizado';
  if (minutes < 60) return `hace ${minutes} min`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `hace ${hours} h`;

  const days = Math.round(hours / 24);
  if (days === 1) return 'ayer';
  if (days < 30) return `hace ${days} días`;

  return date.toLocaleDateString('es-CL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'America/Santiago',
  });
}

/** Newest of a set of timestamps — the freshness of a whole comparison. */
export function newestTimestamp(raws: Array<string | null | undefined>): string | null {
  let best: string | null = null;
  let bestMs = -Infinity;
  for (const raw of raws) {
    const date = parseTimestamp(raw);
    if (date && date.getTime() > bestMs) {
      bestMs = date.getTime();
      best = raw ?? null;
    }
  }
  return best;
}

/**
 * Chain tints for the home page only. Deliberately pale: the interface must
 * never look like it is endorsing a chain, and the only saturated colour on a
 * screen full of prices is reserved for the money (see globals.css).
 */
export const CHAIN_TINT: Record<string, string> = {
  cruz_verde: 'bg-green-50 text-green-800 border-green-100',
  salcobrand: 'bg-blue-50 text-blue-800 border-blue-100',
  ahumada: 'bg-orange-50 text-orange-800 border-orange-100',
  dr_simi: 'bg-yellow-50 text-yellow-800 border-yellow-100',
  farmex: 'bg-purple-50 text-purple-800 border-purple-100',
  curie: 'bg-pink-50 text-pink-800 border-pink-100',
  farmaloop: 'bg-teal-50 text-teal-800 border-teal-100',
  preunic: 'bg-rose-50 text-rose-800 border-rose-100',
  mercadofarma: 'bg-amber-50 text-amber-800 border-amber-100',
  knop: 'bg-lime-50 text-lime-800 border-lime-100',
};

export function chainTint(chain: string | null | undefined): string {
  return CHAIN_TINT[chain ?? ''] ?? 'bg-gray-50 text-gray-700 border-gray-200';
}
