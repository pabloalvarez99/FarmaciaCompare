import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatCLP } from '@/lib/utils';
import { ShoppingCart } from 'lucide-react';

interface PriceRow {
  pharmacyId: string; pharmacyName: string; pharmacyChain: string | null;
  price: number; originalPrice: number | null; discountPct: number | null;
  stockStatus: string; recordedAt: Date | null;
}

const CHAIN_COLORS: Record<string, string> = {
  cruz_verde: 'bg-green-100 text-green-800', salcobrand: 'bg-blue-100 text-blue-800',
  ahumada: 'bg-orange-100 text-orange-800', dr_simi: 'bg-yellow-100 text-yellow-800',
};

export function PriceTable({ prices }: { prices: PriceRow[] }) {
  const sorted = [...prices].sort((a, b) => a.price - b.price);
  const lowestPrice = sorted[0]?.price;
  return (
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
          {sorted.map((row, i) => (
            <tr key={row.pharmacyId} className={i === 0 ? 'bg-green-50' : 'hover:bg-gray-50'}>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {i === 0 && <Badge className="bg-green-600 text-white text-xs">Mejor precio</Badge>}
                  <div>
                    <p className="font-medium text-sm">{row.pharmacyName}</p>
                    {row.pharmacyChain && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${CHAIN_COLORS[row.pharmacyChain] ?? 'bg-gray-100 text-gray-600'}`}>
                        {row.pharmacyChain.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <span className={`font-bold text-lg ${row.price === lowestPrice ? 'text-green-600' : 'text-gray-900'}`}>{formatCLP(row.price)}</span>
                {row.discountPct && row.discountPct > 0 && <Badge variant="destructive" className="ml-1 text-xs">-{row.discountPct}%</Badge>}
              </td>
              <td className="px-4 py-3 text-right hidden sm:table-cell">
                {row.originalPrice && row.originalPrice > row.price ? (
                  <span className="text-sm text-muted-foreground line-through">{formatCLP(row.originalPrice)}</span>
                ) : '\u2014'}
              </td>
              <td className="px-4 py-3 text-center hidden md:table-cell">
                {row.stockStatus === 'in_stock' && <Badge variant="outline" className="text-green-600 border-green-200">Disponible</Badge>}
                {row.stockStatus === 'low_stock' && <Badge variant="outline" className="text-yellow-600 border-yellow-200">Pocas</Badge>}
                {row.stockStatus === 'out_of_stock' && <Badge variant="outline" className="text-red-600 border-red-200">Agotado</Badge>}
              </td>
              <td className="px-4 py-3 text-right">
                <Button size="sm" variant="outline" className="gap-1"><ShoppingCart className="h-3 w-3" />Comprar</Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
