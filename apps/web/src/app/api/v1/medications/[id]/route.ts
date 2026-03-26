import { NextRequest, NextResponse } from 'next/server';
import { getMedicationById } from '@/lib/demo-data';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const med = getMedicationById(params.id);
  if (!med) return NextResponse.json({ message: 'Not found' }, { status: 404 });
  return NextResponse.json(med);
}
