// Static demo data — used when NEXT_PUBLIC_API_URL is not set (Vercel preview/prod)
// Derived from the seed script (scripts/seed.mjs)

export interface DemoMedication {
  id: string;
  name: string;
  activeIngredient: { name: string };
  dosage: string;
  pharmaceuticalForm: string;
  prescriptionRequired: boolean;
  ispRegistration: string | null;
  prices: DemoPrice[];
  names: { normalizedName: string }[];
}

export interface DemoPrice {
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

const PHARMACIES = [
  { id: 'ph-cv-las-condes', name: 'Cruz Verde Las Condes', chain: 'cruz_verde', city: 'Santiago', region: 'Metropolitana' },
  { id: 'ph-sb-vitacura', name: 'Salcobrand Vitacura', chain: 'salcobrand', city: 'Santiago', region: 'Metropolitana' },
  { id: 'ph-ah-nunoa', name: 'Farmacia Ahumada Ñuñoa', chain: 'ahumada', city: 'Santiago', region: 'Metropolitana' },
  { id: 'ph-ds-maipu', name: 'Dr. Simi Maipú', chain: 'dr_simi', city: 'Santiago', region: 'Metropolitana' },
  { id: 'ph-cv-ls-centro', name: 'Cruz Verde La Serena Centro', chain: 'cruz_verde', city: 'La Serena', region: 'Coquimbo' },
  { id: 'ph-sb-ls', name: 'Salcobrand La Serena', chain: 'salcobrand', city: 'La Serena', region: 'Coquimbo' },
  { id: 'ph-knop-ls', name: 'Knop La Serena', chain: 'knop', city: 'La Serena', region: 'Coquimbo' },
  { id: 'ph-ds-ls', name: 'Dr. Simi La Serena', chain: 'dr_simi', city: 'La Serena', region: 'Coquimbo' },
  { id: 'ph-pueblo-ls', name: 'Farmacia del Pueblo La Serena', chain: null, city: 'La Serena', region: 'Coquimbo' },
  { id: 'ph-cv-cq', name: 'Cruz Verde Coquimbo', chain: 'cruz_verde', city: 'Coquimbo', region: 'Coquimbo' },
  { id: 'ph-ds-cq', name: 'Dr. Simi Coquimbo', chain: 'dr_simi', city: 'Coquimbo', region: 'Coquimbo' },
  { id: 'ph-popular-cq', name: 'Farmacia Popular Coquimbo', chain: null, city: 'Coquimbo', region: 'Coquimbo' },
  { id: 'ph-cv-ov', name: 'Cruz Verde Ovalle', chain: 'cruz_verde', city: 'Ovalle', region: 'Coquimbo' },
  { id: 'ph-ds-ov', name: 'Dr. Simi Ovalle', chain: 'dr_simi', city: 'Ovalle', region: 'Coquimbo' },
  { id: 'ph-mercado-ov', name: 'Farmacia del Mercado Ovalle', chain: null, city: 'Ovalle', region: 'Coquimbo' },
  { id: 'ph-andacollo', name: 'Farmacia Andacollo', chain: null, city: 'Andacollo', region: 'Coquimbo' },
];

const CHAIN_MULT: Record<string, number> = {
  dr_simi: 0.82, knop: 0.90, cruz_verde: 1.05, salcobrand: 1.08, ahumada: 1.10,
};

function makePrices(medId: string, basePrice: number): DemoPrice[] {
  return PHARMACIES.map((ph, i) => {
    const mult = ph.chain ? (CHAIN_MULT[ph.chain] ?? 1.0) : 0.78;
    const price = Math.round(basePrice * mult / 10) * 10;
    const hasDiscount = ph.chain === 'dr_simi' || ph.chain === 'knop';
    return {
      pharmacyId: ph.id,
      pharmacyName: ph.name,
      pharmacyChain: ph.chain,
      pharmacyCity: ph.city,
      pharmacyRegion: ph.region,
      pharmacyProductId: `pp-${medId}-${ph.id}`,
      price,
      originalPrice: hasDiscount ? Math.round(price / mult * 1.05 / 10) * 10 : null,
      discountPct: hasDiscount ? 18 : null,
      stockStatus: i % 7 === 0 ? 'low_stock' : 'in_stock',
      recordedAt: new Date(),
    };
  }).sort((a, b) => a.price - b.price);
}

export const MEDICATIONS: DemoMedication[] = [
  {
    id: 'med-paracetamol-500',
    name: 'Tapsin Forte Comprimidos',
    activeIngredient: { name: 'Paracetamol' },
    dosage: '500mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-14235/22',
    names: [{ normalizedName: 'tapsin' }, { normalizedName: 'paracetamol' }],
    prices: makePrices('paracetamol-500', 2100),
  },
  {
    id: 'med-ibuprofeno-400',
    name: 'Ibuprofeno 400mg Comprimidos',
    activeIngredient: { name: 'Ibuprofeno' },
    dosage: '400mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-22341/21',
    names: [{ normalizedName: 'ibuprofeno' }, { normalizedName: 'ibupirac' }],
    prices: makePrices('ibuprofeno-400', 3200),
  },
  {
    id: 'med-amoxicilina-500',
    name: 'Amoxicilina 500mg Cápsulas',
    activeIngredient: { name: 'Amoxicilina' },
    dosage: '500mg',
    pharmaceuticalForm: 'Cápsulas',
    prescriptionRequired: true,
    ispRegistration: 'F-19823/20',
    names: [{ normalizedName: 'amoxicilina' }, { normalizedName: 'amoxil' }],
    prices: makePrices('amoxicilina-500', 5800),
  },
  {
    id: 'med-enalapril-10',
    name: 'Enalapril 10mg Comprimidos',
    activeIngredient: { name: 'Enalapril' },
    dosage: '10mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-11234/19',
    names: [{ normalizedName: 'enalapril' }, { normalizedName: 'renitec' }],
    prices: makePrices('enalapril-10', 4500),
  },
  {
    id: 'med-metformina-850',
    name: 'Metformina 850mg Comprimidos',
    activeIngredient: { name: 'Metformina' },
    dosage: '850mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-13456/21',
    names: [{ normalizedName: 'metformina' }, { normalizedName: 'glucophage' }],
    prices: makePrices('metformina-850', 6200),
  },
  {
    id: 'med-omeprazol-20',
    name: 'Omeprazol 20mg Cápsulas',
    activeIngredient: { name: 'Omeprazol' },
    dosage: '20mg',
    pharmaceuticalForm: 'Cápsulas',
    prescriptionRequired: false,
    ispRegistration: 'F-15678/20',
    names: [{ normalizedName: 'omeprazol' }, { normalizedName: 'prilosec' }],
    prices: makePrices('omeprazol-20', 4800),
  },
  {
    id: 'med-atorvastatina-20',
    name: 'Atorvastatina 20mg Comprimidos',
    activeIngredient: { name: 'Atorvastatina' },
    dosage: '20mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-17890/22',
    names: [{ normalizedName: 'atorvastatina' }, { normalizedName: 'lipitor' }],
    prices: makePrices('atorvastatina-20', 8900),
  },
  {
    id: 'med-levotiroxina-100',
    name: 'Levotiroxina 100mcg Comprimidos',
    activeIngredient: { name: 'Levotiroxina' },
    dosage: '100mcg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-20123/21',
    names: [{ normalizedName: 'levotiroxina' }, { normalizedName: 'eutirox' }],
    prices: makePrices('levotiroxina-100', 7200),
  },
  {
    id: 'med-loratadina-10',
    name: 'Loratadina 10mg Comprimidos',
    activeIngredient: { name: 'Loratadina' },
    dosage: '10mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-22456/22',
    names: [{ normalizedName: 'loratadina' }, { normalizedName: 'claritin' }],
    prices: makePrices('loratadina-10', 3500),
  },
  {
    id: 'med-sertralina-50',
    name: 'Sertralina 50mg Comprimidos',
    activeIngredient: { name: 'Sertralina' },
    dosage: '50mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-24789/20',
    names: [{ normalizedName: 'sertralina' }, { normalizedName: 'zoloft' }],
    prices: makePrices('sertralina-50', 9500),
  },
  {
    id: 'med-aspirina-100',
    name: 'Aspirina 100mg Comprimidos',
    activeIngredient: { name: 'Ácido Acetilsalicílico' },
    dosage: '100mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-10234/19',
    names: [{ normalizedName: 'aspirina' }, { normalizedName: 'acido acetilsalicilico' }],
    prices: makePrices('aspirina-100', 2800),
  },
  {
    id: 'med-clonazepam-05',
    name: 'Clonazepam 0.5mg Comprimidos',
    activeIngredient: { name: 'Clonazepam' },
    dosage: '0.5mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-18234/21',
    names: [{ normalizedName: 'clonazepam' }, { normalizedName: 'ravotril' }],
    prices: makePrices('clonazepam-05', 5100),
  },
  {
    id: 'med-salbutamol-inh',
    name: 'Salbutamol 100mcg Inhalador',
    activeIngredient: { name: 'Salbutamol' },
    dosage: '100mcg',
    pharmaceuticalForm: 'Inhalador',
    prescriptionRequired: false,
    ispRegistration: 'F-21345/22',
    names: [{ normalizedName: 'salbutamol' }, { normalizedName: 'ventolin' }],
    prices: makePrices('salbutamol-inh', 8500),
  },
  {
    id: 'med-vitamina-c-1000',
    name: 'Vitamina C 1000mg Comprimidos',
    activeIngredient: { name: 'Ácido Ascórbico' },
    dosage: '1000mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: null,
    names: [{ normalizedName: 'vitamina c' }, { normalizedName: 'acido ascorbico' }],
    prices: makePrices('vitamina-c-1000', 4200),
  },
  {
    id: 'med-amlodipino-5',
    name: 'Amlodipino 5mg Comprimidos',
    activeIngredient: { name: 'Amlodipino' },
    dosage: '5mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-16789/20',
    names: [{ normalizedName: 'amlodipino' }, { normalizedName: 'norvasc' }],
    prices: makePrices('amlodipino-5', 5600),
  },
  {
    id: 'med-losartan-50',
    name: 'Losartán 50mg Comprimidos',
    activeIngredient: { name: 'Losartán' },
    dosage: '50mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-19345/21',
    names: [{ normalizedName: 'losartan' }, { normalizedName: 'cozaar' }],
    prices: makePrices('losartan-50', 6800),
  },
  {
    id: 'med-ranitidina-150',
    name: 'Ranitidina 150mg Comprimidos',
    activeIngredient: { name: 'Ranitidina' },
    dosage: '150mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-12456/19',
    names: [{ normalizedName: 'ranitidina' }, { normalizedName: 'zantac' }],
    prices: makePrices('ranitidina-150', 3900),
  },
  {
    id: 'med-diclofenaco-50',
    name: 'Diclofenaco 50mg Comprimidos',
    activeIngredient: { name: 'Diclofenaco' },
    dosage: '50mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: false,
    ispRegistration: 'F-14567/20',
    names: [{ normalizedName: 'diclofenaco' }, { normalizedName: 'voltaren' }],
    prices: makePrices('diclofenaco-50', 4100),
  },
  {
    id: 'med-ciprofloxacino-500',
    name: 'Ciprofloxacino 500mg Comprimidos',
    activeIngredient: { name: 'Ciprofloxacino' },
    dosage: '500mg',
    pharmaceuticalForm: 'Comprimidos',
    prescriptionRequired: true,
    ispRegistration: 'F-21678/22',
    names: [{ normalizedName: 'ciprofloxacino' }, { normalizedName: 'ciproxin' }],
    prices: makePrices('ciprofloxacino-500', 7500),
  },
];

export function getPriceHistory(id: string) {
  const med = getMedicationById(id);
  if (!med) return [];
  const top5 = med.prices.slice(0, 5);
  const now = Date.now();
  return top5.flatMap(p =>
    Array.from({ length: 10 }, (_, i) => ({
      pharmacyName: p.pharmacyName,
      pharmacyChain: p.pharmacyChain,
      price: Math.round((p.price * (1 + Math.sin(i * 0.9 + p.price * 0.001) * 0.06)) / 10) * 10,
      recordedAt: new Date(now - (9 - i) * 3 * 24 * 60 * 60 * 1000).toISOString(), // string for JSON API
    }))
  );
}

export function searchMedications(query: string) {
  const q = query.toLowerCase().trim();
  if (!q) return MEDICATIONS;
  return MEDICATIONS.filter(m =>
    m.name.toLowerCase().includes(q) ||
    m.activeIngredient.name.toLowerCase().includes(q) ||
    m.names.some(n => n.normalizedName.includes(q))
  );
}

export function getMedicationById(id: string): DemoMedication | undefined {
  return MEDICATIONS.find(m => m.id === id);
}
