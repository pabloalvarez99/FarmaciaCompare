import { NextRequest, NextResponse } from 'next/server';

/**
 * Retired: the demo history was generated with a random walk, so it looked like
 * a real price series without being one. Genuine history will come from the
 * `prices` table once there is more than one day of scrapes to chart.
 */
export async function GET(_req: NextRequest) {
  return NextResponse.json(
    { message: 'Endpoint retirado. El historial real todavía no está disponible.' },
    { status: 410 },
  );
}
