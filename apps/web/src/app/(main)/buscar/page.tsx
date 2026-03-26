import { Suspense } from 'react';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';
import { MedicationCard } from '@/components/search/MedicationCard';
import { MEDICATIONS } from '@/lib/demo-data';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Buscar medicamentos — FarmaciaCompare',
  description: 'Busca y compara precios de medicamentos en Cruz Verde, Salcobrand, Ahumada, Dr. Simi y farmacias independientes de Chile.',
};

interface Props {
  searchParams: { q?: string; page?: string; receta?: string };
}

export default function BuscarPage({ searchParams }: Props) {
  const query = searchParams.q ?? '';
  const page = parseInt(searchParams.page ?? '1');
  const receta = searchParams.receta;

  const withReceta = MEDICATIONS.filter((m) => m.prescriptionRequired).length;
  const sinReceta = MEDICATIONS.filter((m) => !m.prescriptionRequired).length;

  const allMeds = MEDICATIONS.filter((m) => {
    if (receta === 'si') return m.prescriptionRequired;
    if (receta === 'no') return !m.prescriptionRequired;
    return true;
  }).map((m) => ({
    id: m.id,
    name: m.name,
    activeIngredientName: m.activeIngredient.name,
    dosage: m.dosage,
    pharmaceuticalForm: m.pharmaceuticalForm,
    prescriptionRequired: m.prescriptionRequired,
    lowestPrice: m.prices[0]?.price ?? null,
    highestPrice: m.prices[m.prices.length - 1]?.price ?? null,
    pharmacyCount: m.prices.length,
  }));

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <SearchBar defaultValue={query} />
      </div>

      {query.length >= 2 ? (
        <Suspense
          fallback={
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="border rounded-lg p-4 animate-pulse bg-gray-50 h-24" />
              ))}
            </div>
          }
        >
          <SearchResults query={query} page={page} />
        </Suspense>
      ) : (
        <div>
          <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
            <p className="text-sm text-gray-500">
              {allMeds.length} medicamentos disponibles
            </p>
            <div className="flex gap-2 flex-wrap">
              <Link
                href="/buscar"
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  !receta
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Todos ({MEDICATIONS.length})
              </Link>
              <Link
                href="/buscar?receta=no"
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  receta === 'no'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Sin receta ({sinReceta})
              </Link>
              <Link
                href="/buscar?receta=si"
                className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  receta === 'si'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Con receta ({withReceta})
              </Link>
            </div>
          </div>

          <div className="space-y-3">
            {allMeds.map((med) => (
              <MedicationCard key={med.id} med={med} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
