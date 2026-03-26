export interface Category {
  id: string;
  label: string;
  emoji: string;
}

export const CATEGORIES: Category[] = [
  { id: 'analgesicos', label: 'Analgésicos', emoji: '💊' },
  { id: 'antibioticos', label: 'Antibióticos', emoji: '🔬' },
  { id: 'cardiovascular', label: 'Cardiovascular', emoji: '❤️' },
  { id: 'respiratorio', label: 'Respiratorio', emoji: '🫁' },
  { id: 'digestivo', label: 'Digestivo', emoji: '🩺' },
  { id: 'nervioso', label: 'Sistema Nervioso', emoji: '🧠' },
  { id: 'endocrinologia', label: 'Endocrinología', emoji: '⚡' },
  { id: 'alergias', label: 'Alergias', emoji: '🌸' },
  { id: 'vitaminas', label: 'Vitaminas', emoji: '✨' },
];

export const MED_CATEGORIES: Record<string, string> = {
  'med-paracetamol-500': 'analgesicos',
  'med-ibuprofeno-400': 'analgesicos',
  'med-aspirina-100': 'analgesicos',
  'med-diclofenaco-50': 'analgesicos',
  'med-amoxicilina-500': 'antibioticos',
  'med-ciprofloxacino-500': 'antibioticos',
  'med-enalapril-10': 'cardiovascular',
  'med-amlodipino-5': 'cardiovascular',
  'med-losartan-50': 'cardiovascular',
  'med-atorvastatina-20': 'cardiovascular',
  'med-salbutamol-inh': 'respiratorio',
  'med-omeprazol-20': 'digestivo',
  'med-ranitidina-150': 'digestivo',
  'med-clonazepam-05': 'nervioso',
  'med-sertralina-50': 'nervioso',
  'med-metformina-850': 'endocrinologia',
  'med-levotiroxina-100': 'endocrinologia',
  'med-loratadina-10': 'alergias',
  'med-vitamina-c-1000': 'vitaminas',
};

export function getCategoryLabel(medicationId: string): string | null {
  const catId = MED_CATEGORIES[medicationId];
  if (!catId) return null;
  return CATEGORIES.find((c) => c.id === catId)?.label ?? null;
}
