import { Injectable, Logger, ServiceUnavailableException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface PriceComparison {
  pharmacyId: string;
  pharmacyName: string;
  pharmacyChain: string | null;
  pharmacyCity: string | null;
  pharmacyRegion: string | null;
  pharmacyProductId: string;
  price: number;
  originalPrice: number | null;
  discountPct: number | null;
  stockStatus: string | null;
  recordedAt: string;
}

export interface PriceHistoryPoint {
  recordedAt: string;
  price: number;
  pharmacyName: string;
}

export interface PriceStats {
  medicationId: string;
  minPrice: number | null;
  maxPrice: number | null;
  avgPrice: number | null;
  pharmacyCount: number | null;
}

@Injectable()
export class PriceServiceClient {
  private readonly logger = new Logger(PriceServiceClient.name);
  private readonly baseUrl: string;

  constructor(private readonly config: ConfigService) {
    this.baseUrl = config.get('PRICE_SERVICE_URL', 'http://localhost:4001');
  }

  private async get<T>(path: string): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`);
    } catch (err) {
      this.logger.error(`Price service unreachable: ${err}`);
      throw new ServiceUnavailableException('Price service unavailable');
    }
    if (!res.ok) {
      if (res.status === 404) return null as T;
      this.logger.error(`Price service error ${res.status} for ${path}`);
      throw new ServiceUnavailableException('Price service error');
    }
    return res.json() as Promise<T>;
  }

  async getPrices(medicationId: string): Promise<PriceComparison[]> {
    return this.get(`/api/v1/prices/medications/${medicationId}`);
  }

  async getPriceHistory(medicationId: string, days = 30): Promise<PriceHistoryPoint[]> {
    return this.get(`/api/v1/prices/medications/${medicationId}/history?days=${days}`);
  }

  async getPriceStats(medicationId: string): Promise<PriceStats | null> {
    return this.get(`/api/v1/prices/medications/${medicationId}/stats`);
  }
}
