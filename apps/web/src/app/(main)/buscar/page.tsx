import { Suspense } from 'react';
import { SearchBar } from '@/components/search/SearchBar';
import { SearchResults } from '@/components/search/SearchResults';
import { MedicationCard } from '@/components/search/MedicationCard';
import { MEDICATIONS } from '@/lib/demo-data';
import { CATEGORIES, MED_CATEGORIES } from '@/lib/categories';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Buscar medicamentos — FarmaciaCompare',
  description:
    'Busca y compara precios de medicamentos en Cruz Verde, Salcobrand, Ahumada, Dr. Simi y farmacias independientes de Chile.',
};

interface Props {
  searchParams: { q?: string; page?: string; receta?: string; cat?: string };
}

export default function BuscarPage({ searchParams }: Props) {
  const query = searchParams.q ?? '';
  const page = parseInt(searchParams.page ?? '1');
  const receta = searchParams.receta;
  const cat = searchParams.cat;

  const withReceta = MEDICATIONS.filter((m) => m.prescriptionRequired).length;
  const sinReceta = MEDICATIONS.filter((m) => !m.prescriptionRequired).length;

  const allMeds = MEDICATIONS.filter((m) => {
    if (receta === 'si' && !m.prescriptionRequired) return false;
    if (receta === 'no' && m.prescriptionRequired) return false;
    if (cat && MED_CATEGORIES[m.id] !== cat) return false;
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

  // Build href helper that preserves existing params
  const filterHref = (overrides: Record<string, string | undefined>) => {
    const params = new URLSearchParams();
    const merged = { receta, cat, ...overrides };
    for (const [k, v] of Object.entries(merged)) {
      if (v) params.set(k, v);
    }
    const qs = params.toString();
    return `/buscar${qs ? `?${qs}` : ''}`;
  };

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
          {/* Category pills */}
          <div className="mb-4 overflow-x-auto pb-1">
            <div className="flex gap-2 min-w-max">
              <Link
                href="/buscar"
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  !cat && !receta
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Todos ({MEDICATIONS.length})
              </Link>
              <Link
                href={filterHref({ cat: undefined, receta: 'no' })}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  receta === 'no' && !cat
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Sin receta ({sinReceta})
              </Link>
              <Link
                href={filterHref({ cat: undefined, receta: 'si' })}
                className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                  receta === 'si' && !cat
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Con receta ({withReceta})
              </Link>
              <div className="w-px bg-gray-200 self-stretch mx-1" />
              {CATEGORIES.map((c) => {
                const count = MEDICATIONS.filter((m) => MED_CATEGORIES[m.id] === c.id).length;
                if (count === 0) return null;
                return (
                  <Link
                    key={c.id}
                    href={filterHref({ cat: c.id, receta: undefined })}
                    className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                      cat === c.id
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {c.emoji} {c.label} ({count})
                  </Link>
                );
              })}
            </div>
          </div>

          <p className="text-xs text-gray-400 mb-3">{allMeds.length} resultados</p>

          <div className="space-y-3">
            {allMeds.map((med) => (
              <MedicationCard key={med.id} med={med} />
            ))}
            {allMeds.length === 0 && (
              <div className="text-center py-12 text-muted-foreground">
                <p>No hay medicamentos en esta categoría.</p>
                <Link href="/buscar" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
                  Ver todos
                </Link>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
