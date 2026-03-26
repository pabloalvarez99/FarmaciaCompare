import { notFound } from 'next/navigation';
import { getMedicationById } from '@/lib/demo-data';
import { formatCLP } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Comparar medicamentos — FarmaciaCompare',
};

interface Props {
  searchParams: { ids?: string };
}

const CHAIN_COLORS: Record<string, string> = {
  cruz_verde: 'bg-green-100 text-green-800',
  salcobrand: 'bg-blue-100 text-blue-800',
  ahumada: 'bg-orange-100 text-orange-800',
  dr_simi: 'bg-yellow-100 text-yellow-800',
  knop: 'bg-purple-100 text-purple-800',
};

export default function CompararPage({ searchParams }: Props) {
  const ids = (searchParams.ids ?? '').split(',').filter(Boolean).slice(0, 3);

  if (ids.length < 2) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center">
        <p className="text-4xl mb-4">🔍</p>
        <h1 className="text-xl font-semibold text-gray-900 mb-2">Selecciona medicamentos para comparar</h1>
        <p className="text-gray-500 mb-6">Necesitas al menos 2 medicamentos. Agrégarlos desde la ficha de cada medicamento.</p>
        <Link href="/buscar" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
          Buscar medicamentos
        </Link>
      </div>
    );
  }

  const meds = ids.map((id) => getMedicationById(id));
  if (meds.some((m) => !m)) notFound();
  const medications = meds as NonNullable<typeof meds[0]>[];

  // Collect all pharmacy IDs present in any of the medications
  const allPharmacyIds = Array.from(
    new Set(medications.flatMap((m) => m.prices.map((p) => p.pharmacyId)))
  );
  // Build a lookup: pharmacyId → price per medication
  const priceMatrix = medications.map((m) => {
    const map: Record<string, number> = {};
    for (const p of m.prices) map[p.pharmacyId] = p.price;
    return map;
  });

  // Sort pharmacies by average price across all meds
  const pharmacies = allPharmacyIds.map((phId) => {
    const firstMed = medications.find((m) => m.prices.some((p) => p.pharmacyId === phId));
    const phInfo = firstMed?.prices.find((p) => p.pharmacyId === phId);
    const prices = priceMatrix.map((pm) => pm[phId] ?? null);
    const available = prices.filter((p): p is number => p !== null);
    const avgPrice = available.length ? available.reduce((a, b) => a + b, 0) / available.length : Infinity;
    return { phId, phInfo, prices, avgPrice };
  }).sort((a, b) => a.avgPrice - b.avgPrice);

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="text-sm text-muted-foreground mb-6">
        <Link href="/" className="hover:text-foreground">Inicio</Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">Comparar medicamentos</span>
      </nav>

      <h1 className="text-2xl font-bold text-gray-900 mb-6">Comparación de precios</h1>

      {/* Medication headers */}
      <div className="grid gap-4 mb-6" style={{ gridTemplateColumns: `200px repeat(${medications.length}, 1fr)` }}>
        <div /> {/* empty corner */}
        {medications.map((med) => (
          <div key={med.id} className="bg-blue-50 rounded-xl p-4 border border-blue-100">
            <Link href={`/medicamentos/${med.id}`} className="hover:underline">
              <h2 className="font-semibold text-gray-900 text-sm leading-tight">{med.name}</h2>
            </Link>
            <p className="text-xs text-gray-500 mt-1">{med.activeIngredient.name} · {med.dosage}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {med.prescriptionRequired && <Badge variant="secondary" className="text-xs">Receta</Badge>}
            </div>
            <div className="mt-3">
              <p className="text-xs text-gray-400">Mejor precio</p>
              <p className="text-xl font-bold text-blue-700">{formatCLP(med.prices[0]?.price ?? 0)}</p>
              <p className="text-xs text-gray-400">{med.prices[0]?.pharmacyName}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Price matrix */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">Precios por farmacia</h2>
      <div className="border rounded-xl overflow-hidden">
        <div
          className="grid bg-gray-50 text-xs text-gray-500 font-medium"
          style={{ gridTemplateColumns: `1fr repeat(${medications.length}, 1fr)` }}
        >
          <div className="px-4 py-3">Farmacia</div>
          {medications.map((med) => (
            <div key={med.id} className="px-4 py-3 text-center truncate">{med.name}</div>
          ))}
        </div>
        {pharmacies.map(({ phId, phInfo, prices }, rowIdx) => (
          <div
            key={phId}
            className={`grid divide-x border-t ${rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
            style={{ gridTemplateColumns: `1fr repeat(${medications.length}, 1fr)` }}
          >
            <div className="px-4 py-3">
              <p className="text-sm font-medium text-gray-900 leading-tight">{phInfo?.pharmacyName}</p>
              <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                {phInfo?.pharmacyChain && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${CHAIN_COLORS[phInfo.pharmacyChain] ?? 'bg-gray-100 text-gray-600'}`}>
                    {phInfo.pharmacyChain.replace('_', ' ')}
                  </span>
                )}
                {phInfo?.pharmacyCity && (
                  <span className="text-xs text-gray-400">{phInfo.pharmacyCity}</span>
                )}
              </div>
            </div>
            {prices.map((price, medIdx) => {
              // Highlight the lowest price in this row
              const rowPrices = prices.filter((p): p is number => p !== null);
              const isLowest = price !== null && rowPrices.length > 0 && price === Math.min(...rowPrices);
              return (
                <div key={medIdx} className="px-4 py-3 text-center flex items-center justify-center">
                  {price !== null ? (
                    <span className={`font-semibold text-sm ${isLowest ? 'text-green-600' : 'text-gray-800'}`}>
                      {formatCLP(price)}
                    </span>
                  ) : (
                    <span className="text-gray-300 text-sm">—</span>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Savings summary */}
      <div className="mt-6 grid gap-4" style={{ gridTemplateColumns: `repeat(${medications.length}, 1fr)` }}>
        {medications.map((med) => {
          const lowest = med.prices[0]?.price;
          const highest = med.prices[med.prices.length - 1]?.price;
          const saving = lowest && highest ? highest - lowest : 0;
          return (
            <div key={med.id} className="bg-green-50 border border-green-100 rounded-xl p-4">
              <p className="text-xs text-green-700 font-medium mb-1">{med.name}</p>
              <p className="text-sm text-gray-600">
                Ahorro máximo: <span className="font-bold text-green-700">−{formatCLP(saving)}</span>
              </p>
              <p className="text-xs text-gray-400 mt-0.5">
                entre {med.prices.length} farmacias
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex gap-3">
        <Link href="/buscar" className="text-sm text-blue-600 hover:underline">
          ← Buscar más medicamentos
        </Link>
      </div>
    </div>
  );
}
