'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatCLP } from '@/lib/utils';

interface OrderItem {
  id: string;
  quantity: number;
  unitPrice: number;
  product: { rawName: string } | null;
}

interface Order {
  id: string;
  status: string;
  totalAmount: number;
  createdAt: string;
  pharmacy: { name: string; chain: string | null };
  items: OrderItem[];
}

const STATUS_MAP: Record<string, { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' }> = {
  pending: { label: 'Pendiente', variant: 'secondary' },
  confirmed: { label: 'Confirmado', variant: 'default' },
  preparing: { label: 'Preparando', variant: 'default' },
  ready: { label: 'Listo para retiro', variant: 'default' },
  dispatched: { label: 'Despachado', variant: 'default' },
  delivered: { label: 'Entregado', variant: 'outline' },
  cancelled: { label: 'Cancelado', variant: 'destructive' },
};

export default function PedidosPage() {
  const router = useRouter();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (!token) { router.push('/login'); return; }
    apiClient
      .get('/orders')
      .then((r) => setOrders(Array.isArray(r.data) ? r.data : r.data.data || []))
      .catch(() => setOrders([]))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-2xl font-bold text-foreground mb-6">Mis Pedidos</h1>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-muted rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-foreground mb-6">Mis Pedidos</h1>

      {orders.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-muted-foreground mb-2">No tienes pedidos todavía</p>
          <p className="text-sm text-muted-foreground">
            Busca un medicamento y compáralo para encontrar el mejor precio
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {orders.map((order) => {
            const status = STATUS_MAP[order.status] || { label: order.status, variant: 'secondary' as const };
            return (
              <Card key={order.id} className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-medium text-foreground truncate">
                        {order.pharmacy?.chain || order.pharmacy?.name}
                      </p>
                      <Badge variant={status.variant}>{status.label}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {new Date(order.createdAt).toLocaleDateString('es-CL', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                      {' · '}
                      {order.items?.length || 0} {order.items?.length === 1 ? 'producto' : 'productos'}
                    </p>
                    {order.items?.slice(0, 2).map((item) => (
                      <p key={item.id} className="text-xs text-muted-foreground mt-0.5 truncate">
                        {item.product?.rawName || 'Producto'} x{item.quantity}
                      </p>
                    ))}
                    {(order.items?.length || 0) > 2 && (
                      <p className="text-xs text-muted-foreground">
                        +{order.items.length - 2} más
                      </p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-lg font-bold text-foreground">{formatCLP(order.totalAmount)}</p>
                    <p className="text-xs text-muted-foreground mt-1">Pedido #{order.id.slice(0, 8)}</p>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
