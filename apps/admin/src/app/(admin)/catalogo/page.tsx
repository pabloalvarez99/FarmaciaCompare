'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { adminApi } from '@/lib/api-client';

interface Medication {
  id: string;
  name: string;
  dosage: string;
  pharmaceuticalForm: string;
  prescriptionRequired: boolean;
  activeIngredient?: { name: string };
}

interface UnmatchedProduct {
  id: string;
  rawName: string;
  sku: string;
  pharmacy: { name: string; chain: string };
}

export default function CatalogoPage() {
  const [tab, setTab] = useState<'search' | 'unmatched'>('search');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Medication[]>([]);
  const [unmatched, setUnmatched] = useState<UnmatchedProduct[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tab === 'unmatched') {
      setLoading(true);
      adminApi.get('/admin/catalog/unmatched')
        .then((r) => setUnmatched(r.data.data || r.data))
        .catch(() => setUnmatched([]))
        .finally(() => setLoading(false));
    }
  }, [tab]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const r = await adminApi.get(`/admin/catalog?q=${encodeURIComponent(query)}`);
      setResults(r.data.data || r.data);
    } catch { setResults([]); }
    setLoading(false);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Catálogo de Medicamentos</h1>

      <div className="flex gap-1 bg-gray-800 rounded-lg p-0.5 mb-6 w-fit">
        <button
          onClick={() => setTab('search')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            tab === 'search' ? 'bg-gray-700 text-white font-medium' : 'text-gray-400 hover:text-white'
          }`}
        >
          Buscar
        </button>
        <button
          onClick={() => setTab('unmatched')}
          className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
            tab === 'unmatched' ? 'bg-gray-700 text-white font-medium' : 'text-gray-400 hover:text-white'
          }`}
        >
          Sin vincular
        </button>
      </div>

      {tab === 'search' && (
        <>
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Buscar por nombre, principio activo o ISP..."
              className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
            />
            <button
              onClick={handleSearch}
              className="px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700"
            >
              Buscar
            </button>
          </div>
          {loading ? (
            <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-800 rounded animate-pulse" />)}</div>
          ) : results.length > 0 ? (
            <Card className="bg-gray-900 border-gray-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-800">
                    <th className="text-left p-3 text-gray-400 font-medium">Medicamento</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Principio activo</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Dosis</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Forma</th>
                    <th className="text-center p-3 text-gray-400 font-medium">Receta</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((m) => (
                    <tr key={m.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                      <td className="p-3 text-white font-medium">{m.name}</td>
                      <td className="p-3 text-gray-300">{m.activeIngredient?.name || '—'}</td>
                      <td className="p-3 text-gray-300">{m.dosage}</td>
                      <td className="p-3 text-gray-300">{m.pharmaceuticalForm}</td>
                      <td className="p-3 text-center">
                        {m.prescriptionRequired ? (
                          <span className="text-xs bg-red-900/30 text-red-400 px-2 py-0.5 rounded">Sí</span>
                        ) : (
                          <span className="text-xs bg-green-900/30 text-green-400 px-2 py-0.5 rounded">No</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ) : query ? (
            <Card className="p-6 bg-gray-900 border-gray-800">
              <p className="text-gray-400 text-center">Sin resultados para &ldquo;{query}&rdquo;</p>
            </Card>
          ) : null}
        </>
      )}

      {tab === 'unmatched' && (
        loading ? (
          <div className="space-y-2">{[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-800 rounded animate-pulse" />)}</div>
        ) : unmatched.length === 0 ? (
          <Card className="p-6 bg-gray-900 border-gray-800">
            <p className="text-gray-400 text-center">Todos los productos están vinculados</p>
          </Card>
        ) : (
          <Card className="bg-gray-900 border-gray-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left p-3 text-gray-400 font-medium">Producto</th>
                  <th className="text-left p-3 text-gray-400 font-medium">SKU</th>
                  <th className="text-left p-3 text-gray-400 font-medium">Farmacia</th>
                  <th className="text-center p-3 text-gray-400 font-medium">Acción</th>
                </tr>
              </thead>
              <tbody>
                {unmatched.map((p) => (
                  <tr key={p.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="p-3 text-white">{p.rawName}</td>
                    <td className="p-3 text-gray-400 font-mono text-xs">{p.sku}</td>
                    <td className="p-3 text-gray-300">{p.pharmacy?.chain || p.pharmacy?.name}</td>
                    <td className="p-3 text-center">
                      <button className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700">
                        Vincular
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )
      )}
    </div>
  );
}
