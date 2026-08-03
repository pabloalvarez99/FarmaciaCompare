import { Injectable } from '@nestjs/common';
import { Prisma, prisma } from '@farmacia/database';

/** Sort keys accepted by `search()`. `name` is the historical default. */
export type ProductSort = 'name' | 'price_asc' | 'price_desc';

export const PRODUCT_SORTS: readonly ProductSort[] = ['name', 'price_asc', 'price_desc'];

/**
 * Optional narrowing for `search()`. Every field is optional and omitting all of
 * them reproduces the pre-filter behaviour exactly.
 */
export interface ProductSearchFilters {
  /** Pharmacy chain slugs (`cruz_verde`, `salcobrand`, …). Empty = every chain. */
  chains?: string[];
  /** Keep only offers the storefront reports as in stock (`in_stock`/`low_stock`). */
  inStock?: boolean;
  /** Inclusive price floor, in CLP. */
  minPrice?: number;
  /** Inclusive price ceiling, in CLP. */
  maxPrice?: number;
  /**
   * Canonical category slugs (`medicamento`, `cosmetica`, …). Empty = every
   * category, including the listings that have none.
   *
   * A null `category_id` means no chain evidence was good enough to classify
   * the listing — it is an honest "we do not know", not a category. Asking for
   * a category therefore excludes them rather than sweeping them into whichever
   * one was requested.
   */
  categories?: string[];
  sort?: ProductSort;
}

/** Shape of every row both search plans return, so one mapper covers both. */
interface SearchRow {
  id: string;
  raw_name: string;
  brand: string | null;
  laboratory: string | null;
  barcode: string | null;
  image_url: string | null;
  medication_id: string | null;
  pharmacy_id: string;
  pharmacy_name: string;
  chain: string | null;
  website: string | null;
  price: number;
  original_price: number | null;
  discount_pct: number | null;
  stock_status: string | null;
  recorded_at: Date;
  total_count?: number;
}

/** A storefront reports one of these; anything else is treated as unknown. */
const IN_STOCK_STATUSES = ['in_stock', 'low_stock'];

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * ORDER BY fragments, resolved from a closed set. User input never reaches
 * `Prisma.raw` — only these three literals do.
 */
const ORDER_BY: Record<ProductSort, Prisma.Sql> = {
  name: Prisma.raw('c.raw_name ASC'),
  price_asc: Prisma.raw('l.price ASC'),
  price_desc: Prisma.raw('l.price DESC'),
};

/**
 * A product is only a search result if a usable price exists for it — that is
 * what the price lookup resolves and what the old code expressed as
 * `if (!latest) return null`, silently, *after* counting. 2742 of the 77021
 * active products have none (mostly Farmaloop, which publishes `bestPrice: 0`
 * for out-of-stock items and the writer correctly refuses to store a 0), so the
 * old `total` overcounted by that much and pages came back short.
 *
 * Defined once and used by every plan below so the row filter and the count
 * cannot drift apart again. Assumes the row alias is `pp`.
 */
const HAS_USABLE_PRICE = Prisma.sql`
  EXISTS (
    SELECT 1 FROM prices p
    WHERE p.pharmacy_product_id = pp.id AND p.source <> 'quarantine'
  )`;

/**
 * The same predicate, inverted and materialised.
 *
 * Applied inline, the semi-join stops Postgres from using a top-N sort for the
 * unfiltered browse and costs 51 ms → 257 ms. Collecting the ~2.7k unpriced ids
 * once and anti-joining against that brings it back to ~115 ms. Logically it is
 * `NOT (HAS_USABLE_PRICE)`, and it is written as exactly that so the two can
 * never disagree.
 */
const UNPRICED_CTE = Prisma.sql`
  unpriced AS MATERIALIZED (
    SELECT pp.id FROM pharmacy_products pp WHERE NOT ${HAS_USABLE_PRICE}
  )`;

/**
 * Search over what the scrapers actually collected.
 *
 * MedicationsService searches the curated `medications` catalog, which stays
 * empty until the ISP import runs. This service works straight off
 * `pharmacy_products.raw_name`, so real prices are searchable from day one.
 */
