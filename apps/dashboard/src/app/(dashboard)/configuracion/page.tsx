'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { dashboardApi } from '@/lib/api-client';

interface PharmacySettings {
  id: string;
  name: string;
  address: string | null;
  city: string | null;
  region: string | null;
  phone: string | null;
  email: string | null;
  hasDelivery: boolean;
  hasPickup: boolean;
}

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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    dashboardApi
      .get('/dashboard/settings')
      .then((r) => {
        const s: PharmacySettings = r.data;
        setForm({
          pharmacyName: s.name || '',
          address: s.address || '',
          city: s.city || '',
          phone: s.phone || '',
          email: s.email || '',
          hasDelivery: s.hasDelivery,
          hasPickup: s.hasPickup,
        });
      })
      .catch(() => setError('No se pudo cargar la configuración'))
      .finally(() => setLoading(false));
  }, []);

  const update = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [field]: value }));
    setSaved(false);
    setError('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await dashboardApi.put('/dashboard/settings', {
        name: form.pharmacyName,
        address: form.address || undefined,
        city: form.city || undefined,
        phone: form.phone || undefined,
        email: form.email || undefined,
        hasDelivery: form.hasDelivery,
        hasPickup: form.hasPickup,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Error al guardar los cambios');
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div>
        <h1 className="text-2xl font-bold mb-6">Configuración</h1>
        <div className="space-y-4">
          {[1, 2].map((i) => (
            <div key={i} className="h-32 bg-gray-100 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Configuración</h1>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg">
          {error}
        </div>
      )}

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
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Farmacia XYZ"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Teléfono</label>
              <input
                type="tel"
                value={form.phone}
                onChange={update('phone')}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="+56 9 1234 5678"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Dirección</label>
              <input
                type="text"
                value={form.address}
                onChange={update('address')}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Av. Providencia 1234"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
              <input
                type="text"
                value={form.city}
                onChange={update('city')}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="Santiago"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Email de contacto</label>
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
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
              <div>
                <span className="text-sm font-medium">Retiro en tienda</span>
                <p className="text-xs text-gray-400">Los clientes pueden retirar en la farmacia</p>
              </div>
            </label>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={form.hasDelivery}
                onChange={update('hasDelivery')}
                className="w-4 h-4 rounded border-gray-300"
              />
              <div>
                <span className="text-sm font-medium">Despacho a domicilio</span>
                <p className="text-xs text-gray-400">Los pedidos se envían al domicilio del cliente</p>
              </div>
            </label>
          </div>
        </Card>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </button>
          {saved && <span className="text-sm text-green-600 font-medium">✓ Cambios guardados</span>}
        </div>
      </div>
    </div>
  );
}
