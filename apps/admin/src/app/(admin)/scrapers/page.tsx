'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { adminApi } from '@/lib/api-client';

interface ScrapingJob {
  id: string;
  pharmacyChain: string;
  status: string;
  startedAt: string | null;
  finishedAt: string | null;
  itemsScraped: number;
  itemsUpdated: number;
}

interface ScraperStats {
  totalJobs24h: number;
  completedJobs: number;
  failedJobs: number;
  activeJobs: number;
  priceUpdates24h: number;
}

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-green-900/30 text-green-400',
  running: 'bg-yellow-900/30 text-yellow-400',
  failed: 'bg-red-900/30 text-red-400',
  pending: 'bg-gray-800 text-gray-400',
};

export default function ScrapersPage() {
  const [stats, setStats] = useState<ScraperStats | null>(null);
  const [jobs, setJobs] = useState<ScrapingJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      adminApi.get('/admin/scrapers/stats').catch(() => ({ data: {} })),
      adminApi.get('/admin/scrapers/jobs').catch(() => ({ data: [] })),
    ]).then(([statsRes, jobsRes]) => {
      setStats(statsRes.data);
      setJobs(Array.isArray(jobsRes.data) ? jobsRes.data : []);
      setLoading(false);
    });
  }, []);

  const statCards = [
    { label: 'Jobs (24h)', value: stats?.totalJobs24h, color: '' },
    { label: 'Completados', value: stats?.completedJobs, color: 'text-green-400' },
    { label: 'Fallidos', value: stats?.failedJobs, color: 'text-red-400' },
    { label: 'En ejecución', value: stats?.activeJobs, color: 'text-yellow-400' },
  ];

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Monitoreo de Scrapers</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {statCards.map((c) => (
          <Card key={c.label} className="p-6 bg-gray-900 border-gray-800">
            <p className="text-sm text-gray-400">{c.label}</p>
            <p className={`text-3xl font-bold mt-1 ${c.color} ${loading ? 'animate-pulse text-gray-600' : ''}`}>
              {loading ? '...' : (c.value ?? 0).toLocaleString('es-CL')}
            </p>
          </Card>
        ))}
      </div>

      <Card className="bg-gray-900 border-gray-800">
        <div className="p-4 border-b border-gray-800">
          <h2 className="font-semibold">Jobs recientes</h2>
        </div>
        {loading ? (
          <div className="p-4 space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />)}</div>
        ) : jobs.length === 0 ? (
          <p className="p-6 text-gray-400 text-center">No hay jobs registrados</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left p-3 text-gray-400 font-medium">Cadena</th>
                <th className="text-center p-3 text-gray-400 font-medium">Estado</th>
                <th className="text-right p-3 text-gray-400 font-medium">Productos</th>
                <th className="text-right p-3 text-gray-400 font-medium">Actualizados</th>
                <th className="text-right p-3 text-gray-400 font-medium">Duración</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const duration = j.startedAt && j.finishedAt
                  ? `${Math.round((new Date(j.finishedAt).getTime() - new Date(j.startedAt).getTime()) / 1000)}s`
                  : j.startedAt ? 'En curso' : '—';
                return (
                  <tr key={j.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="p-3 text-white font-medium">{j.pharmacyChain}</td>
                    <td className="p-3 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[j.status] || 'bg-gray-800 text-gray-400'}`}>
                        {j.status}
                      </span>
                    </td>
                    <td className="p-3 text-right text-gray-300">{j.itemsScraped.toLocaleString('es-CL')}</td>
                    <td className="p-3 text-right text-gray-300">{j.itemsUpdated.toLocaleString('es-CL')}</td>
                    <td className="p-3 text-right text-gray-400">{duration}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
