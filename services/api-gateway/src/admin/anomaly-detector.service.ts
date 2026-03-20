import { Injectable, Logger } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class AnomalyDetectorService {
  private readonly logger = new Logger(AnomalyDetectorService.name);

  async detectPriceAnomalies() {
    const threshold = 0.5;
    const since = new Date();
    since.setDate(since.getDate() - 7);

    const products = await prisma.pharmacyProduct.findMany({
      where: { isActive: true, medicationId: { not: null } },
      include: {
        prices: {
          where: { recordedAt: { gte: since } },
          orderBy: { recordedAt: 'desc' },
        },
        pharmacy: { select: { name: true } },
        medication: { select: { name: true } },
      },
    });

    const anomalies = [];
    for (const product of products) {
      if (product.prices.length < 3) continue;
      const latestPrice = product.prices[0].price;
      const historicalPrices = product.prices.slice(1).map((p) => p.price);
      const avg =
        historicalPrices.reduce((a, b) => a + b, 0) / historicalPrices.length;
      if (avg === 0) continue;
      const deviation = Math.abs(latestPrice - avg) / avg;
      if (deviation > threshold) {
        anomalies.push({
          productId: product.id,
          pharmacyName: product.pharmacy?.name,
          medicationName: product.medication?.name,
          currentPrice: latestPrice,
          avgPrice: Math.round(avg),
          deviationPct: Math.round(deviation * 100),
        });
      }
    }
    return anomalies;
  }
}