@Injectable()
export class ProductsService {
  /**
   * Paginated product search.
   *
   * Two query plans, picked by whether the request needs the latest price
   * *before* it can filter or order. Measured against production (77k products,
   * 76k prices, median of 5 runs including network RTT):
   *
   * | request                                  | before | after  |
   * |------------------------------------------|--------|--------|
   * | `q=""` (browse)                          | 105 ms | 118 ms |
   * | `q="paracetamol"`                        | 172 ms | 151 ms |
   * | `q="" chain=salcobrand`                  |   n/a  |  53 ms |
   * | `q="paracetamol"` + inStock + price sort |   n/a  | 103 ms |
   * | `q=""` + inStock + price sort            |   n/a  | 454 ms |
   *
   * The old implementation cost two sequential scans of `pharmacy_products`
   * (`findMany` + `count`) plus a third round trip for the prices. Both plans
   * below fold the price lookup into the same statement. The unfiltered browse
   * gives back some of that to the has-a-price guard (see `UNPRICED_CTE`) —
   * a deliberate trade of ~13 ms for a `total` that is actually true.
   *
   * The remaining floor is the `ILIKE '%…%'` scan: 85 ms of the 151 ms is a seq
   * scan over 77k rows, and the browse case pays for sorting 77k `raw_name`
   * values with no index to do it. `pg_trgm` is already installed on the
   * database. Two indexes would remove both costs:
   *
   *   CREATE INDEX CONCURRENTLY idx_pp_raw_name_trgm
   *     ON pharmacy_products USING gin (raw_name gin_trgm_ops);
   *   CREATE INDEX CONCURRENTLY idx_pp_raw_name_id
   *     ON pharmacy_products (raw_name, id);
   *
   * Both are schema changes, so neither is done here.
   */
  async search(query: string, page = 1, limit = 20, filters: ProductSearchFilters = {}) {
    const safePage = Math.max(1, Math.floor(page) || 1);
    const safeLimit = Math.min(Math.max(1, Math.floor(limit) || 20), 100);
    const skip = (safePage - 1) * safeLimit;
    const sort: ProductSort = PRODUCT_SORTS.includes(filters.sort as ProductSort)
      ? (filters.sort as ProductSort)
      : 'name';
    const chains = (filters.chains ?? []).filter(Boolean);

    // Anything that reads the price row has to resolve prices before ordering
    // or filtering, which is the expensive plan. Plain name-ordered browsing
    // does not, so it stays on the cheap one.
    const needsPriceContext =
      filters.inStock === true ||
      typeof filters.minPrice === 'number' ||
      typeof filters.maxPrice === 'number' ||
      sort !== 'name';

    const { rows, total } = needsPriceContext
      ? await this.searchWithPriceContext(query, skip, safeLimit, sort, chains, filters)
      : await this.searchByName(query, skip, safeLimit, chains, filters);

    return {
      results: rows.map((r) => this.toSearchResult(r)),
      total,
      page: safePage,
      limit: safeLimit,
      totalPages: Math.ceil(total / safeLimit),
      sort,
    };
  }

