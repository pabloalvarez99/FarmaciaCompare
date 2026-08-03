import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Alertas de precio — FarmaciaCompare',
  description:
    'Avísame cuando baje el precio de un medicamento en las farmacias online de Chile.',
};

/**
 * The previous screen rendered a mock list of alerts over the demo dataset, so
 * it showed invented prices as if they were market data. The alerts feature has
 * no backend yet — the UI is kept in git history and can come back once
 * `price_alerts` is wired to scraped prices.
 */
export default function AlertasPage() {
  return (
    <div className="max-w-2xl mx-auto px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-gray-900">Alertas de precio</h1>
      <p className="mt-3 text-gray-600">
        Todavía no están disponibles. Cuando lo estén, vas a poder elegir un
        producto y recibir un aviso cuando alguna farmacia lo baje.
      </p>
      <p className="mt-6 text-sm text-gray-500">
        Mientras tanto, los precios de hoy ya están comparados.
      </p>
      <Link
        href="/precios"
        className="mt-6 inline-block rounded bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700"
      >
        Ver precios
      </Link>
    </div>
  );
}
