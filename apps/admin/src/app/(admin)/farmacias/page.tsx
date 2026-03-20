'use client';

import { Card } from '@/components/ui/card';

export default function FarmaciasPage() {
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Farmacias</h1>
      </div>
      <Card className="p-6 bg-gray-900 border-gray-800">
        <p className="text-gray-400 text-center py-8">
          Lista de farmacias registradas en la plataforma
        </p>
      </Card>
    </div>
  );
}
