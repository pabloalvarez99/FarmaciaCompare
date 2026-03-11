export type PharmaceuticalForm =
  | 'comprimido'
  | 'capsula'
  | 'jarabe'
  | 'solucion'
  | 'inyectable'
  | 'crema'
  | 'gel'
  | 'colirio'
  | 'supositorio'
  | 'parche'
  | 'otro';

export interface ActiveIngredient {
  id: string;
  name: string;
  atcCode: string | null;
}

export interface Medication {
  id: string;
  name: string;
  activeIngredient: ActiveIngredient;
  dosage: string;
  pharmaceuticalForm: PharmaceuticalForm;
  prescriptionRequired: boolean;
  ispRegistration: string | null;
}

export interface MedicationPrice {
  pharmacyId: string;
  pharmacyName: string;
  pharmacyChain: string | null;
  price: number;
  originalPrice: number | null;
  discountPct: number | null;
  stockStatus: 'in_stock' | 'low_stock' | 'out_of_stock';
  recordedAt: Date;
}

export interface MedicationSearchResult {
  id: string;
  name: string;
  activeIngredientName: string;
  dosage: string;
  pharmaceuticalForm: string;
  prescriptionRequired: boolean;
  lowestPrice: number | null;
  highestPrice: number | null;
  pharmacyCount: number;
}
