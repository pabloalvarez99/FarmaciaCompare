/**
 * Client for the scraped-price endpoints of the API gateway.
 *
 * These read `pharmacy_products` directly, so they return real prices even
 * while the curated `medications` catalog is still empty.
 */

export interface ScrapedProductResult {
  id: string;
  name: string;
  brand: string | null;
  laboratory: string | null;
  barcode: string | null;
  imageUrl?: string | null;
  medicationId: string | null;
  /**
   * Derived identity of the listing (`brand|size|words|qualifiers`). It is what
   * lets a cosmetics listing — no barcode, no catalog link — open a comparison
   * at all. Null when the evidence did not reach the threshold.
   */
  derivedGroupKey?: string | null;
  pharmacy: {
    id: string;
    name: string;
    chain: string | null;
    website: string | null;
  };
  price: number;
  originalPrice: number | null;
  discountPct: number | null;
  stockStatus: string | null;
  recordedAt: string;
}

export interface ProductSearchResponse {
  results: ScrapedProductResult[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface ComparisonOffer {
  pharmacy: string;
  chain: string | null;
  website: string | null;
  price: number;
  stockStatus: string | null;
  productName: string;
  imageUrl?: string | null;
  barcode?: string | null;
  recordedAt: string;
}

/**
 * How the offers were grouped into one comparable product.
 * - barcode: exact EAN identity published by the storefronts
 * - medication: matcher-linked catalog id (covers chains that publish no EAN)
 * - derived: identity built from the storefront's own title — brand, size and
 *   distinctive words. The only path that reaches cosmetics, hygiene and baby
 *   care, which have no registry to match against and almost no barcodes.
 */
export type MatchBasis = 'barcode' | 'medication' | 'derived';

/**
 * One product sold by more than one chain. Same envelope for all three grouping
 * paths so the UI can render any of them without branching on shape — only the
 * address (`barcode` / `medicationId` / `derivedGroupKey`) and the confidence
 * label differ.
 */
export interface ComparisonGroup {
  id: string;
  barcode: string | null;
  medicationId?: string | null;
  derivedGroupKey?: string | null;
  name: string;
  /**
   * Only the derived path fills this in, and it matters there: the chains that
   * drop the brand from the title are exactly the ones that path exists for.
   */
  brand?: string | null;
  laboratory?: string | null;
  pharmacyCount: number;
  lowestPrice: number;
  highestPrice: number;
  saving: number;
  savingPct: number;
  offers: ComparisonOffer[];
  matchBasis?: MatchBasis;
}

export interface ProductCategory {
  id: string;
  name: string;
  identityKey: string;
  position: number;
  productCount: number;
  pharmacyCount: number;
}

export interface PharmacyCoverage {
  pharmacyId: string;
  name: string;
  chain: string | null;
  website: string | null;
  productCount: number;
}

/** Physical or online pharmacy row (Places import + online storefronts). */
export interface PharmacyDirectoryEntry {
  id: string;
  name: string;
  chain: string | null;
  type: string;
  address: string | null;
  city: string | null;
  region: string | null;
  lat: string | number | null;
  lng: string | number | null;
  phone: string | null;
  website: string | null;
  rating: string | number | null;
  ratingCount: number | null;
}

const EMPTY: ProductSearchResponse = {
  results: [],
  total: 0,
  page: 1,
  limit: 20,
  totalPages: 0,
};

function apiBase(): string | null {
  const raw = process.env.NEXT_PUBLIC_API_URL;
  if (!raw) return null;
  // The var is sometimes set with the /api/v1 suffix already; normalise both.
  return raw.replace(/\/+$/, '').replace(/\/api\/v1$/, '');
}

export function isLiveDataConfigured(): boolean {
  return apiBase() !== null;
}

export const PRODUCT_SORTS = ['name', 'price_asc', 'price_desc'] as const;
export type ProductSort = (typeof PRODUCT_SORTS)[number];

/**
 * The filters `/products/search` accepts. Every one of them was already
 * implemented in the gateway and unused by this app, which is why the listing
 * could be narrowed by category and by nothing else.
 */
export interface ProductFilters {
  category?: string;
  chain?: string;
  inStock?: boolean;
  minPrice?: number;
  maxPrice?: number;
  sort?: ProductSort;
}

export async function searchProducts(
  query: string,
  page = 1,
  limit = 20,
  filters: ProductFilters = {},
): Promise<ProductSearchResponse> {
  const base = apiBase();
  if (!base) return EMPTY;

  // The gateway answers 400 for any parameter it does not know, so only the
  // documented set is ever sent — and only when it carries a value.
  const params = new URLSearchParams({
    q: query,
    page: String(page),
    limit: String(limit),
  });
  if (filters.category) params.set('category', filters.category);
  if (filters.chain) params.set('chain', filters.chain);
  if (filters.inStock) params.set('inStock', 'true');
  if (typeof filters.minPrice === 'number') params.set('minPrice', String(filters.minPrice));
  if (typeof filters.maxPrice === 'number') params.set('maxPrice', String(filters.maxPrice));
  if (filters.sort && filters.sort !== 'name') params.set('sort', filters.sort);

  try {
    // Prices move through the day; 5 minutes keeps the page fast without
    // showing figures that are meaningfully stale.
    const res = await fetch(`${base}/api/v1/products/search?${params.toString()}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return EMPTY;
    return (await res.json()) as ProductSearchResponse;
  } catch {
    return EMPTY;
  }
}


export async function getComparisons(
  query = '',
  limit = 12,
  minSaving = 0,
  groupBy: MatchBasis = 'barcode',
): Promise<ComparisonGroup[]> {
  const base = apiBase();
  if (!base) return [];

  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
    minSaving: String(minSaving),
  });
  if (groupBy !== 'barcode') params.set('groupBy', groupBy);

  const url = `${base}/api/v1/products/comparisons?${params.toString()}`;
  try {
    const res = await fetch(url, { next: { revalidate: 300 } });
    if (!res.ok) return [];
    return (await res.json()) as ComparisonGroup[];
  } catch {
    return [];
  }
}

export async function getComparison(barcode: string): Promise<ComparisonGroup | null> {
  const base = apiBase();
  if (!base) return null;

  try {
    const res = await fetch(`${base}/api/v1/products/comparisons/${encodeURIComponent(barcode)}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as ComparisonGroup;
  } catch {
    return null;
  }
}

/** One catalog-linked comparison, addressed by medications.id (uuid). */
export async function getComparisonByMedication(
  medicationId: string,
): Promise<ComparisonGroup | null> {
  const base = apiBase();
  if (!base) return null;

  const id = medicationId.trim();
  if (!id) return null;

  try {
    const res = await fetch(
      `${base}/api/v1/products/comparisons/medication/${encodeURIComponent(id)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as ComparisonGroup;
  } catch {
    return null;
  }
}

/**
 * One derived-identity comparison, addressed by its key.
 *
 * The key travels as a query parameter, not a path segment: it is assembled
 * from the brand the storefront published and can hold any character, `/`
 * included, which a path segment cannot carry reliably.
 */
export async function getComparisonByDerivedKey(
  key: string,
): Promise<ComparisonGroup | null> {
  const base = apiBase();
  if (!base) return null;

  const trimmed = key.trim();
  if (!trimmed) return null;

  try {
    const res = await fetch(
      `${base}/api/v1/products/comparisons/derived?key=${encodeURIComponent(trimmed)}`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return null;
    return (await res.json()) as ComparisonGroup;
  } catch {
    return null;
  }
}

/**
 * Canonical web path for a comparison group. Medication-linked groups cover
 * Cruz Verde / Salcobrand / Dr. Simi (no EAN); barcode groups keep the exact
 * EAN identity path; derived groups cover cosmetics and hygiene, which have
 * neither.
 */
export function comparisonHref(
  group: Pick<ComparisonGroup, 'barcode' | 'medicationId' | 'derivedGroupKey' | 'matchBasis'>,
): string | null {
  if (group.matchBasis === 'derived' || (!group.barcode && !group.medicationId && group.derivedGroupKey)) {
    return group.derivedGroupKey ? derivedHref(group.derivedGroupKey) : null;
  }
  if (group.matchBasis === 'medication' || (!group.barcode && group.medicationId)) {
    return group.medicationId
      ? `/precios/medicamento/${encodeURIComponent(group.medicationId)}`
      : null;
  }
  if (group.barcode) return `/precios/${encodeURIComponent(group.barcode)}`;
  if (group.medicationId) {
    return `/precios/medicamento/${encodeURIComponent(group.medicationId)}`;
  }
  if (group.derivedGroupKey) return derivedHref(group.derivedGroupKey);
  return null;
}

/**
 * `/precios/derivado?k=…`.
 *
 * A static segment under `/precios`, so Next matches it before the `[barcode]`
 * dynamic segment, and the key rides in the query string where a `/` inside it
 * is harmless.
 */
export function derivedHref(key: string): string {
  return `/precios/derivado?k=${encodeURIComponent(key)}`;
}

export async function getCoverage(): Promise<PharmacyCoverage[]> {
  const base = apiBase();
  if (!base) return [];

  try {
    const res = await fetch(`${base}/api/v1/products/coverage`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return [];
    return (await res.json()) as PharmacyCoverage[];
  } catch {
    return [];
  }
}

/**
 * The seven canonical categories with their live counts.
 *
 * Fetched rather than hardcoded so a category whose count changes — or a new
 * one — needs no web deploy. Categories with no priced listing are dropped:
 * a facet that leads to an empty page is worse than no facet.
 */
export async function getCategories(): Promise<ProductCategory[]> {
  const base = apiBase();
  if (!base) return [];

  try {
    const res = await fetch(`${base}/api/v1/products/categories`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return [];
    const rows = (await res.json()) as ProductCategory[];
    return rows.filter((c) => c.productCount > 0);
  } catch {
    return [];
  }
}

export async function getPharmacies(
  region = 'Coquimbo',
  city = '',
): Promise<PharmacyDirectoryEntry[]> {
  const base = apiBase();
  if (!base) return [];

  const params = new URLSearchParams();
  if (region) params.set('region', region);
  if (city) params.set('city', city);
  const qs = params.toString();
  const url = `${base}/api/v1/products/pharmacies${qs ? `?${qs}` : ''}`;
  try {
    const res = await fetch(url, { next: { revalidate: 600 } });
    if (!res.ok) return [];
    return (await res.json()) as PharmacyDirectoryEntry[];
  } catch {
    return [];
  }
}

export function formatCLP(value: number): string {
  return `$${value.toLocaleString('es-CL')}`;
}
