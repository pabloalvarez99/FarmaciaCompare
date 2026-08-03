import { BadRequestException } from '@nestjs/common';
import {
  SEARCH_PARAMS,
  assertKnownSearchParams,
  parseBool,
  parseMoney,
  parseSlugList,
  parseSort,
  suggestParam,
} from './search-query';

describe('parseSlugList', () => {
  it('returns nothing for an absent or blank parameter', () => {
    expect(parseSlugList(undefined)).toEqual([]);
    expect(parseSlugList('')).toEqual([]);
    expect(parseSlugList('   ')).toEqual([]);
    expect(parseSlugList([])).toEqual([]);
  });

  it('splits the comma form: ?category=cosmetica,higiene', () => {
    expect(parseSlugList('cosmetica,higiene')).toEqual(['cosmetica', 'higiene']);
  });

  it('accepts the repeated form Express turns into an array: ?category=a&category=b', () => {
    expect(parseSlugList(['cosmetica', 'higiene'])).toEqual(['cosmetica', 'higiene']);
  });

  it('accepts both forms mixed in one request', () => {
    expect(parseSlugList(['cosmetica,higiene', 'bebe'])).toEqual([
      'cosmetica',
      'higiene',
      'bebe',
    ]);
  });

  it('trims surrounding whitespace', () => {
    expect(parseSlugList('  cosmetica ,  higiene  ')).toEqual(['cosmetica', 'higiene']);
    expect(parseSlugList([' cosmetica ', ' higiene'])).toEqual(['cosmetica', 'higiene']);
  });

  it('lowercases, because category ids and chain slugs are lowercase in the database', () => {
    expect(parseSlugList('COSMETICA,Higiene,DermoCosmetica')).toEqual([
      'cosmetica',
      'higiene',
      'dermocosmetica',
    ]);
  });

  it('drops empty segments instead of binding an impossible ""', () => {
    expect(parseSlugList('cosmetica,,higiene')).toEqual(['cosmetica', 'higiene']);
    expect(parseSlugList(',')).toEqual([]);
    expect(parseSlugList(' , ')).toEqual([]);
  });

  it('collapses duplicates, keeping first appearance', () => {
    expect(parseSlugList('higiene,cosmetica,higiene')).toEqual(['higiene', 'cosmetica']);
    expect(parseSlugList(['Cosmetica', 'cosmetica'])).toEqual(['cosmetica']);
  });
});

describe('parseBool', () => {
  it.each(['true', 'TRUE', ' True ', '1', 'yes', 'YES'])('reads %p as true', (v) => {
    expect(parseBool(v)).toBe(true);
  });

  it.each(['false', 'FALSE', '0', 'no', ' No '])('reads %p as false', (v) => {
    expect(parseBool(v)).toBe(false);
  });

  it('leaves an unreadable value undefined rather than guessing', () => {
    expect(parseBool('maybe')).toBeUndefined();
    expect(parseBool('')).toBeUndefined();
    expect(parseBool(undefined)).toBeUndefined();
  });
});

describe('parseMoney', () => {
  it('reads a whole number of pesos', () => {
    expect(parseMoney('12990')).toBe(12990);
  });

  it('floors a fractional amount — CLP has no cents', () => {
    expect(parseMoney('12990.99')).toBe(12990);
  });

  it('accepts zero', () => {
    expect(parseMoney('0')).toBe(0);
  });

  it.each(['', '   ', 'abc', '-1', 'NaN', 'Infinity'])(
    'ignores %p instead of turning it into a bound',
    (v) => {
      expect(parseMoney(v)).toBeUndefined();
    },
  );
});

