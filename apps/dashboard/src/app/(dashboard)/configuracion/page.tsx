'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';

export default function ConfiguracionPage() {
  const [form, setForm] = useState({
    pharmacyName: '',
    address: '',
    city: '',
    phone: '',
    email: '',
    hasDelivery: false,
    hasPickup: true,
  });
  const [saved, setSaved] = useState(false);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [field]: value }));
    setSaved(false);
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Configuración</h1>

      <div className="space-y-6">
        <Card className="p-6">
          <h2 className="font-semibold mb-4">Datos de la farmacia</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
              <input
                type="text"
                value={form.pharmacyName}
                onChange={update('pharmacyName')}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="Farmacia XYZ"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
              <input
                type="tel"
                value={form.phone}
                onChange={update('phone')}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="+56 9 1234 5678"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
              <input
                type="text"
                value={form.address}
                onChange={update('address')}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="Av. Providencia 1234"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
              <input
                type="text"
                value={form.city}
                onChange={update('city')}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="Santiago"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email de contacto</label>
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                className="w-full px-3 py-2 border rounded-lg text-sm"
                placeholder="contacto@farmacia.cl"
              />
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-semibold mb-4">Opciones de entrega</h2>
          <div className="space-y-3">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.hasPickup}
                onChange={update('hasPickup')}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm">Retiro en tienda</span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.hasDelivery}
                onChange={update('hasDelivery')}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className="text-sm">Despacho a domicilio</span>
            </label>
          </div>
        </Card>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            className="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
          >
            Guardar cambios
          </button>
          {saved && <span className="text-sm text-green-600">Cambios guardados</span>}
        </div>
      </div>
    </div>
  );
}