  /**
   * Cheap plan — no price-derived filter or sort.
   *
   * Paginates on `pharmacy_products` first, then resolves the latest price for
   * the ≤100 rows of that page with a LATERAL that rides `idx_prices_latest`.
   * Both the page and the count carry the has-a-price guard, so `total` is the
   * number of rows this endpoint can actually return and a full page is always
   * full.
   *
   * The `ORDER BY … , pp.id ASC` tiebreaker matters: `raw_name` alone is not
   * unique (a chain lists the same drug under several SKUs), so without it
   * Postgres was free to order ties differently between two OFFSET queries and
   * the same product could show up on two pages, or on none.
   */
  private async searchByName(
    query: string,
    skip: number,
    limit: number,
    chains: string[],
    filters: ProductSearchFilters = {},
  ) {
    const nameFilter = query
      ? Prisma.sql`AND pp.raw_name ILIKE ${`%${query}%`}`
      : Prisma.empty;
    // The pharmacies join only exists to filter; skipping it when no chain was
    // asked for keeps the browse case on a single table.
    const chainJoin = chains.length
      ? Prisma.sql`JOIN pharmacies fph ON fph.id = pp.pharmacy_id`
      : Prisma.empty;
    const chainFilter = chains.length
      ? Prisma.sql`AND fph.chain = ANY(${chains})`
      : Prisma.empty;
    // `category_id` lives on pharmacy_products, so this needs no extra join.
    const categories = (filters.categories ?? []).filter(Boolean);
    const categoryFilter = categories.length
      ? Prisma.sql`AND pp.category_id = ANY(${categories})`
      : Prisma.empty;

    const [rows, counted] = await Promise.all([
      prisma.$queryRaw<SearchRow[]>`
        WITH ${UNPRICED_CTE}, page AS (
          SELECT pp.id, pp.raw_name, pp.brand, pp.laboratory, pp.barcode,
                 pp.image_url, pp.medication_id, pp.pharmacy_id
          FROM pharmacy_products pp
          ${chainJoin}
          WHERE pp.is_active = true ${nameFilter} ${chainFilter} ${categoryFilter}
            AND NOT EXISTS (SELECT 1 FROM unpriced u WHERE u.id = pp.id)
          ORDER BY pp.raw_name ASC, pp.id ASC
          OFFSET ${skip} LIMIT ${limit}
        )
        SELECT pg.id, pg.raw_name, pg.brand, pg.laboratory, pg.barcode,
               pg.image_url, pg.medication_id, pg.pharmacy_id,
               ph.name AS pharmacy_name, ph.chain, ph.website,
               pr.price, pr.original_price, pr.discount_pct, pr.stock_status, pr.recorded_at
        FROM page pg
        JOIN pharmacies ph ON ph.id = pg.pharmacy_id
        JOIN LATERAL (
          SELECT p.price, p.original_price, p.discount_pct, p.stock_status, p.recorded_at
          FROM prices p
          WHERE p.pharmacy_product_id = pg.id AND p.source <> 'quarantine'
          ORDER BY p.recorded_at DESC
          LIMIT 1
        ) pr ON true
        ORDER BY pg.raw_name ASC, pg.id ASC`,
      prisma.$queryRaw<Array<{ n: number }>>`
        SELECT count(*)::int AS n
        FROM pharmacy_products pp
        ${chainJoin}
        WHERE pp.is_active = true ${nameFilter} ${chainFilter} ${categoryFilter}
          AND ${HAS_USABLE_PRICE}`,
    ]);

    return { rows, total: counted[0]?.n ?? 0 };
  }

  /**
   * Rich plan — the request filters or sorts on the price row.
   *
   * `candidates` applies everything that lives on the product/pharmacy, then
   * `latest` picks one price per candidate. When the request narrows at all
   * (text or chain) the price scan is restricted to those candidates, which is
   * what keeps a filtered search at ~100 ms; an unrestricted browse has to walk
   * every price once, so the restriction is dropped rather than turned into a
   * pointless full-table semi-join.
   *
   * `total` here counts offers that survive the price filters, which is what a
   * facet count should be. It can differ from the cheap plan's product count
   * for the same text query — that only happens on requests that pass the new
   * parameters, so no existing caller sees a change.
   */
  private async searchWithPriceContext(
    query: string,
    skip: number,
    limit: number,
    sort: ProductSort,
    chains: string[],
    filters: ProductSearchFilters,
  ) {
    const nameFilter = query
      ? Prisma.sql`AND pp.raw_name ILIKE ${`%${query}%`}`
      : Prisma.empty;
    const chainFilter = chains.length
      ? Prisma.sql`AND ph.chain = ANY(${chains})`
      : Prisma.empty;
    // `.filter(Boolean)` mirrors the cheap plan exactly: without it a caller
    // passing `['']` would get no category predicate on one plan and an
    // impossible `= ANY('{""}')` on the other, i.e. the same request answered
    // two different ways depending on whether it also touched price.
    const categories = (filters.categories ?? []).filter(Boolean);
    const categoryFilter = categories.length
      ? Prisma.sql`AND pp.category_id = ANY(${categories})`
      : Prisma.empty;
    const narrows = Boolean(query) || chains.length > 0 || categories.length > 0;
    const priceScope = narrows
      ? Prisma.sql`AND p.pharmacy_product_id IN (SELECT id FROM candidates)`
      : Prisma.empty;

    const stockFilter = filters.inStock
      ? Prisma.sql`AND l.stock_status = ANY(${IN_STOCK_STATUSES})`
      : Prisma.empty;
    const minFilter =
      typeof filters.minPrice === 'number'
        ? Prisma.sql`AND l.price >= ${filters.minPrice}`
        : Prisma.empty;
    const maxFilter =
      typeof filters.maxPrice === 'number'
        ? Prisma.sql`AND l.price <= ${filters.maxPrice}`
        : Prisma.empty;

    const rows = await prisma.$queryRaw<SearchRow[]>`
      WITH candidates AS (
        SELECT pp.id, pp.raw_name, pp.brand, pp.laboratory, pp.barcode,
               pp.image_url, pp.medication_id,
               ph.id AS pharmacy_id, ph.name AS pharmacy_name, ph.chain, ph.website
        FROM pharmacy_products pp
        JOIN pharmacies ph ON ph.id = pp.pharmacy_id
        WHERE pp.is_active = true ${nameFilter} ${chainFilter} ${categoryFilter}
      ), latest AS (
        SELECT DISTINCT ON (p.pharmacy_product_id)
               p.pharmacy_product_id, p.price, p.original_price, p.discount_pct,
               p.stock_status, p.recorded_at
        FROM prices p
        WHERE p.source <> 'quarantine' ${priceScope}
        ORDER BY p.pharmacy_product_id, p.recorded_at DESC
      )
      SELECT c.id, c.raw_name, c.brand, c.laboratory, c.barcode, c.image_url,
             c.medication_id, c.pharmacy_id, c.pharmacy_name, c.chain, c.website,
             l.price, l.original_price, l.discount_pct, l.stock_status, l.recorded_at,
             COUNT(*) OVER ()::int AS total_count
      FROM candidates c
      JOIN latest l ON l.pharmacy_product_id = c.id
      WHERE true ${stockFilter} ${minFilter} ${maxFilter}
      ORDER BY ${ORDER_BY[sort]}, c.id ASC
      OFFSET ${skip} LIMIT ${limit}`;

    return { rows, total: rows[0]?.total_count ?? 0 };
  }

