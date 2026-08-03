import { BadRequestException } from '@nestjs/common';
import { PRODUCT_SORTS, ProductSort } from './products.service';

/**
 * Parsing and validation of the `/products/search` query string.
 *
 * Lives apart from the controller so each rule can be exercised on its own:
 * these are the only place a user-supplied string turns into a filter, and a
 * mistake here is invisible in the response (it looks like an ordinary result
 * page) rather than loud.
 */

/** Query params are strings; unrecognised *values* are ignored, never fatal. */
export function parseBool(value?: string): boolean | undefined {
  if (value === undefined) return undefined;
  const v = value.trim().toLowerCase();
  if (v === 'true' || v === '1' || v === 'yes') return true;
  if (v === 'false' || v === '0' || v === 'no') return false;
  return undefined;
}

export function parseMoney(value?: string): number | undefined {
  if (value === undefined || value.trim() === '') return undefined;
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return undefined;
  return Math.floor(n);
}

/**
 * Accepts `?x=a,b` and the repeated `?x=a&x=b` Express produces.
 *
 * Used for both `chain` and `category`: chain slugs and category ids are both
 * lowercase, so the same normalisation fits. Order of first appearance is kept
 * and duplicates collapse, so `?category=a,a,b` binds two values, not three.
 */
export function parseSlugList(value?: string | string[]): string[] {
  if (!value) return [];
  const raw = Array.isArray(value) ? value : [value];
  return [
    ...new Set(
      raw
        .flatMap((v) => String(v).split(','))
        .map((v) => v.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
}

export function parseSort(value?: string): ProductSort | undefined {
  if (!value) return undefined;
  const v = value.trim().toLowerCase();
  return PRODUCT_SORTS.includes(v as ProductSort) ? (v as ProductSort) : undefined;
}

/**
 * Every parameter `/products/search` understands. This is the endpoint's public
 * contract: adding a name here widens it, removing one narrows it.
 *
 * Deploy order matters — the API has to accept a parameter before any client
 * starts sending it (`docs/PLAN.md` §6).
 */
export const SEARCH_PARAMS = [
  'q',
  'page',
  'limit',
  'chain',
  'category',
  'inStock',
  'minPrice',
  'maxPrice',
  'sort',
] as const;

/**
 * Params that ride along without ever being read: analytics tags and cache
 * busters that browsers, ad platforms and proxies append on their own.
 *
 * Rejecting an unknown parameter is right when it means the caller asked for
 * something we silently ignored. `utm_source` is not that — nobody expects it to
 * filter anything, and 400-ing a shared or proxied link over it would break a
 * request that is otherwise perfectly well formed.
 */
const PASSIVE_PARAM_RE = /^(utm_|_ga|gclid$|fbclid$|msclkid$|mc_|ref$|source$|cb$|_$)/i;

function isPassiveParam(name: string): boolean {
  return PASSIVE_PARAM_RE.test(name.trim());
}

/** Levenshtein distance, capped implicitly by the tiny inputs it runs on. */
function distance(a: string, b: string): number {
  const prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  const curr = new Array<number>(b.length + 1);
  for (let i = 1; i <= a.length; i += 1) {
    curr[0] = i;
    for (let j = 1; j <= b.length; j += 1) {
      curr[j] = Math.min(
        prev[j] + 1,
        curr[j - 1] + 1,
        prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    prev.splice(0, prev.length, ...curr);
  }
  return prev[b.length];
}

/**
 * Best guess at what an unrecognised parameter meant, or undefined when nothing
 * is close enough to be worth suggesting.
 *
 * Ranking, cheapest first: same name in another case (`Q`), a prefix relation
 * in either direction (`query` → `q`, `p` → `page`), then an edit distance of
 * at most two (`categoria` → `category`). Ties break alphabetically so the
 * message is deterministic.
 */
export function suggestParam(
  received: string,
  known: readonly string[] = SEARCH_PARAMS,
): string | undefined {
  const u = received.trim().toLowerCase();
  if (!u) return undefined;

  let best: { name: string; score: number } | undefined;
  for (const name of [...known].sort()) {
    const k = name.toLowerCase();
    let score: number;
    if (u === k) score = 0;
    else if (u.startsWith(k) || k.startsWith(u)) score = 1;
    else {
      const d = distance(u, k);
      score = d <= 2 ? 2 + d : Number.POSITIVE_INFINITY;
    }
    if (Number.isFinite(score) && (!best || score < best.score)) best = { name, score };
  }
  return best?.name;
}

/**
 * Rejects a search request that carries a parameter the endpoint does not know.
 *
 * The alternative — the behaviour this replaces — is that `?query=paracetamol`
 * returns HTTP 200 with the first page of the *entire* catalogue, because `q`
 * defaulted to the empty string and an empty `q` means "browse everything".
 * A wrong answer dressed as a right one is the failure mode this codebase
 * refuses everywhere else (`CLAUDE.md` §3.1: an honest emptiness beats an
 * invented number), and it is the same intent already declared globally in
 * `main.ts` via `forbidNonWhitelisted: true` — which only reaches DTO-validated
 * payloads, never `@Query()` scalars like these.
 *
 * Scoped to `/products/search` on purpose: it is the endpoint where a silently
 * ignored parameter produces plausible-looking garbage instead of an obvious
 * error.
 */
export function assertKnownSearchParams(
  received: readonly string[],
  known: readonly string[] = SEARCH_PARAMS,
): void {
  const unknown = received.filter(
    (name) => !known.includes(name) && !isPassiveParam(name),
  );
  if (unknown.length === 0) return;

  const described = unknown
    .map((name) => {
      const hint = suggestParam(name, known);
      return hint ? `'${name}' (¿quisiste decir '${hint}'?)` : `'${name}'`;
    })
    .join(', ');

  throw new BadRequestException(
    `${unknown.length === 1 ? 'Parámetro no reconocido' : 'Parámetros no reconocidos'}: ` +
      `${described}. Parámetros aceptados: ${known.join(', ')}.`,
  );
}
