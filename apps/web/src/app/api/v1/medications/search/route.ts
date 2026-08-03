import { NextRequest, NextResponse } from 'next/server';
import { searchProducts } from '@/lib/api-products';

/**
 * Was serving the demo dataset. Now proxies the real scraped-product search, so
 * any client on this path gets genuine prices instead of invented ones.
 *
 * The response keeps the old envelope (results/total/page/limit/totalPages),
 * but each result is a pharmacy product rather than a catalogued medication —
 * there is no medication catalog yet.
 */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get('q') ?? '';
  const page = parseInt(req.nextUrl.searchParams.get('page') ?? '1', 10) || 1;
  const limit = Math.min(
    parseInt(req.nextUrl.searchParams.get('limit') ?? '20', 10) || 20,
    100,
  );

  const data = await searchProducts(q, page, limit);
  return NextResponse.json(data);
}
