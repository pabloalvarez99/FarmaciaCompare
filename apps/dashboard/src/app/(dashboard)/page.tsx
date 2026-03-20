'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface Overview {
  totalProducts: number;
  pendingOrders: number;
  revenue30d: number;
  orderCount30d: number;
}

function formatCLP(amount: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(amount);
}

export default function DashboardHome() {
  const [data, setData] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardApi.get('/dashboard/overview')
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  const stats = [
    { label: 'Productos activos', value: data ? data.totalProducts.toLocaleString('es-CL') : '—' },
    { label: 'Pedidos pendientes', value: data ? data.pendingOrders.toLocaleString('es-CL') : '—' },
    { label: 'Ventas (30 días)', value: data ? formatCLP(data.revenue30d) : '—' },
    { label: 'Pedidos (30 días)', value: data ? data.orderCount30d.toLocaleString('es-CL') : '—' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Resumen</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <Card key={s.label} className="p-6">
            <p className="text-sm text-muted-foreground">{s.label}</p>
            <p className={`text-3xl font-bold mt-1 ${loading ? 'animate-pulse text-gray-300' : ''}`}>
              {loading ? '...' : s.value}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
