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

/**
 * Human freshness for a price, in es-CL. `null` when the date is unusable.
 *
 * **`recordedAt` is when the price last *changed*, not when it was last
 * checked.** The writer only inserts a row when the figure moved, so a product
 * whose price has been stable for two days carries a two-day-old timestamp even
 * though a scraper confirmed it an hour ago — and every chain is scraped at
 * least every six hours.
 *
 * Reading that as staleness got the meaning backwards: "hace 2 días" on a price
 * verified this morning invites doubt about data that is current, and the
 * average across the catalogue is ~44 h precisely because most prices are
 * stable. So past a day the wording says what the number actually means — the
 * price has held — instead of implying nobody has looked.
 */
export function freshnessLabel(raw: string | null | undefined): string | null {
  const date = parseTimestamp(raw);
  if (!date) return null;

  const minutes = Math.round((Date.now() - date.getTime()) / 60_000);
  if (minutes < 2) return 'precio actualizado recién';
  if (minutes < 60) return `precio actualizado hace ${minutes} min`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `precio actualizado hace ${hours} h`;

  const days = Math.round(hours / 24);
  if (days === 1) return 'mismo precio desde ayer';
  if (days < 30) return `mismo precio hace ${days} días`;

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
 * Listings that mix a multipack with a single unit under one comparison.
 *
 * "Pack 3 x 75 ml" against "75 ml" is not a 66% saving, it is two different
 * things, and the headline number would be a lie in the only place the product
 * cannot afford one. The check is a heuristic on the titles each shop
 * published, so it warns rather than hides — and it lives here because all four
 * screens that render a comparison need exactly the same answer.
 *
 * `x 2`…`x 12` counts as a pack marker unless a unit follows it (`x 12 ml` is a
 * size, not a quantity of boxes).
 */
const PACK_MARKER = /\b(pack|kit|combo|x\s?([2-9]|1[0-2])\b(?!\s*m?[lg]))/i;

export function hasPackMismatch(productNames: string[]): boolean {
  if (productNames.length < 2) return false;
  const packed = productNames.filter((name) => PACK_MARKER.test(name)).length;
  return packed > 0 && packed < productNames.length;
}
