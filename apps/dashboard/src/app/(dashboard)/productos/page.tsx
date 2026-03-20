'use client';

import { Card } from '@/components/ui/card';

export default function ProductosPage() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Productos</h1>
      </div>
      <Card className="p-6">
        <p className="text-muted-foreground text-center py-8">
          Conecta tu farmacia para ver tus productos
        </p>
      </Card>
    </div>
  );
}