describe('parseSort', () => {
  it.each(['name', 'price_asc', 'price_desc'])('accepts the known key %p', (v) => {
    expect(parseSort(v)).toBe(v);
  });

  it('is case-insensitive', () => {
    expect(parseSort(' PRICE_DESC ')).toBe('price_desc');
  });

  it('falls back to undefined (the service then uses `name`) for anything else', () => {
    expect(parseSort('price')).toBeUndefined();
    expect(parseSort('cheapest')).toBeUndefined();
    expect(parseSort('')).toBeUndefined();
    expect(parseSort(undefined)).toBeUndefined();
  });

  it('never lets user input reach the ORDER BY vocabulary', () => {
    expect(parseSort('l.price ASC; DROP TABLE prices')).toBeUndefined();
  });
});

describe('assertKnownSearchParams', () => {
  it('accepts a request with no parameters at all', () => {
    expect(() => assertKnownSearchParams([])).not.toThrow();
  });

  it('accepts every parameter the endpoint documents', () => {
    expect(() => assertKnownSearchParams([...SEARCH_PARAMS])).not.toThrow();
  });

  it('accepts exactly what apps/web sends today', () => {
    // If this ever fails, the deployed site is about to start getting 400s.
    expect(() => assertKnownSearchParams(['q', 'page', 'limit', 'category'])).not.toThrow();
  });

  it('rejects the misspelling that used to return the whole catalogue with HTTP 200', () => {
    expect(() => assertKnownSearchParams(['query'])).toThrow(BadRequestException);
  });

  it('names the offender and points at the parameter that was meant', () => {
    let message = '';
    try {
      assertKnownSearchParams(['query']);
    } catch (e) {
      message = (e as BadRequestException).message;
    }
    expect(message).toContain("'query'");
    expect(message).toContain("'q'");
    expect(message).toContain('q, page, limit, chain, category, inStock, minPrice, maxPrice, sort');
  });

  it('rejects a known name in the wrong case rather than silently accepting it', () => {
    expect(() => assertKnownSearchParams(['Q'])).toThrow(/'Q'.*'q'/);
    expect(() => assertKnownSearchParams(['Category'])).toThrow(BadRequestException);
  });

  it('reports every unknown parameter in one response', () => {
    expect(() => assertKnownSearchParams(['q', 'query', 'categoria'])).toThrow(
      /Parámetros no reconocidos/,
    );
    let message = '';
    try {
      assertKnownSearchParams(['q', 'query', 'categoria']);
    } catch (e) {
      message = (e as BadRequestException).message;
    }
    expect(message).toContain("'query'");
    expect(message).toContain("'categoria'");
    expect(message).toContain("'category'");
  });

  it('answers with 400, not 500', () => {
    try {
      assertKnownSearchParams(['nope']);
      throw new Error('expected a rejection');
    } catch (e) {
      expect(e).toBeInstanceOf(BadRequestException);
      expect((e as BadRequestException).getStatus()).toBe(400);
    }
  });
});

describe('suggestParam', () => {
  it.each([
    ['query', 'q'],
    ['Q', 'q'],
    ['categoria', 'category'],
    ['chains', 'chain'],
    ['instock', 'inStock'],
    ['minprice', 'minPrice'],
    ['pag', 'page'],
    ['sortBy', 'sort'],
  ])('maps %p to %p', (received, expected) => {
    expect(suggestParam(received)).toBe(expected);
  });

  it('says nothing when nothing is close, instead of inventing a hint', () => {
    expect(suggestParam('utm_source')).toBeUndefined();
    expect(suggestParam('nombre')).toBeUndefined();
    expect(suggestParam('')).toBeUndefined();
  });
});

describe('parámetros pasivos', () => {
  // Analytics tags are appended by things outside the caller's control. They
  // ask for nothing, so ignoring them is not the silent-wrong-answer failure
  // this guard exists to prevent.
  it.each(['utm_source', 'utm_medium', 'gclid', 'fbclid', 'mc_cid', '_ga'])(
    'deja pasar %s sin error',
    (name) => {
      expect(() => assertKnownSearchParams(['q', name])).not.toThrow();
    },
  );

  it('sigue rechazando un typo aunque venga con analítica', () => {
    expect(() => assertKnownSearchParams(['query', 'utm_source'])).toThrow(
      /query/,
    );
  });
});
