import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';

const POPULAR_SEARCHES = [
  'Paracetamol',
  'Ibuprofeno',
  'Losartán',
  'Omeprazol',
  'Metformina',
  'Amoxicilina',
  'Atorvastatina',
  'Clonazepam',
];

const PHARMACY_CHAINS = [
  { name: 'Cruz Verde', color: 'bg-green-100 text-green-800' },
  { name: 'Salcobrand', color: 'bg-blue-100 text-blue-800' },
  { name: 'Ahumada', color: 'bg-orange-100 text-orange-800' },
  { name: 'Dr. Simi', color: 'bg-yellow-100 text-yellow-800' },
  { name: 'Knop', color: 'bg-purple-100 text-purple-800' },
  { name: 'Mapuche', color: 'bg-red-100 text-red-800' },
];

const FEATURES = [
  {
    title: 'Precios actualizados',
    description: 'Comparamos precios cada 4 horas en las principales cadenas de farmacias de Chile.',
    icon: '🔄',
  },
  {
    title: 'Alertas de precio',
    description: 'Recibe una notificación cuando el precio de tu medicamento baje al valor que deseas.',
    icon: '🔔',
  },
  {
    title: 'Todas las farmacias',
    description: 'Cruz Verde, Salcobrand, Ahumada, Dr. Simi, Knop y farmacias independientes.',
    icon: '🏥',
  },
  {
    title: 'Gratis y sin registro',
    description: 'Compara precios sin necesidad de crear una cuenta. Regístrate solo para alertas y pedidos.',
    icon: '✨',
  },
];

export default function HomePage() {
  return (
    <main>
      <section className="bg-gradient-to-b from-blue-50 via-white to-white">
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4 tracking-tight">
            Compara precios de{' '}
            <span className="text-blue-600">medicamentos</span>
          </h1>
          <p className="text-lg sm:text-xl text-gray-600 mb-8">
            Encuentra el mejor precio en farmacias de todo Chile
          </p>
          <SearchBar size="lg" />
          <p className="text-sm text-gray-400 mt-4">
            Más de 10,000 medicamentos. Actualizado cada 4 horas.
          </p>
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 py-12">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Búsquedas populares
        </h2>
        <div className="flex flex-wrap gap-2">
          {POPULAR_SEARCHES.map((term) => (
            <Link
              key={term}
              href={`/buscar?q=${encodeURIComponent(term)}`}
              className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-full text-sm text-gray-700 transition-colors"
            >
              {term}
            </Link>
          ))}
        </div>
      </section>

      <section className="max-w-5xl mx-auto px-4 py-12">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Farmacias comparadas
        </h2>
        <div className="flex flex-wrap gap-2">
          {PHARMACY_CHAINS.map((chain) => (
            <span
              key={chain.name}
              className={`px-4 py-2 rounded-full text-sm font-medium ${chain.color}`}
            >
              {chain.name}
            </span>
          ))}
        </div>
      </section>

      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">
            ¿Por qué usar FarmaciaCompare?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="bg-white rounded-xl p-6 border border-gray-200"
              >
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="font-semibold text-gray-900 mt-3 mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-gray-500 leading-relaxed">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-4 py-16 text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-3">
          Ahorra en tus medicamentos
        </h2>
        <p className="text-gray-500 mb-6">
          Crea una cuenta gratuita para guardar alertas de precio y hacer pedidos directamente
        </p>
        <div className="flex gap-3 justify-center">
          <Link
            href="/registro"
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
          >
            Crear cuenta gratis
          </Link>
          <Link
            href="/buscar?q="
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
          >
            Explorar medicamentos
          </Link>
        </div>
      </section>
    </main>
  );
}
