import { notFound } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { PriceTable } from '@/components/prices/PriceTable';
import { PriceHistoryChart } from '@/components/prices/PriceHistoryChart';
import { apiClient } from '@/lib/api-client';
import type { Metadata } from 'next';

interface Props { params: { id: string } }

async function getMedication(id: string) {
  try {
    const { data } = await apiClient.get(`/medications/${id}`);
    return data;
  } catch { return null; }
}

async function getPriceHistory(id: string) {
  try {
    const { data } = await apiClient.get(`/medications/${id}/price-history?days=30`);
    return Array.isArray(data) ? data : [];
  } catch { return []; }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const med = await getMedication(params.id);
  if (!med) return { title: 'Medicamento no encontrado' };
  return {
    title: `${med.name} — Comparar precios | FarmaciaCompare`,
    description: `Compara precios de ${med.name} en Cruz Verde, Salcobrand, Ahumada y más.`,
  };
}

export default async function MedicamentoPage({ params }: Props) {
  const [med, history] = await Promise.all([
    getMedication(params.id),
    getPriceHistory(params.id),
  ]);

  if (!med) notFound();

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{med.name}</h1>
        <p className="text-muted-foreground mt-1">
          {med.activeIngredient?.name} · {med.dosage} · {med.pharmaceuticalForm}
        </p>
        <div className="flex gap-2 mt-2">
          {med.prescriptionRequired && <Badge variant="secondary">Requiere receta</Badge>}
          {med.ispRegistration && <Badge variant="outline">ISP: {med.ispRegistration}</Badge>}
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-3">Precios en farmacias</h2>
      {med.prices?.length > 0 ? (
        <PriceTable prices={med.prices} medicationName={med.name} />
      ) : (
        <p className="text-muted-foreground py-8 text-center">
          No hay precios disponibles para este medicamento.
        </p>
      )}

      {history.length > 0 && <PriceHistoryChart data={history} />}
    </div>
  );
}
