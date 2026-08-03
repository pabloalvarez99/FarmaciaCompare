import { NextRequest, NextResponse } from 'next/server';

/**
 * Retired: this route served the illustrative demo dataset as if it were an
 * API, so every price it returned was invented. Real data comes from the API
 * gateway (`NEXT_PUBLIC_API_URL`), and scraped prices are exposed under
 * /api/v1/products/* there.
 */
export async function GET(_req: NextRequest) {
  return NextResponse.json(
    {
      message:
        'Endpoint retirado. Usa /api/v1/products/comparisons en el API gateway para precios reales.',
    },
    { status: 410 },
  );
}
