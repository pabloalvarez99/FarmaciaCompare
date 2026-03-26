import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { PriceServiceClient } from './price-service.client';

@Injectable()
export class MedicationsService {
  constructor(private readonly priceService: PriceServiceClient) {}
  async search(query: string, page = 1, limit = 20) {
    const skip = (page - 1) * limit;
    const where = query
      ? {
          OR: [
            { name: { contains: query, mode: 'insensitive' as const } },
            { names: { some: { normalizedName: { contains: query.toLowerCase() } } } },
            { activeIngredient: { name: { contains: query, mode: 'insensitive' as const } } },
          ],
        }
      : {};

    const [medications, total] = await Promise.all([
      prisma.medication.findMany({
        where, skip, take: limit,
        include: {
          activeIngredient: true,
          names: { take: 3 },
          pharmacyProducts: {
            where: { isActive: true },
            include: { prices: { orderBy: { recordedAt: 'desc' }, take: 1 } },
          },
        },
        orderBy: { name: 'asc' },
      }),
      prisma.medication.count({ where }),
    ]);

    const results = medications.map((med) => {
      const allPrices = med.pharmacyProducts
        .flatMap((pp) => pp.prices).map((p) => p.price).filter((p) => p > 0);
      return {
        id: med.id, name: med.name,
        activeIngredientName: med.activeIngredient?.name ?? null,
        dosage: med.dosage, pharmaceuticalForm: med.pharmaceuticalForm,
        prescriptionRequired: med.prescriptionRequired,
        lowestPrice: allPrices.length > 0 ? Math.min(...allPrices) : null,
        highestPrice: allPrices.length > 0 ? Math.max(...allPrices) : null,
        pharmacyCount: med.pharmacyProducts.length,
      };
    });
    return { results, total, page, limit, totalPages: Math.ceil(total / limit) };
  }

  async findById(id: string) {
    // Medication metadata from Prisma, prices from Rust price service (parallel)
    const [med, prices] = await Promise.all([
      prisma.medication.findUniqueOrThrow({
        where: { id },
        include: { activeIngredient: true, names: true },
      }),
      this.priceService.getPrices(id),
    ]);
    return { ...med, prices };
  }

  async getPriceHistory(id: string, days = 30) {
    return this.priceService.getPriceHistory(id, days);
  }
}
