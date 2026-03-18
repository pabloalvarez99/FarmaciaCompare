import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class MedicationsService {
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
    const med = await prisma.medication.findUniqueOrThrow({
      where: { id },
      include: {
        activeIngredient: true, names: true,
        pharmacyProducts: {
          where: { isActive: true },
          include: { pharmacy: true, prices: { orderBy: { recordedAt: 'desc' }, take: 1 } },
        },
      },
    });
    return {
      ...med,
      prices: med.pharmacyProducts.map((pp) => ({
        pharmacyId: pp.pharmacyId, pharmacyName: pp.pharmacy.name,
        pharmacyChain: pp.pharmacy.chain,
        price: pp.prices[0]?.price ?? null, originalPrice: pp.prices[0]?.originalPrice ?? null,
        discountPct: pp.prices[0]?.discountPct ?? null,
        stockStatus: pp.prices[0]?.stockStatus ?? 'unknown',
        recordedAt: pp.prices[0]?.recordedAt ?? null,
      })).filter((p) => p.price !== null).sort((a, b) => (a.price ?? 0) - (b.price ?? 0)),
    };
  }

  async getPriceHistory(id: string, days = 30) {
    const since = new Date();
    since.setDate(since.getDate() - days);
    const products = await prisma.pharmacyProduct.findMany({
      where: { medicationId: id, isActive: true },
      include: {
        pharmacy: { select: { name: true, chain: true } },
        prices: { where: { recordedAt: { gte: since } }, orderBy: { recordedAt: 'asc' }, select: { price: true, recordedAt: true } },
      },
    });
    return products.filter((p) => p.prices.length > 0).map((p) => ({
      pharmacyName: p.pharmacy.name, pharmacyChain: p.pharmacy.chain,
      history: p.prices.map((pr) => ({ price: pr.price, date: pr.recordedAt.toISOString().split('T')[0] })),
    }));
  }
}
