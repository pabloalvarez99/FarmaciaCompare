import Link from 'next/link';
import { SearchBar } from '@/components/search/SearchBar';
import { MEDICATIONS } from '@/lib/demo-data';
import { formatCLP } from '@/lib/utils';

const POPULAR_SEARCHES = [
  'Paracetamol', 'Ibuprofeno', 'Losartán', 'Omeprazol',
  'Metformina', 'Amoxicilina', 'Atorvastatina', 'Clonazepam',
];

const PHARMACY_CHAINS = [
  { name: 'Cruz Verde', color: 'bg-green-100 text-green-800' },
  { name: 'Salcobrand', color: 'bg-blue-100 text-blue-800' },
  { name: 'Ahumada', color: 'bg-orange-100 text-orange-800' },
  { name: 'Dr. Simi', color: 'bg-yellow-100 text-yellow-800' },
  { name: 'Knop', color: 'bg-purple-100 text-purple-800' },
  { name: 'Independientes', color: 'bg-gray-100 text-gray-700' },
];

const FEATURES = [
  {
    title: 'Precios en tiempo real',
    description: 'Comparamos precios en las principales cadenas de farmacias de Chile.',
    icon: '🔄',
  },
  {
    title: 'Alertas de precio',
    description: 'Recibe notificaciones cuando el precio de tu medicamento baje.',
    icon: '🔔',
  },
  {
    title: 'Región de Coquimbo',
    description: 'La Serena, Coquimbo, Ovalle, Illapel, Vicuña y más ciudades.',
    icon: '📍',
  },
  {
    title: 'Gratis y sin registro',
    description: 'Compara precios sin cuenta. Regístrate solo para alertas y pedidos.',
    icon: '✨',
  },
];

// Pick 6 featured medications for the homepage
const FEATURED = MEDICATIONS.slice(0, 6);

export default function HomePage() {
  return (
    <main>
      {/* Hero */}
      <section className="bg-gradient-to-b from-blue-50 via-white to-white">
        <div className="max-w-3xl mx-auto px-4 py-20 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 mb-4 tracking-tight">
            Compara precios de{' '}
            <span className="text-blue-600">medicamentos</span>
          </h1>
          <p className="text-lg sm:text-xl text-gray-600 mb-8">
            Encuentra el mejor precio en farmacias de Chile — Santiago, La Serena, Coquimbo y más
          </p>
          <SearchBar size="lg" />
          <p className="text-sm text-gray-400 mt-4">
            {MEDICATIONS.length} medicamentos · {16} farmacias · Región Coquimbo incluida
          </p>
        </div>
      </section>

      {/* Featured medications with real prices */}
      <section className="max-w-5xl mx-auto px-4 py-12">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Medicamentos destacados</h2>
          <Link href="/buscar" className="text-sm text-blue-600 hover:underline">Ver todos →</Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURED.map((med) => {
            const lowest = med.prices[0];
            const highest = med.prices[med.prices.length - 1];
            const saving = highest && lowest ? highest.price - lowest.price : 0;
            return (
              <Link key={med.id} href={`/medicamentos/${med.id}`}>
                <div className="border rounded-xl p-4 bg-white hover:border-blue-300 hover:shadow-sm transition-all h-full">
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 text-sm leading-tight truncate">{med.name}</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">{med.activeIngredient.name} · {med.dosage}</p>
                    </div>
                    {med.prescriptionRequired && (
                      <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded ml-2 shrink-0">Receta</span>
                    )}
                  </div>
                  {lowest && (
                    <div className="mt-3 flex items-end justify-between">
                      <div>
                        <p className="text-xs text-gray-400">Desde</p>
                        <p className="text-xl font-bold text-blue-600">{formatCLP(lowest.price)}</p>
                        <p className="text-xs text-gray-400 mt-0.5">{lowest.pharmacyName}</p>
                      </div>
                      {saving > 0 && (
                        <div className="text-right">
                          <p className="text-xs text-gray-400">Ahorro</p>
                          <p className="text-sm font-semibold text-green-600">−{formatCLP(saving)}</p>
                          <p className="text-xs text-gray-400">{med.prices.length} farmacias</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </section>

      {/* Popular searches */}
      <section className="max-w-5xl mx-auto px-4 py-8">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Búsquedas populares
        </h2>
        <div className="flex flex-wrap gap-2">
          {POPULAR_SEARCHES.map((term) => (
            <Link
              key={term}
              href={`/buscar?q=${encodeURIComponent(term)}`}
              className="px-4 py-2 bg-gray-100 hover:bg-blue-50 hover:text-blue-700 rounded-full text-sm text-gray-700 transition-colors"
            >
              {term}
            </Link>
          ))}
        </div>
      </section>

      {/* Chains */}
      <section className="max-w-5xl mx-auto px-4 py-8">
        <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">
          Farmacias comparadas
        </h2>
        <div className="flex flex-wrap gap-2">
          {PHARMACY_CHAINS.map((chain) => (
            <span key={chain.name} className={`px-4 py-2 rounded-full text-sm font-medium ${chain.color}`}>
              {chain.name}
            </span>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">
            ¿Por qué usar FarmaciaCompare?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {FEATURES.map((feature) => (
              <div key={feature.title} className="bg-white rounded-xl p-6 border border-gray-200">
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="font-semibold text-gray-900 mt-3 mb-2">{feature.title}</h3>
                <p className="text-sm text-gray-500 leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-4 py-16 text-center">
        <h2 className="text-2xl font-bold text-gray-900 mb-3">Ahorra en tus medicamentos</h2>
        <p className="text-gray-500 mb-6">
          Crea una cuenta gratuita para guardar alertas de precio y hacer pedidos directamente
        </p>
        <div className="flex gap-3 justify-center flex-wrap">
          <Link href="/registro"
            className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors">
            Crear cuenta gratis
          </Link>
          <Link href="/buscar"
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors">
            Explorar medicamentos
          </Link>
        </div>
      </section>
    </main>
  );
}
