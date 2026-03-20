'use client';

import { Card } from '@/components/ui/card';

export default function AnomaliasPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Anomalías de Precio</h1>
      <Card className="p-6 bg-gray-900 border-gray-800">
        <p className="text-gray-400 text-center py-8">
          Las anomalías detectadas aparecerán aquí (desviación &gt;50% del
          promedio)
        </p>
      </Card>
    </div>
  );
}
