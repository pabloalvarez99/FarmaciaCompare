'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api-client';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { formatCLP } from '@/lib/utils';

interface PriceAlert {
  id: string;
  targetPrice: number;
  isActive: boolean;
  lastTriggered: string | null;
  createdAt: string;
  medication: {
    id: string;
    name: string;
    dosage: string;
    pharmaceuticalForm: string;
  };
}

interface MedicationResult {
  id: string;
  name: string;
  dosage: string;
  pharmaceuticalForm: string;
}

export default function AlertasPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MedicationResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedMed, setSelectedMed] = useState<MedicationResult | null>(null);
  const [targetPrice, setTargetPrice] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchAlerts = useCallback(() => {
    apiClient
      .get('/users/price-alerts')
      .then((r) => setAlerts(Array.isArray(r.data) ? r.data : []))
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const token = localStorage.getItem('accessToken');
    if (!token) { router.push('/login'); return; }
    fetchAlerts();
  }, [router, fetchAlerts]);

  useEffect(() => {
    if (searchQuery.length < 3) { setSearchResults([]); return; }
    const timeout = setTimeout(async () => {
      setSearching(true);
      try {
        const { data } = await apiClient.get(
          `/medications/search?q=${encodeURIComponent(searchQuery)}`
        );
        setSearchResults(data.data || data);
      } catch {
        setSearchResults([]);
      }
      setSearching(false);
    }, 300);
    return () => clearTimeout(timeout);
  }, [searchQuery]);

  const handleCreate = async () => {
    if (!selectedMed) return;
    const price = parseInt(targetPrice, 10);
    if (!price || price <= 0) return;
    setCreating(true);
    try {
      await apiClient.post('/users/price-alerts', {
        medicationId: selectedMed.id,
        targetPrice: price,
      });
      fetchAlerts();
      setShowCreate(false);
      setSelectedMed(null);
      setTargetPrice('');
      setSearchQuery('');
    } catch { /* noop */ }
    setCreating(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('¿Eliminar esta alerta?')) return;
    try {
      await apiClient.delete(`/users/price-alerts/${id}`);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch { /* noop */ }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Alertas de Precio</h1>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Alertas de Precio</h1>
        <Button onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancelar' : '+ Nueva alerta'}
        </Button>
      </div>

      {showCreate && (
        <Card className="p-4 mb-6">
          {!selectedMed ? (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Buscar medicamento
              </label>
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ej: Paracetamol, Ibuprofeno..."
                autoFocus
              />
              {searching && (
                <p className="text-sm text-gray-400 mt-2">Buscando...</p>
              )}
              {searchResults.length > 0 && (
                <div className="mt-2 border rounded-lg divide-y max-h-60 overflow-auto">
                  {searchResults.map((med) => (
                    <button
                      key={med.id}
                      className="w-full text-left px-3 py-2 hover:bg-gray-50 transition-colors"
                      onClick={() => setSelectedMed(med)}
                    >
                      <p className="text-sm font-medium text-gray-900">{med.name}</p>
                      <p className="text-xs text-gray-500">
                        {med.dosage} · {med.pharmaceuticalForm}
                      </p>
                    </button>
                  ))}
                </div>
              )}
              {searchQuery.length >= 3 && !searching && searchResults.length === 0 && (
                <p className="text-sm text-gray-400 mt-2">Sin resultados</p>
              )}
            </div>
          ) : (
            <div>
              <div className="bg-blue-50 rounded-lg p-3 mb-4">
                <p className="font-medium text-gray-900">{selectedMed.name}</p>
                <p className="text-sm text-gray-500">
                  {selectedMed.dosage} · {selectedMed.pharmaceuticalForm}
                </p>
                <button
                  className="text-sm text-blue-600 mt-1 hover:underline"
                  onClick={() => setSelectedMed(null)}
                >
                  Cambiar medicamento
                </button>
              </div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Precio objetivo (CLP)
              </label>
              <Input
                type="number"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                placeholder="Ej: 5000"
                autoFocus
              />
              <p className="text-xs text-gray-400 mt-1">
                Te notificaremos cuando el precio baje a{' '}
                {targetPrice ? formatCLP(parseInt(targetPrice, 10) || 0) : '$0'} o menos
              </p>
              <Button className="mt-4" onClick={handleCreate} disabled={creating}>
                {creating ? 'Creando...' : 'Crear alerta'}
              </Button>
            </div>
          )}
        </Card>
      )}

      {alerts.length === 0 ? (
        <Card className="p-8 text-center">
          <p className="text-gray-500 mb-2">No tienes alertas de precio</p>
          <p className="text-sm text-gray-400">
            Crea una alerta para recibir notificaciones cuando baje el precio de un medicamento
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <Card key={alert.id} className="p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900">{alert.medication.name}</p>
                  <p className="text-sm text-gray-500">
                    {alert.medication.dosage} · {alert.medication.pharmaceuticalForm}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-lg font-bold text-blue-600">
                    {formatCLP(alert.targetPrice)}
                  </p>
                  <Badge variant={alert.isActive ? 'default' : 'secondary'}>
                    {alert.isActive ? 'Activa' : 'Pausada'}
                  </Badge>
                </div>
              </div>
              <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                <p className="text-xs text-gray-400">
                  Creada el{' '}
                  {new Date(alert.createdAt).toLocaleDateString('es-CL')}
                  {alert.lastTriggered &&
                    ` · Última notificación: ${new Date(alert.lastTriggered).toLocaleDateString('es-CL')}`}
                </p>
                <button
                  className="text-sm text-red-500 hover:text-red-700"
                  onClick={() => handleDelete(alert.id)}
                >
                  Eliminar
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
