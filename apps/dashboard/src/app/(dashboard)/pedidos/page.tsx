'use client';

import { Card } from '@/components/ui/card';

export default function PedidosPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Pedidos</h1>
      <Card className="p-6">
        <p className="text-muted-foreground text-center py-8">
          Los pedidos nuevos aparecer&aacute;n aqu&iacute; en tiempo real
        </p>
      </Card>
    </div>
  );
}
