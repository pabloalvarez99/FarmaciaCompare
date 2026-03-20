'use client';

import { Card } from '@/components/ui/card';

export default function ScrapersPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Monitoreo de Scrapers</h1>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Jobs hoy</p>
          <p className="text-3xl font-bold mt-1">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Completados</p>
          <p className="text-3xl font-bold mt-1 text-green-400">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">Fallidos</p>
          <p className="text-3xl font-bold mt-1 text-red-400">&mdash;</p>
        </Card>
        <Card className="p-6 bg-gray-900 border-gray-800">
          <p className="text-sm text-gray-400">En ejecución</p>
          <p className="text-3xl font-bold mt-1 text-yellow-400">&mdash;</p>
        </Card>
      </div>
    </div>
  );
}
