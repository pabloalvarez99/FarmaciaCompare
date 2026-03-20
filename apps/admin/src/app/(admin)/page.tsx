'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { adminApi } from '@/lib/api-client';

interface Stats {
  totalMedications: number;
  unmatchedProducts: number;
  activeScrapers: number;
  anomalies: number;
}

export default function AdminHome() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminApi.get('/admin/catalog/search?q=&page=1&limit=1').catch(() => ({ data: { total: 0 } })),
      adminApi.get('/admin/catalog/unmatched?page=1&limit=1').catch(() => ({ data: { total: 0 } })),
      adminApi.get('/admin/scrapers/stats').catch(() => ({ data: { activeJobs: 0 } })),
      adminApi.get('/admin/anomalies').catch(() => ({ data: [] })),
    ]).then(([meds, unmatched, scrapers, anomalies]) => {
      setStats({
        totalMedications: meds.data.total || 0,
        unmatchedProducts: unmatched.data.total || 0,
        activeScrapers: scrapers.data.activeJobs || 0,
        anomalies: Array.isArray(anomalies.data) ? anomalies.data.length : 0,
      });
      setLoading(false);
    });
  }, []);

  const cards = [
    { label: 'Total medicamentos', value: stats?.totalMedications },
    { label: 'Productos sin vincular', value: stats?.unmatchedProducts },
    { label: 'Scrapers activos', value: stats?.activeScrapers },
    { label: 'Anomalías detectadas', value: stats?.anomalies },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <Card key={c.label} className="p-6 bg-gray-900 border-gray-800">
            <p className="text-sm text-gray-400">{c.label}</p>
            <p className={`text-3xl font-bold mt-1 ${loading ? 'animate-pulse text-gray-600' : ''}`}>
              {loading ? '...' : (c.value ?? 0).toLocaleString('es-CL')}
            </p>
          </Card>
        ))}
      </div>
    </div>
  );
}
