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
    <div className="mx-auto max-w-3xl px-4 py-10">
      <p className="label mb-2 text-muted-foreground">{REGION_LABEL}</p>
      <h1 className="display mb-3 text-3xl font-bold text-foreground">
        Farmacias en la {REGION_LABEL}
      </h1>
      {/* Says what this page is and, just as importantly, what it is not: the
          prices elsewhere on the site are from online stores and are not the
          stock of any one counter. */}
      <p className="mb-6 leading-relaxed text-muted-foreground">
        {physical.length > 0
          ? `${physical.length.toLocaleString('es-CL')} locales en La Serena, Coquimbo, Ovalle y alrededores, con dirección y teléfono. Los precios que comparamos en el resto del sitio son de tiendas online y no corresponden al stock de un local en particular.`
          : 'Estamos cargando el directorio de locales. Mientras tanto puedes comparar precios de las cadenas online, que despachan a todo Chile.'}
      </p>

      <section className="mb-8">
        <h2 className="display mb-3 text-lg font-semibold text-foreground">
          Filtrar por ciudad
        </h2>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/farmacias"
            aria-current={!cityFilter ? 'page' : undefined}
            className={`chip ${!cityFilter ? 'chip-on' : ''}`}
          >
            Todas ({physical.length || '…'})
          </Link>
          {COQUIMBO_CITIES.map((city) => {
            const n = byCity.get(city);
            const active = cityFilter === city;
            return (
              <Link
                key={city}
                href={`/farmacias?city=${encodeURIComponent(city)}`}
                aria-current={active ? 'page' : undefined}
                className={`chip ${active ? 'chip-on' : ''}`}
              >
                {city}
                {n != null ? ` (${n})` : ''}
              </Link>
            );
          })}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="display mb-3 text-lg font-semibold text-foreground">
          Locales{cityFilter ? ` · ${cityFilter}` : ''}
        </h2>
        {physical.length === 0 ? (
          <p className="panel border-dashed p-6 text-sm text-muted-foreground">
            No tenemos locales cargados para este filtro. Sólo listamos direcciones que
            podemos verificar, así que preferimos dejarlo vacío antes que completarlo.
          </p>
        ) : (
          <div className="panel overflow-hidden">
            {groupByCity(physical).map(([city, items]) => {
              const headingId = cityDomId(city);
              return (
              <section key={city} aria-labelledby={headingId}>
                <h3
                  id={headingId}
                  className="sticky top-0 z-10 border-b border-edge bg-muted/95 px-4 py-2 text-sm font-semibold text-foreground backdrop-blur-sm"
                >
                  {city}
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    ({items.length})
                  </span>
                </h3>
                <ul className="divide-y divide-edge">
                  {items.map((p) => {
                    const rating = ratingLabel(p.rating, p.ratingCount);
                    const mapHref = mapsUrl(p.lat, p.lng);
                    return (
                      <li key={p.id} className="px-4 py-3">
                        <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="font-medium text-foreground">{p.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {[p.address, p.city].filter(Boolean).join(' · ')}
                            </p>
                            {p.phone && (
                              <p className="mt-0.5 text-sm text-muted-foreground">
                                {p.phone}
                              </p>
                            )}
                          </div>
                          <div className="shrink-0 text-sm text-muted-foreground sm:text-right">
                            {p.chain && (
                              <span className="mb-1 inline-block rounded border border-edge bg-muted/60 px-2 py-0.5 text-xs text-foreground">
                                {p.chain.replace(/_/g, ' ')}
                              </span>
                            )}
                            {rating && <p>{rating}</p>}
                            <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 sm:justify-end">
                              {mapHref && (
                                <a
                                  href={mapHref}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="link"
                                >
                                  Cómo llegar ↗
                                </a>
                              )}
                              {p.website && (
                                <a
                                  href={p.website}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="link"
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
        <p className="mt-3 text-xs text-muted-foreground">
          Direcciones y horarios pueden cambiar. Llama al local antes de ir.
        </p>
      </section>

      <section className="panel mb-10 p-5">
        <h2 className="display mb-2 text-lg font-semibold text-foreground">
          Precios online, cobertura nacional
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Estas son las tiendas online cuyos precios comparamos. Despachan a domicilio en
          todo Chile; lo que muestran no es el stock de un local de la región.
        </p>
        {onlineChains.length === 0 ? (
          <p className="text-sm text-muted-foreground">Cargando cobertura de cadenas…</p>
        ) : (
          <ul className="mb-4 flex flex-wrap gap-2">
            {onlineChains.map((c) => (
              <li
                key={c.pharmacyId}
                className="rounded-full border border-edge bg-card px-3 py-1 text-sm text-foreground"
              >
                {c.name.replace(' (Online)', '')}{' '}
                <span className="figure text-muted-foreground">
                  {c.productCount.toLocaleString('es-CL')}
                </span>
              </li>
            ))}
          </ul>
        )}
        <Link href="/comparar" className="link text-sm">
          Ver diferencias de precio →
        </Link>
      </section>

      <p className="text-sm">
        <Link href="/" className="link">
          ← Volver al inicio
        </Link>
      </p>
    </div>
  );
}
