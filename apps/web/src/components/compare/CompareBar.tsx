'use client';
import { useCompare } from '@/hooks/useCompare';
import { getMedicationById } from '@/lib/demo-data';
import { formatCLP } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { X, GitCompareArrows } from 'lucide-react';

export function CompareBar() {
  const { ids, remove, clear } = useCompare();
  const router = useRouter();

  if (ids.length === 0) return null;

  const meds = ids.map((id) => getMedicationById(id)).filter(Boolean);

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-white shadow-lg">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center gap-3 flex-wrap sm:flex-nowrap">
        <div className="flex items-center gap-1.5 text-sm font-medium text-gray-700 shrink-0">
          <GitCompareArrows className="h-4 w-4 text-blue-600" />
          <span>Comparar ({ids.length}/3)</span>
        </div>

        <div className="flex gap-2 flex-1 flex-wrap">
          {meds.map((med) => {
            if (!med) return null;
            return (
              <div
                key={med.id}
                className="flex items-center gap-1.5 bg-blue-50 text-blue-800 text-xs px-2.5 py-1.5 rounded-lg"
              >
                <span className="max-w-[140px] truncate font-medium">{med.name}</span>
                <span className="text-blue-500">
                  {med.prices[0] ? formatCLP(med.prices[0].price) : ''}
                </span>
                <button
                  onClick={() => remove(med.id)}
                  className="ml-0.5 text-blue-400 hover:text-blue-700 transition-colors"
                  aria-label={`Quitar ${med.name}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}

          {/* Empty slots */}
          {Array.from({ length: 3 - ids.length }).map((_, i) => (
            <div
              key={`empty-${i}`}
              className="border-2 border-dashed border-gray-200 text-gray-300 text-xs px-3 py-1.5 rounded-lg"
            >
              + Añadir
            </div>
          ))}
        </div>

        <div className="flex gap-2 shrink-0">
          <button
            onClick={clear}
            className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5 transition-colors"
          >
            Limpiar
          </button>
          <button
            onClick={() =>
              ids.length >= 2
                ? router.push(`/comparar?ids=${ids.join(',')}`)
                : undefined
            }
            disabled={ids.length < 2}
            className="px-4 py-1.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Comparar
          </button>
        </div>
      </div>
    </div>
  );
}
