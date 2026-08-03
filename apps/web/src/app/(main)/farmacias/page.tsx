import Link from 'next/link';
import { COQUIMBO_CITIES, REGION_LABEL } from '@/lib/regions';
import {
  getCoverage,
  getPharmacies,
  type PharmacyDirectoryEntry,
} from '@/lib/api-products';

export const revalidate = 300;

export const metadata = {
  title: `Farmacias en la ${REGION_LABEL} | FarmaciaCompare`,
  description: `Directorio de farmacias físicas en la ${REGION_LABEL}: La Serena, Coquimbo, Ovalle y más. Precios online de cadenas que despachan a domicilio.`,
};

function ratingLabel(rating: string | number | null | undefined, count: number | null | undefined) {
  if (rating == null || rating === '') return null;
  const n = typeof rating === 'string' ? Number(rating) : rating;
  if (Number.isNaN(n)) return null;
  const c = count ?? 0;
  return c > 0 ? `${n.toFixed(1)} · ${c} reseñas` : n.toFixed(1);
}

/** Public Google Maps URL from coords — no API key required. */
function mapsUrl(lat: string | number | null, lng: string | number | null): string | null {
  if (lat == null || lng == null || lat === '' || lng === '') return null;
  const la = typeof lat === 'string' ? Number(lat) : lat;
  const ln = typeof lng === 'string' ? Number(lng) : lng;
  if (Number.isNaN(la) || Number.isNaN(ln)) return null;
  return `https://www.google.com/maps?q=${la},${ln}`;
}

function groupByCity(pharmacies: PharmacyDirectoryEntry[]): [string, PharmacyDirectoryEntry[]][] {
  const map = new Map<string, PharmacyDirectoryEntry[]>();
  for (const p of pharmacies) {
    const city = p.city || 'Sin ciudad';
    const list = map.get(city);
    if (list) list.push(p);
    else map.set(city, [p]);
  }
  for (const list of map.values()) {
    list.sort((a, b) => a.name.localeCompare(b.name, 'es'));
  }
  const preferred = COQUIMBO_CITIES.filter((c) => map.has(c));
  const known = new Set<string>(COQUIMBO_CITIES);
  const rest = [...map.keys()]
    .filter((c) => !known.has(c))
    .sort((a, b) => a.localeCompare(b, 'es'));
  return [...preferred, ...rest].map((city) => [city, map.get(city)!]);
}

function cityDomId(city: string): string {
  return `city-${city.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-').toLowerCase()}`;
}

/**
 * Physical-pharmacy directory for Región de Coquimbo (Google Places → Cloud SQL).
 * Online chain prices stay on /precios (national scrapers).
 */
