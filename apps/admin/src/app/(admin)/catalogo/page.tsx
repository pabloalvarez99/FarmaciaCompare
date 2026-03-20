'use client';

import { Card } from '@/components/ui/card';

export default function CatalogoPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Catálogo de Medicamentos</h1>
      <Card className="p-6 bg-gray-900 border-gray-800">
        <p className="text-gray-400 text-center py-8">
          Busca medicamentos por nombre, principio activo o registro ISP
        </p>
      </Card>
    </div>
  );
}
