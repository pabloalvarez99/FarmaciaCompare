import { BadRequestException, NotFoundException } from '@nestjs/common';
import { ProductsController } from './products.controller';
import { ProductSearchFilters, ProductsService } from './products.service';

/**
 * Controller-level tests: what a query string turns into before it reaches the
 * service. The service is a stub — the SQL these filters produce is covered in
 * `products.service.spec.ts`.
 */

type SearchCall = {
  query: string;
  page: number;
  limit: number;
  filters: ProductSearchFilters;
};

function makeController() {
  const calls: SearchCall[] = [];
  const service = {
    search: jest.fn(
      (query: string, page: number, limit: number, filters: ProductSearchFilters) => {
        calls.push({ query, page, limit, filters });
        return Promise.resolve({ results: [], total: 0, page, limit, totalPages: 0 });
      },
    ),
  } as unknown as ProductsService;

  return { controller: new ProductsController(service), service, calls };
}

/**
 * Calls `search()` the way Nest does: `all` is the raw key/value map Express
 * parsed, the rest are the same values picked out by name.
 */
function search(
  controller: ProductsController,
  all: Record<string, unknown>,
  overrides: Partial<{
    q: string;
    page: number;
    limit: number;
    chain: string | string[];
    category: string | string[];
    inStock: string;
    minPrice: string;
    maxPrice: string;
    sort: string;
  }> = {},
) {
  const pick = (name: string) =>
    (name in overrides
      ? (overrides as Record<string, unknown>)[name]
      : all[name]) as string | undefined;

  return controller.search(
    all,
    (pick('q') as string) ?? '',
    (overrides.page ?? Number(all.page ?? 1)) as number,
    (overrides.limit ?? Number(all.limit ?? 20)) as number,
    pick('chain') as string | string[] | undefined,
    pick('category') as string | string[] | undefined,
    pick('inStock'),
    pick('minPrice'),
    pick('maxPrice'),
    pick('sort'),
  );
}

describe('ProductsController.search — category filter', () => {
  it('passes no categories when the parameter is absent', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: 'paracetamol' });
    expect(calls[0].filters.categories).toEqual([]);
  });

  it('passes the comma form through', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', category: 'cosmetica,higiene' });
    expect(calls[0].filters.categories).toEqual(['cosmetica', 'higiene']);
  });

  it('passes the repeated form through', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', category: ['cosmetica', 'higiene'] });
    expect(calls[0].filters.categories).toEqual(['cosmetica', 'higiene']);
  });

  it('normalises case and whitespace before it reaches SQL', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', category: ' Cosmetica , HIGIENE ' });
    expect(calls[0].filters.categories).toEqual(['cosmetica', 'higiene']);
  });

  it('passes an unknown category through untouched — the database decides, not the parser', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', category: 'no-existe' });
    expect(calls[0].filters.categories).toEqual(['no-existe']);
  });
});

describe('ProductsController.search — the other filters', () => {
  it('parses chains the same way as categories', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', chain: 'CRUZ_VERDE, salcobrand' });
    expect(calls[0].filters.chains).toEqual(['cruz_verde', 'salcobrand']);
  });

  it('keeps a sane price range', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', minPrice: '1000', maxPrice: '5000' });
    expect(calls[0].filters.minPrice).toBe(1000);
    expect(calls[0].filters.maxPrice).toBe(5000);
  });

  it('drops the ceiling of an inverted range instead of serving an empty page', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', minPrice: '5000', maxPrice: '1000' });
    expect(calls[0].filters.minPrice).toBe(5000);
    expect(calls[0].filters.maxPrice).toBeUndefined();
  });

  it('reads inStock and sort', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', inStock: 'true', sort: 'price_asc' });
    expect(calls[0].filters.inStock).toBe(true);
    expect(calls[0].filters.sort).toBe('price_asc');
  });

  it('caps limit at 100 so one request cannot ask for the catalogue', async () => {
    const { controller, calls } = makeController();
    await search(controller, { q: '', limit: 5000 });
    expect(calls[0].limit).toBe(100);
  });
});

