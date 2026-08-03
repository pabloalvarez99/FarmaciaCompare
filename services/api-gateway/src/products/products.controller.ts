import {
  Controller,
  DefaultValuePipe,
  Get,
  Header,
  NotFoundException,
  Param,
  ParseIntPipe,
  Query,
} from '@nestjs/common';
import { ProductSearchFilters, ProductsService } from './products.service';
import {
  assertKnownSearchParams,
  parseBool,
  parseMoney,
  parseSlugList,
  parseSort,
} from './search-query';

/**
 * Prices refresh on the scraper cadence (hours), so a short browser TTL with a
 * longer shared/CDN TTL is safe: Vercel and any CDN in front of Cloud Run can
 * serve the same page to everyone, and `stale-while-revalidate` keeps the edge
 * responsive while it refetches.
 */
const CACHE_PRICES = 'public, max-age=60, s-maxage=300, stale-while-revalidate=600';
/** Store lists and chain counts move on the order of days, not minutes. */
const CACHE_REFERENCE = 'public, max-age=300, s-maxage=3600, stale-while-revalidate=86400';

@Controller('products')
export class ProductsController {
  constructor(private readonly productsService: ProductsService) {}

  /**
   * `q`, `page` and `limit` behave exactly as before. The filters below are all
   * optional; a request that sends none of them takes the same code path and
   * returns the same rows it always did.
   *
   * - `chain`     `cruz_verde` | `cruz_verde,salcobrand` | repeated param
   * - `category`  `medicamento` | `cosmetica,higiene` | repeated param.
   *               Listings with no category are excluded when this is set.
   * - `inStock`   `true` keeps only offers the storefront reports as available
   * - `minPrice`  / `maxPrice`  inclusive bounds in CLP
   * - `sort`      `name` (default) | `price_asc` | `price_desc`
   *
   * Anything outside that list is a 400, not a silently ignored parameter — see
   * `assertKnownSearchParams` for why. `all` exists only to see the raw key set;
   * every value is still read through its own typed `@Query(name)` below.
   */
  @Get('search')
  @Header('Cache-Control', CACHE_PRICES)
  search(
    @Query() all: Record<string, unknown>,
    @Query('q') query: string = '',
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
    @Query('chain') chain?: string | string[],
    @Query('category') category?: string | string[],
    @Query('inStock') inStock?: string,
    @Query('minPrice') minPrice?: string,
    @Query('maxPrice') maxPrice?: string,
    @Query('sort') sort?: string,
  ) {
    assertKnownSearchParams(Object.keys(all ?? {}));

    const min = parseMoney(minPrice);
    const max = parseMoney(maxPrice);
    const filters: ProductSearchFilters = {
      chains: parseSlugList(chain),
      categories: parseSlugList(category),
      inStock: parseBool(inStock),
      minPrice: min,
      // An inverted range would silently return nothing; drop the ceiling
      // instead of serving an empty page for what looks like a typo.
      maxPrice: max !== undefined && min !== undefined && max < min ? undefined : max,
      sort: parseSort(sort),
    };

    return this.productsService.search(query, page, Math.min(limit, 100), filters);
  }

  @Get('coverage')
  @Header('Cache-Control', CACHE_REFERENCE)
  coverage() {
    return this.productsService.coverage();
  }

  /** Chain slugs with active products — the source for the `chain` filter. */
  @Get('chains')
  @Header('Cache-Control', CACHE_REFERENCE)
  chains() {
    return this.productsService.chains();
  }

  /**
   * The seven canonical categories with their live counts — the source for the
   * `category` filter, so the UI never hardcodes the list.
   *
   * Listings the classifier could not place keep a null category and are not
   * reported as a category of their own: unknown is not a bucket.
   */
  @Get('categories')
  @Header('Cache-Control', CACHE_REFERENCE)
  categories() {
    return this.productsService.categories();
  }

  /** Active pharmacies, optionally filtered by region/city (e.g. Coquimbo). */
  @Get('pharmacies')
  @Header('Cache-Control', CACHE_REFERENCE)
  pharmacies(
    @Query('region') region?: string,
    @Query('city') city?: string,
  ) {
    return this.productsService.pharmacies(
      region?.trim() || undefined,
      city?.trim() || undefined,
    );
  }

  /**
   * Products sold by more than one chain, ordered by how much you save.
   *
   * `groupBy` defaults to `barcode`, which is what this endpoint has always
   * returned. `medication` switches to the matcher-derived grouping, the only
   * one that can include the chains that publish no EAN.
   */
  @Get('comparisons')
  @Header('Cache-Control', CACHE_PRICES)
  comparisons(
    @Query('q') query: string = '',
    @Query('limit', new DefaultValuePipe(20), ParseIntPipe) limit: number,
    @Query('minSaving', new DefaultValuePipe(0), ParseIntPipe) minSaving: number,
    @Query('groupBy') groupBy?: string,
  ) {
    const capped = Math.min(limit, 100);
    return groupBy?.trim().toLowerCase() === 'medication'
      ? this.productsService.comparisonsByMedication(query, capped, minSaving)
      : this.productsService.comparisons(query, capped, minSaving);
  }

  /**
   * Declared before `comparisons/:barcode` for clarity — it has three path
   * segments, so the two routes cannot collide.
   */
  @Get('comparisons/medication/:medicationId')
  @Header('Cache-Control', CACHE_PRICES)
  async comparisonByMedication(@Param('medicationId') medicationId: string) {
    const group = await this.productsService.comparisonByMedication(medicationId);
    if (!group) throw new NotFoundException(`No hay ofertas para el medicamento ${medicationId}`);
    return group;
  }

  @Get('comparisons/:barcode')
  @Header('Cache-Control', CACHE_PRICES)
  async comparison(@Param('barcode') barcode: string) {
    const group = await this.productsService.comparisonByBarcode(barcode);
    if (!group) throw new NotFoundException(`No hay ofertas para el código ${barcode}`);
    return group;
  }
}
