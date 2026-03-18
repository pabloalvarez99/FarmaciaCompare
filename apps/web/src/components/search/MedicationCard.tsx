import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { formatCLP } from '@/lib/utils';

interface MedicationSearchResult {
  id: string; name: string; activeIngredientName: string | null;
  dosage: string | null; pharmaceuticalForm: string | null;
  prescriptionRequired: boolean; lowestPrice: number | null;
  highestPrice: number | null; pharmacyCount: number;
}

export function MedicationCard({ med }: { med: MedicationSearchResult }) {
  return (
    <Link href={`/medicamentos/${med.id}`}>
      <div className="border rounded-lg p-4 hover:border-primary hover:shadow-sm transition-all bg-white cursor-pointer">
        <div className="flex justify-between items-start gap-2">
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-gray-900 truncate">{med.name}</h3>
            <p className="text-sm text-muted-foreground mt-0.5">
              {med.activeIngredientName} · {med.dosage} · {med.pharmaceuticalForm}
            </p>
          </div>
          {med.prescriptionRequired && <Badge variant="secondary" className="shrink-0 text-xs">Receta</Badge>}
        </div>
        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm text-muted-foreground">{med.pharmacyCount} {med.pharmacyCount === 1 ? 'farmacia' : 'farmacias'}</div>
          {med.lowestPrice ? (
            <div className="text-right">
              <span className="text-xs text-muted-foreground">Desde </span>
              <span className="font-bold text-primary text-lg">{formatCLP(med.lowestPrice)}</span>
            </div>
          ) : <span className="text-sm text-muted-foreground">Sin precio</span>}
        </div>
      </div>
    </Link>
  );
}