export default async function FarmaciasPage({
  searchParams,
}: {
  searchParams?: Promise<{ city?: string }> | { city?: string };
}) {
  const sp = searchParams instanceof Promise ? await searchParams : searchParams;
  const cityFilter = (sp?.city || '').trim();

  const [coverage, pharmacies] = await Promise.all([
    getCoverage(),
    getPharmacies('Coquimbo', cityFilter),
  ]);
  const onlineChains = coverage.filter((c) => c.productCount > 0);
  const physical = pharmacies.filter((p) => p.type === 'physical');

  const byCity = new Map<string, number>();
  for (const p of physical) {
    const c = p.city || 'Sin ciudad';
    byCity.set(c, (byCity.get(c) || 0) + 1);
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <p className="text-sm font-medium text-blue-600 mb-2">{REGION_LABEL}</p>
      <h1 className="text-3xl font-bold text-gray-900 mb-3">
        Farmacias en la {REGION_LABEL}
      </h1>
      <p className="text-gray-600 mb-6 leading-relaxed">
        {physical.length > 0
          ? `${physical.length.toLocaleString('es-CL')} locales físicos indexados con Google Places
            (La Serena, Coquimbo, Ovalle y más). Los precios online de cadenas nacionales están en
            Comparar precios — no son el stock de un local específico.`
          : `Estamos cargando el directorio de locales físicos. Mientras tanto puedes comparar
            precios de cadenas online que despachan a domicilio en todo Chile.`}
      </p>

      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Filtrar por ciudad</h2>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/farmacias"
            className={`rounded-full border px-3 py-1 text-sm ${
              !cityFilter
                ? 'border-blue-600 bg-blue-600 text-white'
                : 'border-gray-200 bg-white text-gray-800 hover:border-blue-300'
            }`}
          >
            Todas ({physical.length || '…'})
          </Link>
          {COQUIMBO_CITIES.map((city) => {
            const n = byCity.get(city);
            if (cityFilter && city !== cityFilter && !n) {
              // still show main cities even if empty in this deploy
            }
            return (
              <Link
                key={city}
                href={`/farmacias?city=${encodeURIComponent(city)}`}
                className={`rounded-full border px-3 py-1 text-sm ${
                  cityFilter === city
                    ? 'border-blue-600 bg-blue-600 text-white'
                    : 'border-gray-200 bg-white text-gray-800 hover:border-blue-300'
                }`}
              >
                {city}
                {n != null ? ` (${n})` : ''}
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-900 mb-3">
          Locales físicos{cityFilter ? ` · ${cityFilter}` : ''}
        </h2>
        {physical.length === 0 ? (
          <p className="text-sm text-gray-500 rounded-lg border border-dashed border-gray-200 p-6">
            Aún no hay locales en la API para este filtro. El directorio se carga con Google Places
            (proyecto Maps) e import a Cloud SQL — sin direcciones inventadas.
          </p>
        ) : (
          <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
            {groupByCity(physical).map(([city, items]) => {
              const headingId = cityDomId(city);
              return (
              <section key={city} aria-labelledby={headingId}>
                <h3
                  id={headingId}
                  className="sticky top-0 z-10 border-b border-gray-200 bg-gray-50/95 px-4 py-2 text-sm font-semibold text-gray-800 backdrop-blur-sm"
                >
                  {city}
                  <span className="ml-1.5 font-normal text-gray-500">
                    ({items.length})
                  </span>
                </h3>
                <ul className="divide-y divide-gray-100">
                  {items.map((p) => {
                    const rating = ratingLabel(p.rating, p.ratingCount);
                    const mapHref = mapsUrl(p.lat, p.lng);
                    return (
                      <li key={p.id} className="px-4 py-3">
                        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1">
                          <div>
                            <p className="font-medium text-gray-900">{p.name}</p>
                            <p className="text-sm text-gray-600">
                              {[p.address, p.city].filter(Boolean).join(' · ')}
                            </p>
                            {p.phone && (
                              <p className="text-sm text-gray-500 mt-0.5">{p.phone}</p>
                            )}
                          </div>
                          <div className="text-sm text-gray-500 sm:text-right shrink-0">
                            {p.chain && (
                              <span className="inline-block rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700 mb-1">
                                {p.chain}
                              </span>
                            )}
                            {rating && <p>{rating}</p>}
                            <div className="flex flex-wrap gap-x-3 gap-y-0.5 sm:justify-end mt-0.5">
                              {mapHref && (
                                <a
                                  href={mapHref}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline"
                                >
                                  Google Maps ↗
                                </a>
                              )}
                              {p.website && (
                                <a
                                  href={p.website}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-600 hover:underline"
                                >
                                  Sitio web ↗
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
              );
            })}
          </div>
        )}
        <p className="mt-3 text-xs text-gray-400">
          Fuente: Google Places (tablero-iner-maps). Identidad estable por place_id. Re-import
          idempotente.
        </p>
      </section>

      <section className="mb-10 rounded-xl border border-blue-100 bg-blue-50/60 p-5">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">
          Precios online (cobertura nacional)
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Cadenas e-commerce scrapeadas en vivo. Despacho a domicilio; no es el stock de un local
          de Coquimbo.
        </p>
        {onlineChains.length === 0 ? (
          <p className="text-sm text-gray-500">Cargando cobertura de cadenas…</p>
        ) : (
          <ul className="flex flex-wrap gap-2 mb-4">
            {onlineChains.map((c) => (
              <li
                key={c.pharmacyId}
                className="rounded-full bg-white border border-blue-100 px-3 py-1 text-sm text-gray-800"
              >
                {c.name.replace(' (Online)', '')}{' '}
                <span className="text-gray-400">
                  {c.productCount.toLocaleString('es-CL')}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/precios"
          className="inline-flex text-sm font-medium text-blue-700 hover:underline"
        >
          Comparar precios online →
        </Link>
      </section>

      <p className="text-sm text-gray-500">
        <Link href="/" className="text-blue-600 hover:underline">
          ← Volver al inicio
        </Link>
      </p>
    </div>
  );
}
