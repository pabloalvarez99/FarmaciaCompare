'use client';

import { Card } from '@/components/ui/card';

export default function PreciosPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Precios</h1>
      <Card className="p-6">
        <p className="text-muted-foreground text-center py-8">
          Gestiona los precios de tus productos aqu&iacute;
        </p>
      </Card>
    </div>
  );
}
