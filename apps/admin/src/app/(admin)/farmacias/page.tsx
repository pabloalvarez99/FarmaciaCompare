'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { adminApi } from '@/lib/api-client';

interface Pharmacy {
  id: string;
  name: string;
  chain: string | null;
  type: string;
  city: string | null;
  region: string | null;
  isActive: boolean;
  saasActive: boolean;
  saasPlan: string | null;
  _count?: { products: number; staff: number };
}

export default function FarmaciasPage() {
  const [pharmacies, setPharmacies] = useState<Pharmacy[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    adminApi.get('/admin/pharmacies')
      .then((r) => setPharmacies(Array.isArray(r.data) ? r.data : []))
      .catch(() => setPharmacies([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Farmacias</h1>
        <span className="text-sm text-gray-400">{pharmacies.length} registradas</span>
      </div>

      {loading ? (
        <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-800 rounded animate-pulse" />)}</div>
      ) : pharmacies.length === 0 ? (
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-gray-400 text-center py-8">No hay farmacias registradas</p>
        </Card>
      ) : (
        <Card className="bg-gray-900 border-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left p-3 text-gray-400 font-medium">Farmacia</th>
                <th className="text-left p-3 text-gray-400 font-medium">Cadena</th>
                <th className="text-left p-3 text-gray-400 font-medium">Ciudad</th>
                <th className="text-center p-3 text-gray-400 font-medium">Tipo</th>
                <th className="text-center p-3 text-gray-400 font-medium">SaaS</th>
                <th className="text-center p-3 text-gray-400 font-medium">Estado</th>
              </tr>
            </thead>
            <tbody>
              {pharmacies.map((p) => (
                <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                  <td className="p-3 text-white font-medium">{p.name}</td>
                  <td className="p-3 text-gray-300">{p.chain || '—'}</td>
                  <td className="p-3 text-gray-300">{p.city || '—'}</td>
                  <td className="p-3 text-center">
                    <span className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded">{p.type}</span>
                  </td>
                  <td className="p-3 text-center">
                    {p.saasActive ? (
                      <span className="text-xs bg-green-900/30 text-green-400 px-2 py-0.5 rounded">
                        {p.saasPlan || 'Activo'}
                      </span>
                    ) : (
                      <span className="text-xs bg-gray-800 text-gray-500 px-2 py-0.5 rounded">No</span>
                    )}
                  </td>
                  <td className="p-3 text-center">
                    <span className={`w-2 h-2 rounded-full inline-block ${p.isActive ? 'bg-green-500' : 'bg-gray-500'}`} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
