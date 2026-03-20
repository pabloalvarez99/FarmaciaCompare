'use client';

import { Card } from '@/components/ui/card';
import { formatCLP } from '@/lib/utils';

export default function AnalyticsPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Analytics</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ventas totales</p>
          <p className="text-3xl font-bold mt-1">{formatCLP(0)}</p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Total pedidos</p>
          <p className="text-3xl font-bold mt-1">0</p>
        </Card>
        <Card className="p-6">
          <p className="text-sm text-muted-foreground">Ticket promedio</p>
          <p className="text-3xl font-bold mt-1">{formatCLP(0)}</p>
        </Card>
      </div>
      <Card className="p-6">
        <p className="text-muted-foreground text-center py-8">
          Los gr&aacute;ficos de ventas aparecer&aacute;n cuando haya datos
        </p>
      </Card>
    </div>
  );
}