describe('ProductsController.search — unknown parameters', () => {
  it('rejects ?query= instead of answering 200 with the whole catalogue', async () => {
    const { controller, service } = makeController();
    expect(() => search(controller, { query: 'paracetamol' })).toThrow(BadRequestException);
    expect(service.search).not.toHaveBeenCalled();
  });

  it('does not run the query at all when a parameter is unknown', async () => {
    const { controller, service } = makeController();
    expect(() => search(controller, { q: 'ibuprofeno', categoria: 'cosmetica' })).toThrow(
      BadRequestException,
    );
    expect(service.search).not.toHaveBeenCalled();
  });

  it('still serves every documented parameter', async () => {
    const { controller, service } = makeController();
    await search(controller, {
      q: 'paracetamol',
      page: 2,
      limit: 20,
      chain: 'cruz_verde',
      category: 'medicamento',
      inStock: 'true',
      minPrice: '1000',
      maxPrice: '9000',
      sort: 'price_asc',
    });
    expect(service.search).toHaveBeenCalledTimes(1);
  });

  it('still serves the exact request apps/web makes today', async () => {
    const { controller, service } = makeController();
    await search(controller, { q: 'paracetamol', page: 1, limit: 20, category: 'cosmetica' });
    expect(service.search).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// `groupBy` picks one of the three kinds of evidence
// ---------------------------------------------------------------------------

function makeComparisonController() {
  const service = {
    comparisons: jest.fn(() => Promise.resolve([])),
    comparisonsByMedication: jest.fn(() => Promise.resolve([])),
    comparisonsByDerivedGroup: jest.fn(() => Promise.resolve([])),
    comparisonByDerivedKey: jest.fn(() => Promise.resolve(null)),
  } as unknown as ProductsService;
  return { controller: new ProductsController(service), service };
}

describe('comparisons() — groupBy', () => {
  it('defaults to barcode, which is what the endpoint has always returned', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('', 20, 0, undefined);
    expect(service.comparisons).toHaveBeenCalledWith('', 20, 0);
    expect(service.comparisonsByDerivedGroup).not.toHaveBeenCalled();
  });

  it('routes `derived` to the derived-identity grouping', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('shampoo', 30, 500, 'derived');
    expect(service.comparisonsByDerivedGroup).toHaveBeenCalledWith('shampoo', 30, 500);
  });

  it('accepts the value with stray case and whitespace', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('', 20, 0, '  DERIVED ');
    expect(service.comparisonsByDerivedGroup).toHaveBeenCalledTimes(1);
  });

  it('does not confuse `derived` with `medication`', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('', 20, 0, 'medication');
    expect(service.comparisonsByMedication).toHaveBeenCalledTimes(1);
    expect(service.comparisonsByDerivedGroup).not.toHaveBeenCalled();
  });

  it('falls back to barcode on a value it does not know, rather than erroring', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('', 20, 0, 'inventado');
    expect(service.comparisons).toHaveBeenCalledTimes(1);
  });

  it('caps the limit on every path', () => {
    const { controller, service } = makeComparisonController();
    controller.comparisons('', 5000, 0, 'derived');
    expect(service.comparisonsByDerivedGroup).toHaveBeenCalledWith('', 100, 0);
  });
});

describe('comparisonByDerivedKey()', () => {
  it('passes the key straight through — it is free text, not an id', async () => {
    const { controller, service } = makeComparisonController();
    (service.comparisonByDerivedKey as jest.Mock).mockResolvedValue({ id: 'derived:k' });
    await controller.comparisonByDerivedKey("l'oreal|400ml|a-b|400ml");
    expect(service.comparisonByDerivedKey).toHaveBeenCalledWith("l'oreal|400ml|a-b|400ml");
  });

  it('404s when the key matches nothing, instead of returning an empty group', async () => {
    const { controller } = makeComparisonController();
    await expect(controller.comparisonByDerivedKey('no-existe')).rejects.toThrow(
      NotFoundException,
    );
  });

  it('404s when the key is missing altogether', async () => {
    const { controller, service } = makeComparisonController();
    await expect(controller.comparisonByDerivedKey(undefined)).rejects.toThrow(
      NotFoundException,
    );
    expect(service.comparisonByDerivedKey).toHaveBeenCalledWith('');
  });
});
