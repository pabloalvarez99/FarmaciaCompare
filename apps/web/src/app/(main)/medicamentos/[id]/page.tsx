import { notFound } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { PriceTable } from '@/components/prices/PriceTable';
import { PriceHistoryChart } from '@/components/prices/PriceHistoryChart';
import { getMedicationById, getPriceHistory, MEDICATIONS } from '@/lib/demo-data';
import { formatCLP } from '@/lib/utils';
import type { Metadata } from 'next';
import Link from 'next/link';

interface Props { params: { id: string } }

export function generateStaticParams() {
  return MEDICATIONS.map((m) => ({ id: m.id }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const med = getMedicationById(params.id);
  if (!med) return { title: 'Medicamento no encontrado' };
  return {
    title: `${med.name} — Comparar precios | FarmaciaCompare`,
    description: `Compara precios de ${med.name} (${med.activeIngredient.name} ${med.dosage}) en Cruz Verde, Salcobrand, Ahumada, Dr. Simi y farmacias independientes de Chile.`,
  };
}

export default function MedicamentoPage({ params }: Props) {
  const med = getMedicationById(params.id);
  if (!med) notFound();

  const history = getPriceHistory(params.id);
  const lowestPrice = med.prices[0]?.price;
  const highestPrice = med.prices[med.prices.length - 1]?.price;
  const savings = highestPrice && lowestPrice ? highestPrice - lowestPrice : null;

  // Related: same active ingredient, different medication
  const related = MEDICATIONS.filter(
    (m) =>
      m.id !== med.id &&
      m.activeIngredient.name === med.activeIngredient.name
  ).slice(0, 3);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* Breadcrumb */}
      <nav className="text-sm text-muted-foreground mb-6">
        <Link href="/" className="hover:text-foreground">Inicio</Link>
        <span className="mx-2">/</span>
        <Link href="/buscar" className="hover:text-foreground">Medicamentos</Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">{med.name}</span>
      </nav>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{med.name}</h1>
        <p className="text-muted-foreground mt-1">
          {med.activeIngredient.name} · {med.dosage} · {med.pharmaceuticalForm}
        </p>
        <div className="flex gap-2 mt-2 flex-wrap">
          {med.prescriptionRequired && <Badge variant="secondary">Requiere receta</Badge>}
          {med.ispRegistration && <Badge variant="outline">ISP: {med.ispRegistration}</Badge>}
        </div>
      </div>

      {/* Price summary banner */}
      {lowestPrice && (
        <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <p className="text-sm text-blue-700 font-medium">Mejor precio disponible</p>
            <p className="text-3xl font-bold text-blue-800">
              ${lowestPrice.toLocaleString('es-CL')}
            </p>
            <p className="text-xs text-blue-600 mt-0.5">{med.prices[0]?.pharmacyName} · {med.prices[0]?.pharmacyCity}</p>
          </div>
          {savings && savings > 0 && (
            <div className="text-right">
              <p className="text-sm text-gray-500">Ahorro máximo vs precio más caro</p>
              <p className="text-xl font-semibold text-green-600">
                −${savings.toLocaleString('es-CL')}
              </p>
              <p className="text-xs text-gray-400">comparando {med.prices.length} farmacias</p>
            </div>
          )}
        </div>
      )}

      <h2 className="text-lg font-semibold mb-3">Precios en farmacias</h2>
      {med.prices.length > 0 ? (
        <PriceTable prices={med.prices} medicationName={med.name} />
      ) : (
        <p className="text-muted-foreground py-8 text-center">
          No hay precios disponibles para este medicamento.
        </p>
      )}

      {history.length > 0 && <PriceHistoryChart data={history} />}

      {related.length > 0 && (
        <div className="mt-10">
          <h2 className="text-lg font-semibold mb-3">
            Otros productos con {med.activeIngredient.name}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {related.map((r) => (
              <Link key={r.id} href={`/medicamentos/${r.id}`}>
                <div className="border rounded-lg p-3 hover:border-blue-300 hover:shadow-sm transition-all bg-white">
                  <p className="font-medium text-sm text-gray-900 leading-tight">{r.name}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{r.dosage} · {r.pharmaceuticalForm}</p>
                  {r.prices[0] && (
                    <p className="text-blue-600 font-bold text-sm mt-2">
                      Desde {formatCLP(r.prices[0].price)}
                    </p>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
