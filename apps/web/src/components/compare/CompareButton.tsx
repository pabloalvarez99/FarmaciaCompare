'use client';
import { useCompare } from '@/hooks/useCompare';
import { GitCompareArrows } from 'lucide-react';

export function CompareButton({ medicationId }: { medicationId: string }) {
  const { toggle, isSelected, isFull } = useCompare();
  const selected = isSelected(medicationId);

  return (
    <button
      onClick={() => toggle(medicationId)}
      disabled={!selected && isFull}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
        selected
          ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700'
          : isFull
            ? 'bg-gray-50 text-gray-300 border-gray-200 cursor-not-allowed'
            : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600'
      }`}
      title={isFull && !selected ? 'Máximo 3 medicamentos para comparar' : undefined}
    >
      <GitCompareArrows className="h-3 w-3" />
      {selected ? 'Comparando' : 'Comparar'}
    </button>
  );
}
