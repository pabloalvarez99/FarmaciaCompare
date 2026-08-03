/**
 * What SQL `ProductsService` actually emits.
 *
 * `search()` has two query plans and the filters have to be applied by *both*
 * of them. That is not a stylistic point: the cheap plan (`searchByName`) is the
 * one a plain `?category=cosmetica` takes, because nothing in that request needs
 * the price row. If the category predicate only existed on the expensive plan,
 * asking for a category without touching price would quietly return the whole
 * catalogue with HTTP 200 — the loudest possible bug wearing the quietest
 * possible clothes.
 *
 * So these tests read the statement Prisma would send. `prisma.$queryRaw` is a
 * mock; the real `Prisma` tag is kept, so `Prisma.sql(strings, ...values)`
 * rebuilds exactly the `Sql` the service composed, parameters and all. No
 * database is touched.
 */
jest.mock('@farmacia/database', () => ({
  Prisma: jest.requireActual('@prisma/client').Prisma,
  prisma: { $queryRaw: jest.fn() },
}));

import { Prisma, prisma } from '@farmacia/database';
import { ProductSearchFilters, ProductsService } from './products.service';

const queryRaw = prisma.$queryRaw as unknown as jest.Mock;

interface Statement {
  /** The statement with `$1`-style placeholders, whitespace collapsed. */
  text: string;
  /** The bound parameters, in order. */
  values: unknown[];
}

/** Every statement the service sent since the last reset, in call order. */
function statements(): Statement[] {
  return queryRaw.mock.calls.map((call: unknown[]) => {
    const [strings, ...values] = call as [TemplateStringsArray, ...unknown[]];
    const sql = Prisma.sql(strings, ...(values as never[]));
    return { text: sql.text.replace(/\s+/g, ' ').trim(), values: sql.values };
  });
}

/** Answers the page query with `rows` and the `SELECT count(*)` query with `count`. */
function respondWith(rows: unknown[], count = 0) {
  queryRaw.mockImplementation((strings: TemplateStringsArray, ...values: unknown[]) => {
    const text = Prisma.sql(strings, ...(values as never[])).text;
    return Promise.resolve(/count\(\*\)::int AS n/.test(text) ? [{ n: count }] : rows);
  });
}

const ROW = {
  id: 'pp-1',
  raw_name: 'Paracetamol 500 mg x 20 comprimidos',
  brand: 'Generico',
  laboratory: 'Laboratorio Chile',
  barcode: '7801234567890',
  image_url: 'https://cdn.example/p.jpg',
  medication_id: 'med-1',
  derived_group_key: 'dove|370ml|nutricion-tri-oleos|370ml',
  pharmacy_id: 'ph-1',
  pharmacy_name: 'Cruz Verde',
  chain: 'cruz_verde',
  website: 'https://cruzverde.cl',
  price: 1990,
  original_price: 2490,
  discount_pct: 20,
  stock_status: 'in_stock',
  recorded_at: new Date('2026-08-01T12:00:00.000Z'),
};

