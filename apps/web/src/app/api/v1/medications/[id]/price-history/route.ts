import { NextRequest, NextResponse } from 'next/server';
import { getPriceHistory } from '@/lib/demo-data';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  return NextResponse.json(getPriceHistory(params.id));
}