  /** Field-for-field the object `search()` has always returned. */
  private toSearchResult(r: SearchRow) {
    return {
      id: r.id,
      name: r.raw_name,
      brand: r.brand,
      laboratory: r.laboratory,
      barcode: r.barcode,
      imageUrl: r.image_url,
      medicationId: r.medication_id,
      pharmacy: {
        id: r.pharmacy_id,
        name: r.pharmacy_name,
        chain: r.chain,
        website: r.website,
      },
      price: r.price,
      originalPrice: r.original_price,
      discountPct: r.discount_pct,
      stockStatus: r.stock_status,
      recordedAt: r.recorded_at,
    };
  }

  /**
   * Same physical product sold by more than one chain, grouped by barcode.
   *
   * This is real cross-pharmacy comparison without the curated catalog: an EAN
   * is an exact identity, so no fuzzy matching is involved. It only covers the
   * chains that publish barcodes (Farmex, Curie, Farmaloop, Knop today) — Cruz
   * Verde, Salcobrand, Preunic, Ahumada, MercadoFarma and Dr. Simi expose
   * none. `comparisonsByMedication()` is the separate path for those.
   */
  async comparisons(query: string, limit = 20, minSaving = 0) {
    const like = `%${query}%`;

    const rows = await prisma.$queryRaw<
      Array<{
        barcode: string;
        name: string;
        offers: unknown;
        chain_count: number;
        min_price: number;
        max_price: number;
        saving: number;
      }>
    >`
      WITH latest AS (
        SELECT DISTINCT ON (pp.id)
               pp.id, pp.barcode, pp.raw_name, pp.laboratory, pp.image_url,
               ph.chain, ph.name AS pharmacy_name, ph.website,
               pr.price, pr.stock_status, pr.recorded_at
        FROM pharmacy_products pp
        JOIN pharmacies ph ON ph.id = pp.pharmacy_id
        JOIN prices pr ON pr.pharmacy_product_id = pp.id AND pr.source <> 'quarantine'
        WHERE pp.is_active = true
          AND pp.barcode IS NOT NULL AND pp.barcode <> ''
          AND pr.price > 0
          AND (${query}::text = '' OR pp.raw_name ILIKE ${like})
        ORDER BY pp.id, pr.recorded_at DESC
      )
      SELECT barcode,
             MIN(raw_name) AS name,
             COUNT(DISTINCT chain)::int AS chain_count,
             MIN(price)::int AS min_price,
             MAX(price)::int AS max_price,
             (MAX(price) - MIN(price))::int AS saving,
             json_agg(json_build_object(
               'pharmacy', pharmacy_name,
               'chain', chain,
               'website', website,
               'price', price,
               'stockStatus', stock_status,
               'productName', raw_name,
               'imageUrl', image_url,
               'recordedAt', recorded_at
             ) ORDER BY price ASC) AS offers
      FROM latest
      GROUP BY barcode
      HAVING COUNT(DISTINCT chain) > 1
         AND (MAX(price) - MIN(price)) >= ${minSaving}
      ORDER BY saving DESC
      LIMIT ${limit}
    `;

    return rows.map((r) => ({
      id: r.barcode,
      barcode: r.barcode,
      name: r.name,
      pharmacyCount: r.chain_count,
      lowestPrice: r.min_price,
      highestPrice: r.max_price,
      saving: r.saving,
      savingPct: r.max_price > 0 ? Math.round((r.saving / r.max_price) * 100) : 0,
      offers: r.offers,
      matchBasis: 'barcode' as const,
    }));
  }

