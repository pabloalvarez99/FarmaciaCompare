'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface Analytics {
  totalRevenue: number;
  totalOrders: number;
  averageOrderValue: number;
  dailyRevenue: { date: string; revenue: number; orders: number }[];
}

function formatCLP(n: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

  useEffect(() => {
    setLoading(true);
    dashboardApi.get(`/dashboard/analytics?days=${days}`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [days]);

  const maxRevenue = data?.dailyRevenue?.length
    ? Math.max(...data.dailyRevenue.map((d) => d.revenue), 1)
    : 1;

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                days === d ? 'bg-white shadow-sm font-medium' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ventas totales</p>
          <p className={`text-3xl font-bold mt-1 ${loading ? 'animate-pulse text-gray-300' : ''}`}>
            {loading ? '...' : formatCLP(data?.totalRevenue ?? 0)}
          </p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Total pedidos</p>
          <p className={`text-3xl font-bold mt-1 ${loading ? 'animate-pulse text-gray-300' : ''}`}>
            {loading ? '...' : (data?.totalOrders ?? 0).toLocaleString('es-CL')}
          </p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ticket promedio</p>
          <p className={`text-3xl font-bold mt-1 ${loading ? 'animate-pulse text-gray-300' : ''}`}>
            {loading ? '...' : formatCLP(data?.averageOrderValue ?? 0)}
          </p>
        </Card>
      </div>

      <Card className="p-6">
        <h2 className="text-sm font-medium text-gray-600 mb-4">Ventas diarias</h2>
        {!data?.dailyRevenue?.length ? (
          <p className="text-muted-foreground text-center py-8">
            Los datos aparecerán cuando haya ventas
          </p>
        ) : (
          <div className="flex items-end gap-1 h-48">
            {data.dailyRevenue.map((day) => (
              <div key={day.date} className="flex-1 flex flex-col items-center gap-1 group">
                <div className="hidden group-hover:block text-xs bg-gray-800 text-white px-2 py-1 rounded whitespace-nowrap">
                  {formatCLP(day.revenue)} · {day.orders} pedidos
                </div>
                <div
                  className="w-full bg-blue-500 rounded-t transition-all hover:bg-blue-600"
                  style={{ height: `${(day.revenue / maxRevenue) * 100}%`, minHeight: day.revenue > 0 ? '4px' : '0' }}
                />
                <span className="text-[10px] text-gray-400 -rotate-45 origin-top-left">
                  {new Date(day.date).toLocaleDateString('es-CL', { day: '2-digit', month: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
