'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { adminApi } from '@/lib/api-client';

interface Anomaly {
  productId: string;
  productName: string;
  pharmacyName: string;
  currentPrice: number;
  averagePrice: number;
  deviationPct: number;
  recordedAt: string;
}

function formatCLP(n: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

export default function AnomaliasPage() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.get('/admin/anomalies')
      .then((r) => setAnomalies(Array.isArray(r.data) ? r.data : []))
      .catch(() => setAnomalies([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Anomalías de Precio</h1>
        <span className="text-sm text-gray-400">
          Desviación &gt;50% del promedio
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-16 bg-gray-800 rounded animate-pulse" />)}</div>
      ) : anomalies.length === 0 ? (
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-gray-400 text-center py-8">No se detectaron anomalías de precio</p>
        </Card>
      ) : (
        <div className="space-y-2">
          {anomalies.map((a, i) => (
            <Card key={`${a.productId}-${i}`} className="p-4 bg-gray-900 border-gray-800">
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-white truncate">{a.productName}</p>
                  <p className="text-sm text-gray-400">{a.pharmacyName}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 line-through text-sm">{formatCLP(a.averagePrice)}</span>
                    <span className="font-bold text-white">{formatCLP(a.currentPrice)}</span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    a.deviationPct > 0
                      ? 'bg-red-900/30 text-red-400'
                      : 'bg-green-900/30 text-green-400'
                  }`}>
                    {a.deviationPct > 0 ? '+' : ''}{a.deviationPct.toFixed(0)}%
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