  /** One comparison group, addressed by its barcode. */
  async comparisonByBarcode(barcode: string) {
    const groups = await prisma.$queryRaw<
      Array<{ barcode: string; name: string; offers: unknown }>
    >`
      WITH latest AS (
        SELECT DISTINCT ON (pp.id)
               pp.id, pp.barcode, pp.raw_name, pp.laboratory, pp.image_url,
               ph.chain, ph.name AS pharmacy_name, ph.website,
               pr.price, pr.stock_status, pr.recorded_at
        FROM pharmacy_products pp
        JOIN pharmacies ph ON ph.id = pp.pharmacy_id
        JOIN prices pr ON pr.pharmacy_product_id = pp.id AND pr.source <> 'quarantine'
        WHERE pp.barcode = ${barcode} AND pr.price > 0
        ORDER BY pp.id, pr.recorded_at DESC
      )
      SELECT barcode,
             MIN(raw_name) AS name,
             json_agg(json_build_object(
               'pharmacy', pharmacy_name,
               'chain', chain,
               'website', website,
               'price', price,
               'stockStatus', stock_status,
               'productName', raw_name,
               'imageUrl', image_url,
               'recordedAt', recorded_at
             ) ORDER BY price ASC) AS offers
      FROM latest
      GROUP BY barcode
    `;
    return groups[0] ?? null;
  }

  // ---------------------------------------------------------------------------
  // Second grouping path: medication_id
  //
  // Deliberately kept apart from the barcode path above rather than merged into
  // it, because the two are not the same kind of evidence:
  //
  //   barcode      exact identity published by the storefront. Two rows with the
  //                same EAN are the same box. No judgement involved.
  //   medication_id a link the matcher inferred. It is the only way Cruz Verde,
  //                Salcobrand, Ahumada, MercadoFarma and Dr. Simi — none of
  //                which publish an EAN — can ever join a group, and it covers
  //                ~3.5k multi-chain groups against ~3.8k for barcodes. But it
  //                inherits every matcher mistake: presentations of different
  //                sizes do get linked to one medication, which inflates the
  //                spread.
  //
  // So it is opt-in (`groupBy=medication`), every group carries
  // `matchBasis: 'medication'` so a UI can label the confidence, and offers are
  // collapsed to the cheapest per chain — a comparator only ever wants "what
  // does this cost at each chain", and the collapse also removes the duplicate
  // SKUs a single chain lists for one drug.
  // ---------------------------------------------------------------------------

