import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 py-16 text-center">
      <div className="w-20 h-20 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-6">
        <span className="text-4xl">💊</span>
      </div>
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Página no encontrada</h1>
      <p className="text-gray-500 mb-8 max-w-sm">
        No encontramos lo que buscabas. Prueba buscar el medicamento directamente.
      </p>
      <div className="w-full max-w-md mb-6">
        <SearchBar />
      </div>
      <div className="flex gap-3">
        <Link
          href="/"
          className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          Inicio
        </Link>
        <Link
          href="/buscar"
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Ver todos los medicamentos
        </Link>
      </div>
    </div>
  );
}
