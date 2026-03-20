'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface Product {
  id: string;
  sku: string;
  rawName: string;
  prices: { price: number; originalPrice: number | null; stockStatus: string | null }[];
}

function formatCLP(n: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

export default function PreciosPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [newPrice, setNewPrice] = useState('');

  useEffect(() => {
    dashboardApi.get('/dashboard/products?page=1')
      .then((r) => setProducts(r.data.data || r.data))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, []);

  const updatePrice = async (productId: string) => {
    const price = parseInt(newPrice, 10);
    if (isNaN(price) || price <= 0) return;
    try {
      await dashboardApi.put(`/dashboard/products/${productId}/price`, { price });
      setProducts((prev) =>
        prev.map((p) =>
          p.id === productId
            ? { ...p, prices: [{ price, originalPrice: null, stockStatus: 'in_stock' }, ...p.prices] }
            : p,
        ),
      );
      setEditing(null);
      setNewPrice('');
    } catch (e) {
      console.error('Error updating price', e);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Gestión de Precios</h1>

      {loading ? (
        <Card className="p-6">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />)}
          </div>
        </Card>
      ) : products.length === 0 ? (
        <Card className="p-6">
          <p className="text-muted-foreground text-center py-8">No hay productos para gestionar precios</p>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-3 font-medium text-gray-600">Producto</th>
                  <th className="text-right p-3 font-medium text-gray-600">Precio actual</th>
                  <th className="text-right p-3 font-medium text-gray-600">Precio original</th>
                  <th className="text-center p-3 font-medium text-gray-600">Acción</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const latest = p.prices?.[0];
                  return (
                    <tr key={p.id} className="border-b hover:bg-gray-50">
                      <td className="p-3">
                        <p className="font-medium">{p.rawName}</p>
                        <p className="text-xs text-gray-400 font-mono">{p.sku}</p>
                      </td>
                      <td className="p-3 text-right font-medium">
                        {latest ? formatCLP(latest.price) : '—'}
                      </td>
                      <td className="p-3 text-right text-gray-400">
                        {latest?.originalPrice ? formatCLP(latest.originalPrice) : '—'}
                      </td>
                      <td className="p-3 text-center">
                        {editing === p.id ? (
                          <div className="flex items-center gap-1 justify-center">
                            <input
                              type="number"
                              value={newPrice}
                              onChange={(e) => setNewPrice(e.target.value)}
                              className="w-24 px-2 py-1 border rounded text-sm text-right"
                              placeholder="Precio"
                              autoFocus
                            />
                            <button
                              onClick={() => updatePrice(p.id)}
                              className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                            >
                              OK
                            </button>
                            <button
                              onClick={() => { setEditing(null); setNewPrice(''); }}
                              className="px-2 py-1 text-xs border rounded hover:bg-gray-50"
                            >
                              X
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => { setEditing(p.id); setNewPrice(latest?.price?.toString() || ''); }}
                            className="px-3 py-1 text-xs border rounded hover:bg-gray-50"
                          >
                            Editar
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
