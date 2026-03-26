import { NextRequest, NextResponse } from 'next/server';
import { getMedicationById } from '@/lib/demo-data';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const med = getMedicationById(params.id);
  if (!med) return NextResponse.json([], { status: 200 });

  // Generate 30 days of price history for each pharmacy (top 5 cheapest)
  const top5 = med.prices.slice(0, 5);
  const now = Date.now();
  const history = top5.flatMap(p =>
    Array.from({ length: 10 }, (_, i) => ({
      pharmacyName: p.pharmacyName,
      pharmacyChain: p.pharmacyChain,
      price: Math.round((p.price * (1 + (Math.sin(i + p.price) * 0.06))) / 10) * 10,
      recordedAt: new Date(now - (9 - i) * 3 * 24 * 60 * 60 * 1000).toISOString(),
    }))
  );

  return NextResponse.json(history);
}
