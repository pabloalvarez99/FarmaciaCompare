'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface OrderItem {
  id: string;
  quantity: number;
  unitPrice: number;
  pharmacyProduct: { rawName: string };
}

interface Order {
  id: string;
  status: string;
  type: string;
  total: number;
  createdAt: string;
  user: { name: string | null; email: string };
  items: OrderItem[];
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pendiente',
  confirmed: 'Confirmado',
  preparing: 'Preparando',
  ready: 'Listo',
  dispatched: 'Despachado',
  delivered: 'Entregado',
  cancelled: 'Cancelado',
};

const STATUS_COLORS: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  confirmed: 'bg-blue-100 text-blue-700',
  preparing: 'bg-purple-100 text-purple-700',
  ready: 'bg-green-100 text-green-700',
  dispatched: 'bg-indigo-100 text-indigo-700',
  delivered: 'bg-gray-100 text-gray-700',
  cancelled: 'bg-red-100 text-red-700',
};

const NEXT_STATUS: Record<string, string> = {
  pending: 'confirmed',
  confirmed: 'preparing',
  preparing: 'ready',
  ready: 'dispatched',
};

function formatCLP(n: number) {
  return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 }).format(n);
}

export default function PedidosPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchOrders = useCallback(() => {
    dashboardApi.get('/dashboard/orders')
      .then((r) => setOrders(r.data))
      .catch(() => setOrders([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchOrders();
    const interval = setInterval(fetchOrders, 15000);
    return () => clearInterval(interval);
  }, [fetchOrders]);

  const advanceStatus = async (orderId: string, nextStatus: string) => {
    try {
      await dashboardApi.put(`/dashboard/orders/${orderId}/status`, { status: nextStatus });
      fetchOrders();
    } catch (e) {
      console.error('Error updating order status', e);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Pedidos</h1>
        <button onClick={fetchOrders} className="px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
          Actualizar
        </button>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-24 bg-gray-100 rounded animate-pulse" />)}
        </div>
      ) : orders.length === 0 ? (
        <Card className="p-6">
          <p className="text-muted-foreground text-center py-8">No hay pedidos pendientes</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => (
            <Card key={order.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-xs text-gray-400">#{order.id.slice(0, 8)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[order.status] || 'bg-gray-100'}`}>
                      {STATUS_LABELS[order.status] || order.status}
                    </span>
                    <span className="text-xs text-gray-400">
                      {order.type === 'delivery' ? 'Despacho' : 'Retiro'}
                    </span>
                  </div>
                  <p className="text-sm font-medium">{order.user.name || order.user.email}</p>
                  <div className="mt-1 text-xs text-gray-500">
                    {order.items.map((item) => (
                      <span key={item.id} className="mr-2">
                        {item.quantity}x {item.pharmacyProduct.rawName}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className="font-bold">{formatCLP(order.total)}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {new Date(order.createdAt).toLocaleString('es-CL', { hour: '2-digit', minute: '2-digit' })}
                  </p>
                  {NEXT_STATUS[order.status] && (
                    <button
                      onClick={() => advanceStatus(order.id, NEXT_STATUS[order.status])}
                      className="mt-2 px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      {STATUS_LABELS[NEXT_STATUS[order.status]]}
                    </button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