const CATEGORY_PREDICATE = /pp\.category_id = ANY\(/;

let service: ProductsService;

beforeEach(() => {
  queryRaw.mockReset();
  queryRaw.mockResolvedValue([]);
  service = new ProductsService();
});

// ---------------------------------------------------------------------------
// Which plan runs
// ---------------------------------------------------------------------------

describe('search() — plan selection', () => {
  it('browsing with no filters takes the cheap plan: a page query and a separate count', async () => {
    await service.search('', 1, 20, {});
    expect(statements()).toHaveLength(2);
  });

  it('a category filter alone stays on the cheap plan', async () => {
    // This is exactly why the filter has to exist there. A category is a
    // property of the listing, not of the price, so nothing forces the
    // expensive plan — and the request must still come back filtered.
    await service.search('', 1, 20, { categories: ['cosmetica'] });
    expect(statements()).toHaveLength(2);
  });

  it.each<[string, Partial<ProductSearchFilters>]>([
    ['a price sort', { sort: 'price_asc' }],
    ['an in-stock filter', { inStock: true }],
    ['a price floor', { minPrice: 1000 }],
    ['a price ceiling', { maxPrice: 9000 }],
  ])('%s needs the price row, so it takes the single-statement plan', async (_label, extra) => {
    await service.search('', 1, 20, extra);
    expect(statements()).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// The regression this file exists for
// ---------------------------------------------------------------------------

describe('search() — the category filter reaches every plan', () => {
  const PLANS: Array<[string, Partial<ProductSearchFilters>]> = [
    ['cheap plan (no price context)', {}],
    ['cheap plan with a text query', {}],
    ['price sort', { sort: 'price_desc' }],
    ['in-stock filter', { inStock: true }],
    ['price floor', { minPrice: 1000 }],
    ['price ceiling', { maxPrice: 9000 }],
    ['every price filter at once', { inStock: true, minPrice: 1000, maxPrice: 9000, sort: 'price_asc' }],
  ];

  it.each(PLANS)(
    'binds the requested categories on every statement — %s',
    async (label, extra) => {
      const query = label.includes('text query') ? 'paracetamol' : '';
      await service.search(query, 1, 20, { categories: ['cosmetica', 'higiene'], ...extra });

      const emitted = statements();
      expect(emitted.length).toBeGreaterThan(0);
      for (const s of emitted) {
        // If this fails on the cheap plan, `?category=x` is returning the whole
        // catalogue again.
        expect(s.text).toMatch(CATEGORY_PREDICATE);
        expect(s.values).toContainEqual(['cosmetica', 'higiene']);
      }
    },
  );

  it('does not add a category predicate when none was asked for', async () => {
    await service.search('paracetamol', 1, 20, {});
    for (const s of statements()) expect(s.text).not.toMatch(CATEGORY_PREDICATE);
  });
});

// ---------------------------------------------------------------------------
// total
// ---------------------------------------------------------------------------

describe('search() — total obeys the same filters as the page', () => {
  it('the cheap plan counts with the identical predicates and the identical bindings', async () => {
    await service.search('paracetamol', 1, 20, {
      categories: ['medicamento'],
      chains: ['cruz_verde'],
    });

    const [page, count] = statements();
    expect(count.text).toContain('count(*)::int AS n');

    for (const s of [page, count]) {
      expect(s.text).toContain('pp.raw_name ILIKE');
      expect(s.text).toContain('fph.chain = ANY(');
      expect(s.text).toMatch(CATEGORY_PREDICATE);
    }

    // Same three filter values, same order. The count carries no OFFSET/LIMIT,
    // which is the only difference allowed between the two.
    expect(count.values).toEqual(['%paracetamol%', ['cruz_verde'], ['medicamento']]);
    expect(page.values.slice(0, 3)).toEqual(count.values);
    expect(page.values.slice(3)).toEqual([0, 20]);
  });

  it('the cheap plan reports the counted total, not the length of the page', async () => {
    respondWith([ROW], 137);
    const res = await service.search('', 1, 20, { categories: ['cosmetica'] });
    expect(res.results).toHaveLength(1);
    expect(res.total).toBe(137);
    expect(res.totalPages).toBe(Math.ceil(137 / 20));
  });

  it('the price-context plan counts over the filtered candidate set', async () => {
    respondWith([{ ...ROW, total_count: 42 }]);
    const res = await service.search('', 1, 20, {
      categories: ['cosmetica'],
      sort: 'price_asc',
    });

    const [only] = statements();
    expect(only.text).toContain('COUNT(*) OVER ()::int AS total_count');
    // The window runs over `candidates JOIN latest`, and `candidates` is where
    // the category filter lives — so the count is filtered by construction.
    expect(only.text).toMatch(/WITH candidates AS \(.*pp\.category_id = ANY\(/);
    expect(res.total).toBe(42);
  });
});

// ---------------------------------------------------------------------------
// A category nobody has
// ---------------------------------------------------------------------------

describe('search() — a category that matches nothing', () => {
  it('returns an empty page and a zero total instead of the catalogue', async () => {
    respondWith([], 0);
    const res = await service.search('', 1, 20, { categories: ['no-existe'] });

    expect(res.results).toEqual([]);
    expect(res.total).toBe(0);
    expect(res.totalPages).toBe(0);
  });

  it('binds the unknown slug rather than dropping the predicate', async () => {
    // Dropping an unrecognised value would turn "show me category X" into
    // "show me everything", which is the failure this whole file guards.
    await service.search('', 1, 20, { categories: ['no-existe'] });
    for (const s of statements()) {
      expect(s.text).toMatch(CATEGORY_PREDICATE);
      expect(s.values).toContainEqual(['no-existe']);
    }
  });

  it('emits different SQL from an unfiltered browse', async () => {
    await service.search('', 1, 20, {});
    const browse = statements().map((s) => s.text);

    queryRaw.mockClear();
    await service.search('', 1, 20, { categories: ['no-existe'] });
    const filtered = statements().map((s) => s.text);

    expect(filtered).toHaveLength(browse.length);
    expect(filtered).not.toEqual(browse);
  });
});

// ---------------------------------------------------------------------------
// Callers that send no category see no change at all
// ---------------------------------------------------------------------------

describe('search() — an empty category list is the same request as no category', () => {
  async function textsFor(filters: ProductSearchFilters) {
    queryRaw.mockClear();
    await service.search('paracetamol', 2, 20, filters);
    return statements().map((s) => s.text);
  }

  it('holds on the cheap plan', async () => {
    const none = await textsFor({});
    expect(await textsFor({ categories: [] })).toEqual(none);
    // A caller that hands over a blank slug must not get a different plan than
    // one that hands over nothing.
    expect(await textsFor({ categories: [''] })).toEqual(none);
  });

  it('holds on the price-context plan', async () => {
    const none = await textsFor({ sort: 'price_asc' });
    expect(await textsFor({ categories: [], sort: 'price_asc' })).toEqual(none);
    expect(await textsFor({ categories: [''], sort: 'price_asc' })).toEqual(none);
  });
});

// ---------------------------------------------------------------------------
// The response envelope
// ---------------------------------------------------------------------------

describe('search() — response shape', () => {
  it('puts the rows under `results`, which is what the deployed API returns today', async () => {
    respondWith([ROW], 1);
    const res = await service.search('paracetamol', 1, 20, {});

    expect(Object.keys(res)).toEqual(['results', 'total', 'page', 'limit', 'totalPages', 'sort']);
    expect(res).toMatchObject({ total: 1, page: 1, limit: 20, totalPages: 1, sort: 'name' });
  });

  it('maps a row to the field names the web already consumes', async () => {
    respondWith([ROW], 1);
    const { results } = await service.search('paracetamol', 1, 20, {});

    expect(Object.keys(results[0])).toEqual([
      'id',
      'name',
      'brand',
      'laboratory',
      'barcode',
      'imageUrl',
      'medicationId',
      // Added with the derived grouping path: it is what lets /precios link a
      // cosmetics listing — no barcode, no catalog link — to its comparison.
      'derivedGroupKey',
      'pharmacy',
      'price',
      'originalPrice',
      'discountPct',
      'stockStatus',
      'recordedAt',
    ]);
    expect(results[0]).toMatchObject({
      id: 'pp-1',
      name: 'Paracetamol 500 mg x 20 comprimidos',
      price: 1990,
      pharmacy: {
        id: 'ph-1',
        name: 'Cruz Verde',
        chain: 'cruz_verde',
        website: 'https://cruzverde.cl',
      },
    });
  });

  it('echoes the sort it actually used, falling back to `name`', async () => {
    respondWith([], 0);
    expect((await service.search('', 1, 20, { sort: 'price_desc' })).sort).toBe('price_desc');
    expect(
      (await service.search('', 1, 20, { sort: 'cheapest' as never })).sort,
    ).toBe('name');
  });

  it('clamps page and limit to something a database can serve', async () => {
    respondWith([], 0);
    const res = await service.search('', -3, 5000, {});
    expect(res.page).toBe(1);
    expect(res.limit).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// GET /products/categories
// ---------------------------------------------------------------------------

describe('categories()', () => {
  const CATEGORY_ROWS = [
    {
      id: 'medicamento',
      name: 'Medicamento',
      identity_key: 'principio activo + concentracion + forma + unidades',
      position: 1,
      product_count: 40123,
      pharmacy_count: 10,
    },
    {
      id: 'cosmetica',
      name: 'Cosmetica',
      identity_key: 'marca + linea + tono + volumen',
      position: 4,
      product_count: 0,
      pharmacy_count: 0,
    },
  ];

  it('counts from the listings, keeping a category with zero visible instead of missing', async () => {
    queryRaw.mockResolvedValue(CATEGORY_ROWS);
    const res = await service.categories();

    const [only] = statements();
    expect(only.text).toContain('FROM categories c');
    expect(only.text).toContain('LEFT JOIN pharmacy_products pp');
    expect(res).toHaveLength(2);
    expect(res[1]).toEqual({
      id: 'cosmetica',
      name: 'Cosmetica',
      identityKey: 'marca + linea + tono + volumen',
      position: 4,
      productCount: 0,
      pharmacyCount: 0,
    });
  });

  it('only counts active listings that carry a usable price', async () => {
    queryRaw.mockResolvedValue(CATEGORY_ROWS);
    await service.categories();

    const [only] = statements();
    expect(only.text).toContain('pp.is_active = true');
    expect(only.text).toContain('FROM prices p');
    expect(only.text).toContain("p.source <> 'quarantine'");
  });

  it('never reports the unclassified listings as a category of their own', async () => {
    queryRaw.mockResolvedValue(CATEGORY_ROWS);
    await service.categories();

    const [only] = statements();
    // 22.925 listings have a null category_id on purpose: "we do not know" is
    // not a bucket, so nothing here may select for it.
    expect(only.text).not.toMatch(/category_id IS NULL/i);
    expect(only.text).not.toMatch(/COALESCE\(\s*pp\.category_id/i);
  });

  it('orders by the declared display position', async () => {
    queryRaw.mockResolvedValue(CATEGORY_ROWS);
    await service.categories();
    expect(statements()[0].text).toContain('ORDER BY c.position ASC');
  });

  it('binds no user input at all', async () => {
    queryRaw.mockResolvedValue(CATEGORY_ROWS);
    await service.categories();
    expect(statements()[0].values).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// The derived grouping path
// ---------------------------------------------------------------------------

const DERIVED_ROW = {
  derived_group_key: 'cerave|40ml|control-gel-imperfecciones|40ml',
  name: 'Cerave Gel Control Imperfecciones 40 mL',
  brand: 'CeraVe',
  chain_count: 7,
  min_price: 15000,
  max_price: 20999,
  saving: 5999,
  offers: [],
};

describe('comparisonsByDerivedGroup()', () => {
  it('groups on the derived key and never on medication_id or barcode', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonsByDerivedGroup('', 20, 0);

    const [only] = statements();
    expect(only.text).toContain('GROUP BY derived_group_key');
    expect(only.text).toContain('pp.derived_group_key IS NOT NULL');
    expect(only.text).not.toContain('medication_id');
    expect(only.text).not.toContain('GROUP BY barcode');
  });

  it('keeps only groups seen in more than one chain', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonsByDerivedGroup('', 20, 0);
    expect(statements()[0].text).toContain('HAVING COUNT(DISTINCT chain) > 1');
  });

  it('collapses a chain to its cheapest offer, so duplicate SKUs do not inflate the spread', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonsByDerivedGroup('', 20, 0);
    const [only] = statements();
    expect(only.text).toContain('DISTINCT ON (derived_group_key, chain)');
    expect(only.text).toContain('ORDER BY derived_group_key, chain, price ASC');
  });

  it('ignores quarantined prices and zero prices, like every other path', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonsByDerivedGroup('', 20, 0);
    const [only] = statements();
    expect(only.text).toContain(`pr.source <> 'quarantine'`);
    expect(only.text).toContain('pr.price > 0');
  });

  it('binds the query, the saving floor and the limit as parameters', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonsByDerivedGroup('shampoo', 12, 500);
    expect(statements()[0].values).toEqual(['shampoo', '%shampoo%', '%shampoo%', 500, 12]);
  });

  it('labels the basis and carries the key back, so the UI can address the group', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    const [group] = await service.comparisonsByDerivedGroup('', 20, 0);

    expect(group).toMatchObject({
      id: 'derived:cerave|40ml|control-gel-imperfecciones|40ml',
      derivedGroupKey: 'cerave|40ml|control-gel-imperfecciones|40ml',
      brand: 'CeraVe',
      barcode: null,
      medicationId: null,
      matchBasis: 'derived',
      pharmacyCount: 7,
      lowestPrice: 15000,
      highestPrice: 20999,
      saving: 5999,
      savingPct: 29,
    });
  });
});

describe('comparisonByDerivedKey()', () => {
  it('refuses an empty key without going to the database', async () => {
    expect(await service.comparisonByDerivedKey('')).toBeNull();
    expect(await service.comparisonByDerivedKey('   ')).toBeNull();
    expect(queryRaw).not.toHaveBeenCalled();
  });

  it('binds the key rather than interpolating it', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonByDerivedKey("l'oreal|400ml|a-b|400ml");

    const [only] = statements();
    expect(only.text).toContain('pp.derived_group_key = $1');
    expect(only.values).toEqual(["l'oreal|400ml|a-b|400ml"]);
  });

  it('does not require two chains — a single-chain group is a valid page', async () => {
    queryRaw.mockResolvedValue([DERIVED_ROW]);
    await service.comparisonByDerivedKey('k');
    expect(statements()[0].text).not.toContain('HAVING');
  });

  it('answers null when nothing matches', async () => {
    queryRaw.mockResolvedValue([]);
    expect(await service.comparisonByDerivedKey('no-existe')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Known defect, reported not fixed
// ---------------------------------------------------------------------------

describe('KNOWN DEFECT — total on the price-context plan', () => {
  it('reports 0 for a page past the end, because the count rides on the rows', async () => {
    // `searchWithPriceContext` reads `total` from `COUNT(*) OVER ()` on the
    // returned rows, so an OFFSET beyond the last row leaves it with nothing to
    // read and `total` collapses to 0 even though matches exist. The cheap plan
    // does not have this problem: it counts in a separate statement.
    //
    // Consequence for a client: `total`/`totalPages` flip to 0 when you page
    // past the end with any price filter or price sort, so a paginator built on
    // them loses the ability to go back.
    //
    // This test documents current behaviour. When the defect is fixed it will
    // fail — that is the intent; delete it then.
    respondWith([]);
    const res = await service.search('', 999, 20, { sort: 'price_asc' });
    expect(res.total).toBe(0);
    expect(res.totalPages).toBe(0);
  });
});
