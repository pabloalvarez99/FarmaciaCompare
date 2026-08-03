/**
 * Regions and communes present in the physical-pharmacy directory.
 *
 * Every string in `value` and in `cities` is copied verbatim from
 * `GET /api/v1/products/pharmacies` (2.198 locales físicos, snapshot 2026-08-02),
 * not from memory: the API matches these values against the column as stored,
 * case-insensitively but accent-sensitively, so `Valparaiso` and `Valparaíso`
 * are different queries and only the stored spelling returns rows.
 *
 * The directory used to be Coquimbo-only, which is why the rest of the app still
 * carries some Coquimbo-first copy. The data no longer is.
 */

export interface Region {
  /** Exact `region` value stored in the DB — send this to the API. */
  value: string;
  /** Full es-CL name, grammatical after "en la …". */
  label: string;
  /** Communes with at least one local, most locales first. */
  cities: readonly string[];
}

/**
 * Ordered by number of locales in the directory.
 *
 * City lists are the distinct `city` values the API returns for that region,
 * minus rows whose city is not a place in it: region or province names
 * (`Araucanía`, `Cautín`, `Marga Marga`), address or store fragments (`Calle`,
 * `Local1`, `Urgencia`, `Líder`), and communes of a different region
 * (`Iquique` and `Chillan` tagged Biobío, `Lota` tagged Metropolitana). Those
 * locales are not hidden — they still appear in the listing under their own
 * heading; they just do not get a filter chip, because the chip would promise a
 * place the visitor cannot find on a map.
 *
 * Spellings without accents (`Pucon`, `Tome`, `Penaflor`) are kept exactly as
 * stored so the query matches; `cityLabel()` is what fixes them on screen.
 */
export const REGIONS: readonly Region[] = [
  {
    value: 'Metropolitana',
    label: 'Región Metropolitana',
    cities: [
      'Santiago', 'Puente Alto', 'Providencia', 'Ñuñoa', 'Las Condes', 'Vitacura',
      'Recoleta', 'San Miguel', 'Buin', 'Macul', 'Melipilla', 'La Pintana',
      'Conchalí', 'Quilicura', 'San Bernardo', 'La Florida', 'Lo Prado',
      'Peñalolén', 'Penaflor', 'Renca', 'Quinta Normal', 'Estación Central',
      'Independencia', 'Pudahuel', 'Colina', 'El Bosque', 'San Joaquín',
      'Huechuraba', 'La Granja', 'Pedro Aguirre Cerda', 'Cerrillos', 'La Cisterna',
      'La Reina', 'Lo Barnechea', 'Bollenar', 'Chicureo', 'Linderos', 'Maipú',
      'Talagante',
    ],
  },
  {
    value: 'Valparaíso',
    label: 'Región de Valparaíso',
    cities: [
      'Quilpué', 'Villa Alemana', 'Los Andes', 'Quillota', 'San Felipe',
      'Valparaíso', 'Concón', 'La Calera', 'Limache', 'La Ligua', 'San Antonio',
      'El Quisco', 'Viña del Mar', 'Casablanca', 'Quintero', 'Algarrobo',
      'Cartagena', 'Olmué', 'Isla Negra', 'San Esteban', 'Calle Larga', 'La Cruz',
      'Santo Domingo',
    ],
  },
  {
    value: 'Biobío',
    label: 'Región del Biobío',
    cities: [
      'Concepción', 'Los Angeles', 'Talcahuano', 'San Pedro de la Paz', 'Coronel',
      'Hualpén', 'Cañete', 'Chiguayante', 'Tome', 'Arauco', 'Lota', 'Curanilahue',
      'Penco', 'Nacimiento', 'Lebu', 'Mulchen', 'Hualqui', 'Yumbel', 'Lirquen',
    ],
  },
  {
    value: 'Maule',
    label: 'Región del Maule',
    cities: [
      'Curicó', 'Talca', 'Linares', 'Cauquenes', 'San Javier de Loncomilla',
      'Parral', 'Molina', 'Constitución', 'Longaví', 'Maule', 'San Clemente',
      'Teno', 'Villa Alegre', 'Colbun', 'Estación Villa Alegre', 'Retiro',
      'Río Claro', 'Sagrada Familia', 'Hualane', 'Porvenir', 'Rincónada',
    ],
  },
  {
    value: 'Araucanía',
    label: 'Región de La Araucanía',
    cities: [
      'Temuco', 'Villarrica', 'Angol', 'Pucon', 'Victoria', 'Lautaro',
      'Nueva Imperial', 'Loncoche', 'Carahue', 'Padre las Casas', 'Collipulli',
      'Curacautin', 'Pitrufquén', 'Gorbea', 'Traiguen', 'Freire', 'Licán Ray',
      'Lonquimay',
    ],
  },
  {
    value: 'Coquimbo',
    label: 'Región de Coquimbo',
    cities: [
      'La Serena', 'Ovalle', 'Coquimbo', 'Illapel', 'Los Vilos', 'Salamanca',
      'Vicuña', 'Monte Patria', 'Andacollo', 'Pichidangui',
    ],
  },
  // A single local, imported with the Biobío batch before Ñuble was split out of
  // it. Listed anyway: one pharmacy that exists beats a region that silently
  // does not.
  {
    value: 'Ñuble',
    label: 'Región de Ñuble',
    cities: ['Chillán'],
  },
];

