import { PRODUCT_SORTS, type ProductSort } from '@/lib/api-products';

/**
 * The state of the /precios listing, as it travels in the URL.
 *
 * Every control on that page is a plain GET field or a link, so each
 * combination of filters is an address someone can bookmark, share or hand to a
 * search engine — and the whole screen keeps working with JavaScript off.
 */
export interface PreciosState {
  q: string;
  category: string;
  chain: string;
  inStock: boolean;
  sort: ProductSort;
  minPrice?: number;
  maxPrice?: number;
  page: number;
}

function parseMoney(raw: string | undefined): number | undefined {
  if (raw === undefined) return undefined;
  // Chilean readers type `12.990`; the dot is thousands, never a decimal point.
  const digits = raw.replace(/[^\d]/g, '');
  if (!digits) return undefined;
  const value = Number(digits);
  return Number.isFinite(value) && value >= 0 ? value : undefined;
}

export function parsePrecios(searchParams: {
  q?: string;
  category?: string;
  chain?: string;
  inStock?: string;
  sort?: string;
  minPrice?: string;
  maxPrice?: string;
  page?: string;
}): PreciosState {
  const sortRaw = (searchParams.sort ?? '').trim() as ProductSort;
  const min = parseMoney(searchParams.minPrice);
  const max = parseMoney(searchParams.maxPrice);

  return {
    q: (searchParams.q ?? '').trim(),
    category: (searchParams.category ?? '').trim(),
    chain: (searchParams.chain ?? '').trim(),
    inStock: searchParams.inStock === 'true',
    sort: PRODUCT_SORTS.includes(sortRaw) ? sortRaw : 'name',
    minPrice: min,
    // An inverted range returns nothing and looks like a broken site rather
    // than a typo, so the ceiling is dropped instead.
    maxPrice: max !== undefined && min !== undefined && max < min ? undefined : max,
    page: Math.max(1, parseInt(searchParams.page ?? '1', 10) || 1),
  };
}

/**
 * A /precios URL with some of the state replaced.
 *
 * `page` resets unless the caller asks for one: changing a filter and landing
 * on page 7 of a shorter result set is how a listing shows an empty screen for
 * no visible reason.
 */
export function preciosHref(
  state: PreciosState,
  patch: Partial<PreciosState> = {},
): string {
  const next = { ...state, page: 1, ...patch };
  const params = new URLSearchParams();

  if (next.q) params.set('q', next.q);
  if (next.category) params.set('category', next.category);
  if (next.chain) params.set('chain', next.chain);
  if (next.inStock) params.set('inStock', 'true');
  if (next.sort && next.sort !== 'name') params.set('sort', next.sort);
  if (typeof next.minPrice === 'number') params.set('minPrice', String(next.minPrice));
  if (typeof next.maxPrice === 'number') params.set('maxPrice', String(next.maxPrice));
  if (next.page > 1) params.set('page', String(next.page));

  const qs = params.toString();
  return qs ? `/precios?${qs}` : '/precios';
}

/** True when anything narrows the listing beyond the free-text query. */
export function hasActiveFilters(state: PreciosState): boolean {
  return Boolean(
    state.category ||
      state.chain ||
      state.inStock ||
      state.sort !== 'name' ||
      typeof state.minPrice === 'number' ||
      typeof state.maxPrice === 'number',
  );
}