  /** Multi-chain groups built from the matcher's `medication_id` link. */
  async comparisonsByMedication(query: string, limit = 20, minSaving = 0) {
    const like = `%${query}%`;

    const rows = await prisma.$queryRaw<
      Array<{
        medication_id: string;
        name: string;
        laboratory: string | null;
        offers: unknown;
        chain_count: number;
        min_price: number;
        max_price: number;
        saving: number;
      }>
    >`
      WITH latest AS (
        SELECT DISTINCT ON (pp.id)
               pp.id, pp.medication_id, pp.raw_name, pp.barcode, pp.image_url,
               m.name AS medication_name, m.laboratory AS medication_laboratory,
               ph.chain, ph.name AS pharmacy_name, ph.website,
               pr.price, pr.stock_status, pr.recorded_at
        FROM pharmacy_products pp
        JOIN pharmacies ph ON ph.id = pp.pharmacy_id
        JOIN medications m ON m.id = pp.medication_id
        JOIN prices pr ON pr.pharmacy_product_id = pp.id AND pr.source <> 'quarantine'
        WHERE pp.is_active = true
          AND pp.medication_id IS NOT NULL
          AND pr.price > 0
          AND (${query}::text = '' OR pp.raw_name ILIKE ${like} OR m.name ILIKE ${like})
        ORDER BY pp.id, pr.recorded_at DESC
      ), per_chain AS (
        SELECT DISTINCT ON (medication_id, chain) *
        FROM latest
        ORDER BY medication_id, chain, price ASC
      )
      SELECT medication_id,
             COALESCE(MIN(medication_name), MIN(raw_name)) AS name,
             MIN(medication_laboratory) AS laboratory,
             COUNT(DISTINCT chain)::int AS chain_count,
             MIN(price)::int AS min_price,
             MAX(price)::int AS max_price,
             (MAX(price) - MIN(price))::int AS saving,
             json_agg(json_build_object(
               'pharmacy', pharmacy_name,
               'chain', chain,
               'website', website,
               'price', price,
               'stockStatus', stock_status,
               'productName', raw_name,
               'barcode', barcode,
               'imageUrl', image_url,
               'recordedAt', recorded_at
             ) ORDER BY price ASC) AS offers
      FROM per_chain
      GROUP BY medication_id
      HAVING COUNT(DISTINCT chain) > 1
         AND (MAX(price) - MIN(price)) >= ${minSaving}
      ORDER BY saving DESC
      LIMIT ${limit}
    `;

    return rows.map((r) => this.toMedicationGroup(r));
  }

  /** One medication-grouped comparison, addressed by its medication id. */
  async comparisonByMedication(medicationId: string) {
    // `medications.id` is a uuid column, so a malformed path segment would make
    // Postgres raise 22P02 and surface as a 500. Treat it as "not found".
    if (!UUID_RE.test(medicationId)) return null;

    const groups = await prisma.$queryRaw<
      Array<{
        medication_id: string;
        name: string;
        laboratory: string | null;
        offers: unknown;
        chain_count: number;
        min_price: number;
        max_price: number;
        saving: number;
      }>
    >`
      WITH latest AS (
        SELECT DISTINCT ON (pp.id)
               pp.id, pp.medication_id, pp.raw_name, pp.barcode, pp.image_url,
               m.name AS medication_name, m.laboratory AS medication_laboratory,
               ph.chain, ph.name AS pharmacy_name, ph.website,
               pr.price, pr.stock_status, pr.recorded_at
        FROM pharmacy_products pp
        JOIN pharmacies ph ON ph.id = pp.pharmacy_id
        JOIN medications m ON m.id = pp.medication_id
        JOIN prices pr ON pr.pharmacy_product_id = pp.id AND pr.source <> 'quarantine'
        WHERE pp.medication_id = ${medicationId} AND pr.price > 0
        ORDER BY pp.id, pr.recorded_at DESC
      ), per_chain AS (
        SELECT DISTINCT ON (medication_id, chain) *
        FROM latest
        ORDER BY medication_id, chain, price ASC
      )
      SELECT medication_id,
             COALESCE(MIN(medication_name), MIN(raw_name)) AS name,
             MIN(medication_laboratory) AS laboratory,
             COUNT(DISTINCT chain)::int AS chain_count,
             MIN(price)::int AS min_price,
             MAX(price)::int AS max_price,
             (MAX(price) - MIN(price))::int AS saving,
             json_agg(json_build_object(
               'pharmacy', pharmacy_name,
               'chain', chain,
               'website', website,
               'price', price,
               'stockStatus', stock_status,
               'productName', raw_name,
               'barcode', barcode,
               'imageUrl', image_url,
               'recordedAt', recorded_at
             ) ORDER BY price ASC) AS offers
      FROM per_chain
      GROUP BY medication_id
    `;

    return groups[0] ? this.toMedicationGroup(groups[0]) : null;
  }

