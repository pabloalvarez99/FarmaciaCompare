export type PharmacyChain =
  | 'cruz_verde'
  | 'salcobrand'
  | 'ahumada'
  | 'dr_simi'
  | 'independent';

export interface Pharmacy {
  id: string;
  name: string;
  chain: PharmacyChain | null;
  type: 'chain' | 'independent';
  address: string | null;
  city: string | null;
  region: string | null;
  lat: number | null;
  lng: number | null;
  phone: string | null;
  logoUrl: string | null;
  hasDelivery: boolean;
  hasPickup: boolean;
  rating: number | null;
  ratingCount: number;
}
