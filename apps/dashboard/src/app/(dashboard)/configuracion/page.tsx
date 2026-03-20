'use client';

import { Card } from '@/components/ui/card';

export default function ConfiguracionPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Configuraci&oacute;n</h1>
      <Card className="p-6">
        <p className="text-muted-foreground text-center py-8">
          Configura los datos de tu farmacia
        </p>
      </Card>
    </div>
  );
}
