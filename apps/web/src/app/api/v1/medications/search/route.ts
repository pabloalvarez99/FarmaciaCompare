import { NextRequest, NextResponse } from 'next/server';
import { searchMedications, MEDICATIONS } from '@/lib/demo-data';

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get('q') ?? '';
  const page = parseInt(req.nextUrl.searchParams.get('page') ?? '1');
  const limit = parseInt(req.nextUrl.searchParams.get('limit') ?? '20');

  const all = searchMedications(q);
  const skip = (page - 1) * limit;
  const results = all.slice(skip, skip + limit).map(m => ({
    id: m.id,
    name: m.name,
    activeIngredientName: m.activeIngredient.name,
    dosage: m.dosage,
    pharmaceuticalForm: m.pharmaceuticalForm,
    prescriptionRequired: m.prescriptionRequired,
    lowestPrice: m.prices.length > 0 ? Math.min(...m.prices.map(p => p.price)) : null,
    highestPrice: m.prices.length > 0 ? Math.max(...m.prices.map(p => p.price)) : null,
    pharmacyCount: m.prices.length,
  }));

  return NextResponse.json({
    results,
    total: all.length,
    page,
    limit,
    totalPages: Math.ceil(all.length / limit),
  });
}
