import { SearchBar } from '@/components/search/SearchBar';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="max-w-3xl mx-auto px-4 py-24 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          Compara precios de <span className="text-blue-600">medicamentos</span>
        </h1>
        <p className="text-xl text-gray-600 mb-10">Cruz Verde, Salcobrand, Ahumada, Dr. Simi y más</p>
        <SearchBar size="lg" />
        <p className="text-sm text-gray-400 mt-4">Más de 10,000 medicamentos. Actualizado cada 4 horas.</p>
      </div>
    </main>
  );
}
