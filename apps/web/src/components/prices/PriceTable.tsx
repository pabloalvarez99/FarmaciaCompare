'use client';

import { useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatCLP } from '@/lib/utils';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api-client';
import { preferredCoquimboCity } from '@/lib/regions';
import { ShoppingCart, MapPin } from 'lucide-react';

interface PriceRow {
  pharmacyId: string;
  pharmacyName: string;
  pharmacyChain: string | null;
  pharmacyCity: string | null;
  pharmacyRegion: string | null;
  pharmacyProductId: string;
  price: number;
  originalPrice: number | null;
  discountPct: number | null;
  stockStatus: string;
  recordedAt: Date | null;
}

const CHAIN_COLORS: Record<string, string> = {
  cruz_verde: 'bg-green-100 text-green-800',
  salcobrand: 'bg-blue-100 text-blue-800',
  ahumada: 'bg-orange-100 text-orange-800',
  dr_simi: 'bg-yellow-100 text-yellow-800',
};

export function PriceTable({ prices, medicationName }: { prices: PriceRow[]; medicationName?: string }) {
  const sorted = [...prices].sort((a, b) => a.price - b.price);

  const cities = Array.from(
    new Set(prices.map((p) => p.pharmacyCity).filter(Boolean) as string[]),
  ).sort();

  // Prefer La Serena → Coquimbo → Ovalle when present in the row set; else all cities.
  const [selectedCity, setSelectedCity] = useState<string>(() => preferredCoquimboCity(cities));
  const [selected, setSelected] = useState<PriceRow | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [orderState, setOrderState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');

  const filtered = selectedCity ? sorted.filter((p) => p.pharmacyCity === selectedCity) : sorted;
  const lowestFiltered = filtered[0]?.price;

  const handleBuy = (row: PriceRow) => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      window.location.href = '/login';
      return;
    }
    setSelected(row);
    setQuantity(1);
    setOrderState('idle');
  };

  const handleConfirm = async () => {
    if (!selected) return;
    setOrderState('loading');
    try {
      await apiClient.post('/orders', {
        pharmacyId: selected.pharmacyId,
        items: [
          {
            pharmacyProductId: selected.pharmacyProductId,
            quantity,
            unitPrice: selected.price,
          },
        ],
      });
      setOrderState('success');
    } catch {
      setOrderState('error');
    }
  };

  return (
    <>
      {cities.length > 0 && (
        <div className="flex items-center gap-2 mb-3">
          <MapPin className="h-4 w-4 text-gray-400 shrink-0" />
          <select
            value={selectedCity}
            onChange={(e) => setSelectedCity(e.target.value)}
            className="text-sm border rounded-md px-2 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todas las ciudades ({sorted.length})</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                {city} ({sorted.filter((p) => p.pharmacyCity === city).length})
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 text-sm text-gray-500">
            <tr>
              <th className="text-left px-4 py-3">Farmacia</th>
              <th className="text-right px-4 py-3">Precio</th>
              <th className="text-right px-4 py-3 hidden sm:table-cell">Antes</th>
              <th className="text-center px-4 py-3 hidden md:table-cell">Stock</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {filtered.map((row, i) => (
              <tr key={row.pharmacyId} className={i === 0 ? 'bg-green-50' : 'hover:bg-gray-50'}>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {i === 0 && (
                      <Badge className="bg-green-600 text-white text-xs">Mejor precio</Badge>
                    )}
                    <div>
                      <p className="font-medium text-sm">{row.pharmacyName}</p>
                      <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                        {row.pharmacyChain && (
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${CHAIN_COLORS[row.pharmacyChain] ?? 'bg-gray-100 text-gray-600'}`}
                          >
                            {row.pharmacyChain.replace('_', ' ')}
                          </span>
                        )}
                        {row.pharmacyCity && (
                          <span className="text-xs text-gray-400 flex items-center gap-0.5">
                            <MapPin className="h-2.5 w-2.5" />
                            {row.pharmacyCity}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <span
                    className={`font-bold text-lg ${row.price === lowestFiltered ? 'text-green-600' : 'text-gray-900'}`}
                  >
                    {formatCLP(row.price)}
                  </span>
                  {row.discountPct && row.discountPct > 0 && (
                    <Badge variant="destructive" className="ml-1 text-xs">
                      -{row.discountPct}%
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-3 text-right hidden sm:table-cell">
                  {row.originalPrice && row.originalPrice > row.price ? (
                    <span className="text-sm text-muted-foreground line-through">
                      {formatCLP(row.originalPrice)}
                    </span>
                  ) : (
                    '\u2014'
                  )}
                </td>
                <td className="px-4 py-3 text-center hidden md:table-cell">
                  {row.stockStatus === 'in_stock' && (
                    <Badge variant="outline" className="text-green-600 border-green-200">
                      Disponible
                    </Badge>
                  )}
                  {row.stockStatus === 'low_stock' && (
                    <Badge variant="outline" className="text-yellow-600 border-yellow-200">
                      Pocas
                    </Badge>
                  )}
                  {row.stockStatus === 'out_of_stock' && (
                    <Badge variant="outline" className="text-red-600 border-red-200">
                      Agotado
                    </Badge>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1"
                    onClick={() => handleBuy(row)}
                    disabled={row.stockStatus === 'out_of_stock'}
                  >
                    <ShoppingCart className="h-3 w-3" />
                    Comprar
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmar pedido</DialogTitle>
            <DialogDescription>
              {medicationName || 'Medicamento'} en{' '}
              {selected?.pharmacyChain?.replace('_', ' ') || selected?.pharmacyName}
            </DialogDescription>
          </DialogHeader>

          {orderState === 'success' ? (
            <div className="py-4 text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <span className="text-green-600 text-xl">✓</span>
              </div>
              <p className="font-medium text-gray-900">Pedido creado</p>
              <p className="text-sm text-gray-500 mt-1">
                Puedes ver el estado en{' '}
                <a href="/pedidos" className="text-blue-600 hover:underline">
                  Mis pedidos
                </a>
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-4 py-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-gray-600">Precio unitario</span>
                  <span className="font-bold text-lg">{formatCLP(selected?.price || 0)}</span>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cantidad
                  </label>
                  <Input
                    type="number"
                    min={1}
                    max={20}
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  />
                </div>
                <div className="flex justify-between items-center pt-2 border-t">
                  <span className="font-medium text-gray-900">Total</span>
                  <span className="text-xl font-bold text-blue-600">
                    {formatCLP((selected?.price || 0) * quantity)}
                  </span>
                </div>
              </div>

              {orderState === 'error' && (
                <p className="text-sm text-red-500">
                  Error al crear el pedido. Inténtalo de nuevo.
                </p>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setSelected(null)}>
                  Cancelar
                </Button>
                <Button onClick={handleConfirm} disabled={orderState === 'loading'}>
                  {orderState === 'loading' ? 'Creando...' : 'Confirmar pedido'}
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