  /**
   * Same envelope the barcode groups use, so a client can render either without
   * branching. `barcode` is null because the group is not addressed by one.
   */
  private toMedicationGroup(r: {
    medication_id: string;
    name: string;
    laboratory: string | null;
    offers: unknown;
    chain_count: number;
    min_price: number;
    max_price: number;
    saving: number;
  }) {
    return {
      id: `med:${r.medication_id}`,
      medicationId: r.medication_id,
      barcode: null,
      name: r.name,
      laboratory: r.laboratory,
      pharmacyCount: r.chain_count,
      lowestPrice: r.min_price,
      highestPrice: r.max_price,
      saving: r.saving,
      savingPct: r.max_price > 0 ? Math.round((r.saving / r.max_price) * 100) : 0,
      offers: r.offers,
      matchBasis: 'medication' as const,
    };
  }

  /**
   * Physical (and other) active pharmacies, filterable by region/city.
   * Used by the web to list storefronts for Región de Coquimbo, etc.
   */
  async pharmacies(region?: string, city?: string) {
    return prisma.pharmacy.findMany({
      where: {
        isActive: true,
        ...(region ? { region: { equals: region, mode: 'insensitive' as const } } : {}),
        ...(city ? { city: { equals: city, mode: 'insensitive' as const } } : {}),
      },
      select: {
        id: true,
        name: true,
        chain: true,
        type: true,
        address: true,
        city: true,
        region: true,
        lat: true,
        lng: true,
        phone: true,
        website: true,
        rating: true,
        ratingCount: true,
      },
      orderBy: [{ city: 'asc' }, { name: 'asc' }],
    });
  }

  /** Counts per chain — lets the UI show coverage and spot a dead scraper. */
  async coverage() {
    const pharmacies = await prisma.pharmacy.findMany({
      where: { type: 'online' },
      select: {
        id: true,
        name: true,
        chain: true,
        website: true,
        _count: { select: { products: true } },
      },
    });

    return pharmacies
      .map((p) => ({
        pharmacyId: p.id,
        name: p.name,
        chain: p.chain,
        website: p.website,
        productCount: p._count.products,
      }))
      .sort((a, b) => b.productCount - a.productCount);
  }

  /**
   * Distinct chain slugs that currently have active products, with how many.
   * Lets the UI build the `chain` filter without hardcoding the scraper list.
   */
  async chains() {
    const rows = await prisma.$queryRaw<
      Array<{ chain: string; product_count: number; pharmacy_count: number }>
    >`
      SELECT ph.chain,
             COUNT(*)::int AS product_count,
             COUNT(DISTINCT ph.id)::int AS pharmacy_count
      FROM pharmacy_products pp
      JOIN pharmacies ph ON ph.id = pp.pharmacy_id
      WHERE pp.is_active = true AND ph.chain IS NOT NULL
      GROUP BY ph.chain
      ORDER BY product_count DESC
    `;

    return rows.map((r) => ({
      chain: r.chain,
      productCount: r.product_count,
      pharmacyCount: r.pharmacy_count,
    }));
  }

  /**
   * The seven canonical categories with how many priced listings each holds.
   *
   * Counts come from the listings, not from the `categories` table, so a
   * category the classifier never reached shows up as zero instead of silently
   * missing. Only categories carrying a usable price are worth offering as a
   * facet — a filter that leads to an empty page is worse than no filter.
   *
   * Listings with no category are not reported here: `null` means "no chain
   * evidence was good enough", and turning that into a browsable bucket would
   * dress up ignorance as a classification.
   */
  async categories() {
    const rows = await prisma.$queryRaw<
      Array<{
        id: string;
        name: string;
        identity_key: string;
        position: number;
        product_count: number;
        pharmacy_count: number;
      }>
    >`
      SELECT c.id, c.name, c.identity_key, c.position,
             COUNT(pp.id)::int AS product_count,
             COUNT(DISTINCT pp.pharmacy_id)::int AS pharmacy_count
      FROM categories c
      LEFT JOIN pharmacy_products pp
        ON pp.category_id = c.id
       AND pp.is_active = true
       AND ${HAS_USABLE_PRICE}
      GROUP BY c.id, c.name, c.identity_key, c.position
      ORDER BY c.position ASC
    `;

    return rows.map((r) => ({
      id: r.id,
      name: r.name,
      identityKey: r.identity_key,
      position: r.position,
      productCount: r.product_count,
      pharmacyCount: r.pharmacy_count,
    }));
  }
}
