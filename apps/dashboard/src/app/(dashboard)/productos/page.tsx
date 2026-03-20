'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface Product {
  id: string;
  sku: string;
  rawName: string;
  brand: string | null;
  isActive: boolean;
  prices: { price: number; stockStatus: string | null; recordedAt: string }[];
}

function formatCLP(n: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

export default function ProductosPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    dashboardApi.get(`/dashboard/products?page=${page}`)
      .then((r) => setProducts(r.data.data || r.data))
      .catch(() => setProducts([]))
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Productos</h1>
        <span className="text-sm text-muted-foreground">{products.length} productos</span>
      </div>

      {loading ? (
        <Card className="p-6">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
            ))}
          </div>
        </Card>
      ) : products.length === 0 ? (
        <Card className="p-6">
          <p className="text-muted-foreground text-center py-8">No hay productos registrados</p>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-gray-50">
                  <th className="text-left p-3 font-medium text-gray-600">SKU</th>
                  <th className="text-left p-3 font-medium text-gray-600">Producto</th>
                  <th className="text-left p-3 font-medium text-gray-600">Marca</th>
                  <th className="text-right p-3 font-medium text-gray-600">Precio</th>
                  <th className="text-center p-3 font-medium text-gray-600">Stock</th>
                  <th className="text-center p-3 font-medium text-gray-600">Estado</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const latestPrice = p.prices?.[0];
                  return (
                    <tr key={p.id} className="border-b hover:bg-gray-50">
                      <td className="p-3 font-mono text-xs text-gray-500">{p.sku}</td>
                      <td className="p-3 font-medium">{p.rawName}</td>
                      <td className="p-3 text-gray-500">{p.brand || '—'}</td>
                      <td className="p-3 text-right font-medium">
                        {latestPrice ? formatCLP(latestPrice.price) : '—'}
                      </td>
                      <td className="p-3 text-center">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${
                          latestPrice?.stockStatus === 'in_stock'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-yellow-100 text-yellow-700'
                        }`}>
                          {latestPrice?.stockStatus === 'in_stock' ? 'En stock' : 'Sin stock'}
                        </span>
                      </td>
                      <td className="p-3 text-center">
                        <span className={`w-2 h-2 rounded-full inline-block ${p.isActive ? 'bg-green-500' : 'bg-gray-300'}`} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex justify-between items-center p-3 border-t">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm border rounded disabled:opacity-30"
            >
              Anterior
            </button>
            <span className="text-sm text-gray-500">Página {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={products.length < 20}
              className="px-3 py-1.5 text-sm border rounded disabled:opacity-30"
            >
              Siguiente
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}
