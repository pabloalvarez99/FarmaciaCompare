import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class CatalogService {
  async searchMedications(query: string, page = 1, limit = 50) {
    const where = query
      ? {
          OR: [
            { name: { contains: query, mode: 'insensitive' as const } },
            { ispRegistration: { contains: query } },
            {
              activeIngredient: {
                name: { contains: query, mode: 'insensitive' as const },
              },
            },
          ],
        }
      : {};

    const [meds, total] = await Promise.all([
      prisma.medication.findMany({
        where,
        include: {
          activeIngredient: true,
          names: true,
          _count: { select: { pharmacyProducts: true } },
        },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { name: 'asc' },
      }),
      prisma.medication.count({ where }),
    ]);

    return { meds, total, page, totalPages: Math.ceil(total / limit) };
  }

  async getUnmatchedProducts(page = 1, limit = 50) {
    return prisma.pharmacyProduct.findMany({
      where: { medicationId: null, isActive: true },
      include: { pharmacy: { select: { name: true, chain: true } } },
      skip: (page - 1) * limit,
      take: limit,
    });
  }

  async linkProduct(productId: string, medicationId: string) {
    return prisma.pharmacyProduct.update({
      where: { id: productId },
      data: { medicationId },
    });
  }

  async mergeMedications(sourceId: string, targetId: string) {
    await prisma.$transaction([
      prisma.pharmacyProduct.updateMany({
        where: { medicationId: sourceId },
        data: { medicationId: targetId },
      }),
      prisma.medicationName.updateMany({
        where: { medicationId: sourceId },
        data: { medicationId: targetId },
      }),
      prisma.priceAlert.updateMany({
        where: { medicationId: sourceId },
        data: { medicationId: targetId },
      }),
      prisma.medication.delete({ where: { id: sourceId } }),
    ]);
  }
}
