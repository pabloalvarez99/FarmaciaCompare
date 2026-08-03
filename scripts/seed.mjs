/**
 * Seed script: ISP medications + pharmacies across Chile (Coquimbo region focus).
 * Run: node scripts/seed.mjs
 */
import { PrismaClient } from '@prisma/client';
import { randomUUID } from 'crypto';

const prisma = new PrismaClient({
  datasources: { db: { url: process.env.DATABASE_URL } },
});

// ─── 40 Medications ───────────────────────────────────────────────────────────
const ISP_DATA = [
  // Analgésicos / Antiinflamatorios
  { reg: 'F-20001', name: 'Tapsin Forte Comprimidos', ingredient: 'Paracetamol', form: 'Comprimido', dosage: '500 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: false, category: 'analgesico' },
  { reg: 'F-20002', name: 'Advil 200mg Cápsula Blanda', ingredient: 'Ibuprofeno', form: 'Cápsula', dosage: '200 mg', lab: 'Pfizer Inc.', route: 'oral', rx: false, category: 'analgesico' },
  { reg: 'F-20021', name: 'Ibuprofeno 400mg Comprimido', ingredient: 'Ibuprofeno', form: 'Comprimido', dosage: '400 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: false, category: 'analgesico' },
  { reg: 'F-20022', name: 'Naproxeno 500mg Comprimido', ingredient: 'Naproxeno', form: 'Comprimido', dosage: '500 mg', lab: 'Bayer S.A.', route: 'oral', rx: false, category: 'analgesico' },
  { reg: 'F-20023', name: 'Diclofenaco 50mg Comprimido', ingredient: 'Diclofenaco Sódico', form: 'Comprimido', dosage: '50 mg', lab: 'Novartis S.A.', route: 'oral', rx: false, category: 'analgesico' },
  { reg: 'F-20024', name: 'Ketorolaco 10mg Comprimido', ingredient: 'Ketorolaco', form: 'Comprimido', dosage: '10 mg', lab: 'Laboratorio Beta', route: 'oral', rx: true, category: 'analgesico' },
  // Antibióticos
  { reg: 'F-20003', name: 'Amoxicilina 500mg Cápsula', ingredient: 'Amoxicilina', form: 'Cápsula', dosage: '500 mg', lab: 'Laboratorio Beta', route: 'oral', rx: true, category: 'antibiotico' },
  { reg: 'F-20005', name: 'Amoxicilina 250mg/5ml Suspensión', ingredient: 'Amoxicilina', form: 'Suspensión', dosage: '250 mg/5 ml', lab: 'Laboratorio Beta', route: 'oral', rx: true, category: 'antibiotico' },
  { reg: 'F-20025', name: 'Azitromicina 500mg Comprimido', ingredient: 'Azitromicina', form: 'Comprimido', dosage: '500 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'antibiotico' },
  { reg: 'F-20026', name: 'Ciprofloxacino 500mg Comprimido', ingredient: 'Ciprofloxacino', form: 'Comprimido', dosage: '500 mg', lab: 'Bayer S.A.', route: 'oral', rx: true, category: 'antibiotico' },
  { reg: 'F-20027', name: 'Cloxacilina 500mg Cápsula', ingredient: 'Cloxacilina', form: 'Cápsula', dosage: '500 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: true, category: 'antibiotico' },
  // Cardiovascular / Hipertensión
  { reg: 'F-20006', name: 'Losartán 50mg Comprimido', ingredient: 'Losartán Potásico', form: 'Comprimido', dosage: '50 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: true, category: 'cardiovascular' },
  { reg: 'F-20028', name: 'Losartán 100mg Comprimido', ingredient: 'Losartán Potásico', form: 'Comprimido', dosage: '100 mg', lab: 'Merck S.A.', route: 'oral', rx: true, category: 'cardiovascular' },
  { reg: 'F-20029', name: 'Enalapril 10mg Comprimido', ingredient: 'Enalapril', form: 'Comprimido', dosage: '10 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: true, category: 'cardiovascular' },
  { reg: 'F-20030', name: 'Amlodipino 5mg Comprimido', ingredient: 'Amlodipino', form: 'Comprimido', dosage: '5 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'cardiovascular' },
  { reg: 'F-20031', name: 'Metoprolol 50mg Comprimido', ingredient: 'Metoprolol', form: 'Comprimido', dosage: '50 mg', lab: 'AstraZeneca', route: 'oral', rx: true, category: 'cardiovascular' },
  { reg: 'F-20032', name: 'Aspirina 100mg Comprimido', ingredient: 'Ácido Acetilsalicílico', form: 'Comprimido', dosage: '100 mg', lab: 'Bayer S.A.', route: 'oral', rx: false, category: 'cardiovascular' },
  // Gastro
  { reg: 'F-20007', name: 'Omeprazol 20mg Cápsula', ingredient: 'Omeprazol', form: 'Cápsula', dosage: '20 mg', lab: 'Pfizer Inc.', route: 'oral', rx: false, category: 'gastro' },
  { reg: 'F-20033', name: 'Omeprazol 40mg Cápsula', ingredient: 'Omeprazol', form: 'Cápsula', dosage: '40 mg', lab: 'Laboratorio Beta', route: 'oral', rx: false, category: 'gastro' },
  { reg: 'F-20034', name: 'Ranitidina 150mg Comprimido', ingredient: 'Ranitidina', form: 'Comprimido', dosage: '150 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: false, category: 'gastro' },
  { reg: 'F-20035', name: 'Metoclopramida 10mg Comprimido', ingredient: 'Metoclopramida', form: 'Comprimido', dosage: '10 mg', lab: 'Novartis S.A.', route: 'oral', rx: false, category: 'gastro' },
  // Diabetes
  { reg: 'F-20008', name: 'Metformina 850mg Comprimido', ingredient: 'Metformina', form: 'Comprimido', dosage: '850 mg', lab: 'Merck S.A.', route: 'oral', rx: true, category: 'diabetes' },
  { reg: 'F-20036', name: 'Metformina 500mg Comprimido', ingredient: 'Metformina', form: 'Comprimido', dosage: '500 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: true, category: 'diabetes' },
  { reg: 'F-20037', name: 'Glibenclamida 5mg Comprimido', ingredient: 'Glibenclamida', form: 'Comprimido', dosage: '5 mg', lab: 'Laboratorio Beta', route: 'oral', rx: true, category: 'diabetes' },
  // Colesterol
  { reg: 'F-20009', name: 'Atorvastatina 20mg Comprimido', ingredient: 'Atorvastatina', form: 'Comprimido', dosage: '20 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'colesterol' },
  { reg: 'F-20038', name: 'Atorvastatina 40mg Comprimido', ingredient: 'Atorvastatina', form: 'Comprimido', dosage: '40 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'colesterol' },
  { reg: 'F-20039', name: 'Simvastatina 20mg Comprimido', ingredient: 'Simvastatina', form: 'Comprimido', dosage: '20 mg', lab: 'Merck S.A.', route: 'oral', rx: true, category: 'colesterol' },
  // Tiroides
  { reg: 'F-20004', name: 'Levotiroxina 50mcg Comprimido', ingredient: 'Levotiroxina Sódica', form: 'Comprimido', dosage: '50 mcg', lab: 'Merck S.A.', route: 'oral', rx: true, category: 'tiroides' },
  { reg: 'F-20040', name: 'Levotiroxina 100mcg Comprimido', ingredient: 'Levotiroxina Sódica', form: 'Comprimido', dosage: '100 mcg', lab: 'Merck S.A.', route: 'oral', rx: true, category: 'tiroides' },
  // Neurológico / Psiquiátrico
  { reg: 'F-20010', name: 'Clonazepam 0.5mg Comprimido', ingredient: 'Clonazepam', form: 'Comprimido', dosage: '0.5 mg', lab: 'Laboratorio Beta', route: 'oral', rx: true, category: 'neurologico' },
  { reg: 'F-20041', name: 'Clonazepam 2mg Comprimido', ingredient: 'Clonazepam', form: 'Comprimido', dosage: '2 mg', lab: 'Roche', route: 'oral', rx: true, category: 'neurologico' },
  { reg: 'F-20042', name: 'Fluoxetina 20mg Cápsula', ingredient: 'Fluoxetina', form: 'Cápsula', dosage: '20 mg', lab: 'Eli Lilly', route: 'oral', rx: true, category: 'neurologico' },
  { reg: 'F-20043', name: 'Sertralina 50mg Comprimido', ingredient: 'Sertralina', form: 'Comprimido', dosage: '50 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'neurologico' },
  // Respiratorio
  { reg: 'F-20044', name: 'Salbutamol 100mcg Inhalador', ingredient: 'Salbutamol', form: 'Aerosol', dosage: '100 mcg/dosis', lab: 'GlaxoSmithKline', route: 'inhalatoria', rx: false, category: 'respiratorio' },
  { reg: 'F-20045', name: 'Loratadina 10mg Comprimido', ingredient: 'Loratadina', form: 'Comprimido', dosage: '10 mg', lab: 'Schering-Plough', route: 'oral', rx: false, category: 'respiratorio' },
  { reg: 'F-20046', name: 'Cetirizina 10mg Comprimido', ingredient: 'Cetirizina', form: 'Comprimido', dosage: '10 mg', lab: 'UCB S.A.', route: 'oral', rx: false, category: 'respiratorio' },
  // Vitaminas / Suplementos
  { reg: 'F-20047', name: 'Vitamina D3 2000 UI Cápsula', ingredient: 'Colecalciferol', form: 'Cápsula', dosage: '2000 UI', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: false, category: 'vitamina' },
  { reg: 'F-20048', name: 'Ácido Fólico 5mg Comprimido', ingredient: 'Ácido Fólico', form: 'Comprimido', dosage: '5 mg', lab: 'Laboratorio Beta', route: 'oral', rx: false, category: 'vitamina' },
  // Otros
  { reg: 'F-20049', name: 'Prednisona 20mg Comprimido', ingredient: 'Prednisona', form: 'Comprimido', dosage: '20 mg', lab: 'Laboratorio Chile S.A.', route: 'oral', rx: true, category: 'corticoide' },
  { reg: 'F-20050', name: 'Alprazolam 0.25mg Comprimido', ingredient: 'Alprazolam', form: 'Comprimido', dosage: '0.25 mg', lab: 'Pfizer Inc.', route: 'oral', rx: true, category: 'neurologico' },
];

// ─── Pharmacies: Santiago + Coquimbo Region ───────────────────────────────────
const PHARMACIES = [
  // Santiago (existing)
  { name: 'Cruz Verde Las Condes', chain: 'cruz_verde', type: 'chain', city: 'Las Condes', region: 'Metropolitana' },
  { name: 'Cruz Verde Providencia', chain: 'cruz_verde', type: 'chain', city: 'Providencia', region: 'Metropolitana' },
  { name: 'Salcobrand Vitacura', chain: 'salcobrand', type: 'chain', city: 'Vitacura', region: 'Metropolitana' },
  { name: 'Salcobrand Santiago Centro', chain: 'salcobrand', type: 'chain', city: 'Santiago', region: 'Metropolitana' },
  { name: 'Farmacia Ahumada Ñuñoa', chain: 'ahumada', type: 'chain', city: 'Ñuñoa', region: 'Metropolitana' },
  { name: 'Dr. Simi Maipú', chain: 'dr_simi', type: 'chain', city: 'Maipú', region: 'Metropolitana' },

  // La Serena (capital Coquimbo)
  { name: 'Cruz Verde La Serena Centro', chain: 'cruz_verde', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Cruz Verde La Serena El Faro', chain: 'cruz_verde', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Salcobrand La Serena', chain: 'salcobrand', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Farmacia Ahumada La Serena', chain: 'ahumada', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Dr. Simi La Serena', chain: 'dr_simi', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Knop La Serena', chain: 'knop', type: 'chain', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Farmacia del Pueblo La Serena', chain: null, type: 'independent', city: 'La Serena', region: 'Coquimbo' },
  { name: 'Farmacia San Francisco La Serena', chain: null, type: 'independent', city: 'La Serena', region: 'Coquimbo' },

  // Coquimbo ciudad
  { name: 'Cruz Verde Coquimbo', chain: 'cruz_verde', type: 'chain', city: 'Coquimbo', region: 'Coquimbo' },
  { name: 'Salcobrand Coquimbo Baquedano', chain: 'salcobrand', type: 'chain', city: 'Coquimbo', region: 'Coquimbo' },
  { name: 'Dr. Simi Coquimbo', chain: 'dr_simi', type: 'chain', city: 'Coquimbo', region: 'Coquimbo' },
  { name: 'Farmacia Ahumada Coquimbo', chain: 'ahumada', type: 'chain', city: 'Coquimbo', region: 'Coquimbo' },
  { name: 'Farmacia Popular Coquimbo', chain: null, type: 'popular', city: 'Coquimbo', region: 'Coquimbo' },

  // Ovalle
  { name: 'Cruz Verde Ovalle', chain: 'cruz_verde', type: 'chain', city: 'Ovalle', region: 'Coquimbo' },
  { name: 'Salcobrand Ovalle', chain: 'salcobrand', type: 'chain', city: 'Ovalle', region: 'Coquimbo' },
  { name: 'Dr. Simi Ovalle', chain: 'dr_simi', type: 'chain', city: 'Ovalle', region: 'Coquimbo' },
  { name: 'Farmacia del Mercado Ovalle', chain: null, type: 'independent', city: 'Ovalle', region: 'Coquimbo' },

  // Illapel
  { name: 'Cruz Verde Illapel', chain: 'cruz_verde', type: 'chain', city: 'Illapel', region: 'Coquimbo' },
  { name: 'Dr. Simi Illapel', chain: 'dr_simi', type: 'chain', city: 'Illapel', region: 'Coquimbo' },
  { name: 'Farmacia Central Illapel', chain: null, type: 'independent', city: 'Illapel', region: 'Coquimbo' },

  // Vicuña
  { name: 'Cruz Verde Vicuña', chain: 'cruz_verde', type: 'chain', city: 'Vicuña', region: 'Coquimbo' },
  { name: 'Farmacia Vicuña', chain: null, type: 'independent', city: 'Vicuña', region: 'Coquimbo' },

  // Los Vilos
  { name: 'Dr. Simi Los Vilos', chain: 'dr_simi', type: 'chain', city: 'Los Vilos', region: 'Coquimbo' },
  { name: 'Farmacia Los Vilos', chain: null, type: 'independent', city: 'Los Vilos', region: 'Coquimbo' },

  // Andacollo
  { name: 'Farmacia Andacollo', chain: null, type: 'independent', city: 'Andacollo', region: 'Coquimbo' },

  // Monte Patria
  { name: 'Farmacia Monte Patria', chain: null, type: 'independent', city: 'Monte Patria', region: 'Coquimbo' },
];

// Base prices (CLP) per medication
const BASE_PRICES = {
  'F-20001': 2490, 'F-20002': 3990, 'F-20003': 4500, 'F-20004': 6800,
  'F-20005': 5200, 'F-20006': 3100, 'F-20007': 2800, 'F-20008': 2200,
  'F-20009': 7500, 'F-20010': 5900, 'F-20021': 2990, 'F-20022': 4200,
  'F-20023': 3800, 'F-20024': 8900, 'F-20025': 12500, 'F-20026': 9800,
  'F-20027': 7200, 'F-20028': 4100, 'F-20029': 2500, 'F-20030': 4800,
  'F-20031': 5600, 'F-20032': 1200, 'F-20033': 3900, 'F-20034': 2100,
  'F-20035': 2800, 'F-20036': 1800, 'F-20037': 2300, 'F-20038': 9200,
  'F-20039': 6100, 'F-20040': 8500, 'F-20041': 7200, 'F-20042': 11000,
  'F-20043': 9500, 'F-20044': 18500, 'F-20045': 2900, 'F-20046': 3200,
  'F-20047': 4500, 'F-20048': 1500, 'F-20049': 5800, 'F-20050': 4200,
};

// Price variance per pharmacy (chain pharmacies tend to be pricier)
function getPrice(base, pharmacy, seed) {
  const chainMultiplier = {
    cruz_verde: 1.05, salcobrand: 1.08, ahumada: 1.10,
    dr_simi: 0.82, knop: 0.90, popular: 0.75,
  };
  const mult = pharmacy.chain ? (chainMultiplier[pharmacy.chain] ?? 1.0) : 0.78;
  // Add per-pharmacy variance using a deterministic seed
  const variance = 0.93 + (seed % 15) * 0.01;
  return Math.round(base * mult * variance / 10) * 10;
}

// Generate past prices for history (last 30 days)
function generateHistory(basePrice, pharmacy, daysBack = 30) {
  const points = [];
  for (let d = daysBack; d >= 0; d -= 3) {
    const date = new Date();
    date.setDate(date.getDate() - d);
    // Slight price fluctuation over time
    const fluctuation = 0.95 + Math.sin(d * 0.3) * 0.05;
    const price = Math.round(basePrice * fluctuation / 10) * 10;
    points.push({ date, price });
  }
  return points;
}

async function main() {
  console.log('Seeding database...\n');

  // 1. Create active ingredients
  const ingredientMap = new Map();
  const ingredients = [...new Set(ISP_DATA.map(d => d.ingredient))];
  for (const name of ingredients) {
    const existing = await prisma.activeIngredient.findFirst({ where: { name } });
    const ing = existing ?? await prisma.activeIngredient.create({
      data: { id: randomUUID(), name },
    });
    ingredientMap.set(name, ing.id);
  }
  console.log(`✓ ${ingredientMap.size} active ingredients`);

  // 2. Create medications
  const medMap = new Map();
  for (const d of ISP_DATA) {
    const existing = await prisma.medication.findFirst({ where: { ispRegistration: d.reg } });
    const med = existing ?? await prisma.medication.create({
      data: {
        id: randomUUID(),
        name: d.name,
        activeIngredientId: ingredientMap.get(d.ingredient),
        dosage: d.dosage,
        pharmaceuticalForm: d.form,
        routeOfAdministration: d.route,
        prescriptionRequired: d.rx,
        ispRegistration: d.reg,
      },
    });
    medMap.set(d.reg, med.id);
  }
  console.log(`✓ ${ISP_DATA.length} medications`);

  // 3. Create pharmacies
  const pharmacyMap = new Map(); // name → id
  for (const p of PHARMACIES) {
    const existing = await prisma.pharmacy.findFirst({ where: { name: p.name } });
    const pharmacy = existing ?? await prisma.pharmacy.create({
      data: {
        id: randomUUID(),
        name: p.name,
        chain: p.chain ?? null,
        type: p.type,
        city: p.city,
        region: p.region,
        isActive: true,
      },
    });
    pharmacyMap.set(p.name, pharmacy.id);
  }
  console.log(`✓ ${PHARMACIES.length} pharmacies`);

  // 4. Create pharmacy products + prices (with history)
  let productCount = 0, priceCount = 0;

  for (let pi = 0; pi < PHARMACIES.length; pi++) {
    const pharmacy = PHARMACIES[pi];
    const pharmacyId = pharmacyMap.get(pharmacy.name);

    // Not every pharmacy carries every medication (simulate real coverage)
    // Chain pharmacies: full catalog; independents: ~70% of catalog
    const coverage = pharmacy.chain ? 1.0 : 0.7;

    for (let mi = 0; mi < ISP_DATA.length; mi++) {
      const d = ISP_DATA[mi];
      // Skip some meds for independents
      if (coverage < 1.0 && ((pi * 7 + mi * 3) % 10) >= Math.floor(coverage * 10)) continue;

      const medId = medMap.get(d.reg);
      const base = BASE_PRICES[d.reg];
      const currentPrice = getPrice(base, pharmacy, pi + mi);

      const existing = await prisma.pharmacyProduct.findFirst({
        where: { pharmacyId, medicationId: medId },
      });
      const product = existing ?? await prisma.pharmacyProduct.create({
        data: {
          id: randomUUID(),
          pharmacyId,
          medicationId: medId,
          sku: `${d.reg}-${pi}`,
          rawName: d.name,
          source: 'seed',
          isActive: true,
        },
      });
      productCount++;

      // Add price history (10 data points over last 30 days)
      const existingPrices = await prisma.price.count({ where: { pharmacyProductId: product.id } });
      if (existingPrices === 0) {
        const history = generateHistory(currentPrice, pharmacy, 30);
        for (const { date, price } of history) {
          await prisma.price.create({
            data: {
              id: randomUUID(),
              pharmacyProductId: product.id,
              price,
              originalPrice: Math.random() > 0.65 ? Math.round(price * 1.2 / 10) * 10 : null,
              stockStatus: Math.random() > 0.08 ? 'in_stock' : 'low_stock',
              source: 'seed',
              recordedAt: date,
            },
          });
          priceCount++;
        }
      }
    }
    process.stdout.write(`  Pharmacy ${pi + 1}/${PHARMACIES.length}: ${pharmacy.name}\r`);
  }

  console.log(`\n✓ ${productCount} pharmacy products`);
  console.log(`✓ ${priceCount} price records (with history)`);

  // 5. Refresh materialized view
  await prisma.$executeRawUnsafe('REFRESH MATERIALIZED VIEW current_prices');
  console.log('✓ Refreshed current_prices view\n');
  console.log('Seed complete!');
}

main()
  .catch(e => { console.error(e); process.exit(1); })
  .finally(() => prisma.$disconnect());