/**
 * Where the directory opens when the URL says nothing.
 *
 * Coquimbo was hardcoded while it was the only region imported. It no longer is,
 * so the default is the region with the most locales (775 of 2.198) and the most
 * people. It is a starting point, not a scope: every region is one chip — and one
 * shareable `?region=` URL — away.
 */
export const DEFAULT_REGION: Region = REGIONS[0];

/** Lowercase, accent-free, single-spaced — for comparing user input to stored values. */
export function normalizeName(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, ' ');
}

/**
 * Resolve a `?region=` param. Accepts the stored value or the full label, in any
 * case and with or without accents, so a hand-typed `?region=valparaiso` still
 * lands on the right page. `null` when it matches nothing.
 */
export function findRegion(param: string | undefined | null): Region | null {
  if (!param) return null;
  const key = normalizeName(param);
  if (!key) return null;
  return (
    REGIONS.find(
      (r) => normalizeName(r.value) === key || normalizeName(r.label) === key,
    ) ?? null
  );
}

/**
 * Display spellings for communes stored without their accents. The key is the
 * normalized form, so it fixes every variant at once; the query still travels
 * with whatever the DB holds.
 */
const CITY_LABELS: Record<string, string> = {
  pucon: 'Pucón',
  tome: 'Tomé',
  'los angeles': 'Los Ángeles',
  mulchen: 'Mulchén',
  curacautin: 'Curacautín',
  traiguen: 'Traiguén',
  penaflor: 'Peñaflor',
  colbun: 'Colbún',
  hualane: 'Hualañé',
  lirquen: 'Lirquén',
  rinconada: 'Rinconada',
  chillan: 'Chillán',
  nunoa: 'Ñuñoa',
  valparaiso: 'Valparaíso',
  concepcion: 'Concepción',
  'estacion central': 'Estación Central',
};

/** Human spelling for a stored city value. Unknown values pass through unchanged. */
export function cityLabel(city: string): string {
  return CITY_LABELS[normalizeName(city)] ?? city;
}

/**
 * Kept for the home page and the price table, which still frame the product
 * around Coquimbo. Not used by the directory any more.
 */
export const REGION_LABEL = 'Región de Coquimbo';

/** Communes of Región de Coquimbo, most locales first. */
export const COQUIMBO_CITIES: readonly string[] =
  REGIONS.find((r) => r.value === 'Coquimbo')!.cities;

/** First Coquimbo commune present in `available` — a default for city selectors. */
export function preferredCoquimboCity(available: readonly string[]): string {
  const set = new Set(available.map(normalizeName));
  for (const city of COQUIMBO_CITIES) {
    if (set.has(normalizeName(city))) return city;
  }
  return '';
}
