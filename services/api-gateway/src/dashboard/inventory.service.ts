import { Injectable, ForbiddenException } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class InventoryService {
  async getPharmacyForUser(userId: string): Promise<string> {
    const staff = await prisma.pharmacyStaff.findFirst({
      where: { userId },
    });
    if (!staff) throw new ForbiddenException('Not a pharmacy staff member');
    return staff.pharmacyId;
  }

  async getProducts(pharmacyId: string, page = 1, limit = 50) {
    const [products, total] = await Promise.all([
      prisma.pharmacyProduct.findMany({
        where: { pharmacyId },
        include: {
          medication: { include: { activeIngredient: true } },
          prices: { orderBy: { recordedAt: 'desc' }, take: 1 },
        },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { rawName: 'asc' },
      }),
      prisma.pharmacyProduct.count({ where: { pharmacyId } }),
    ]);
    return {
      products,
      total,
      page,
      totalPages: Math.ceil(total / limit),
    };
  }

  async upsertProduct(
    pharmacyId: string,
    data: {
      sku: string;
      rawName: string;
      brand?: string;
      laboratory?: string;
      barcode?: string;
    },
  ) {
    return prisma.pharmacyProduct.upsert({
      where: {
        pharmacyId_sku: { pharmacyId, sku: data.sku },
      },
      update: {
        rawName: data.rawName,
        brand: data.brand,
        laboratory: data.laboratory,
        barcode: data.barcode,
        isActive: true,
      },
      create: {
        id: uuidv4(),
        pharmacyId,
        source: 'saas',
        isActive: true,
        ...data,
      },
    });
  }

  async updatePrice(
    pharmacyId: string,
    productId: string,
    price: number,
    stockStatus = 'in_stock',
  ) {
    await prisma.pharmacyProduct.findFirstOrThrow({
      where: { id: productId, pharmacyId },
    });
    return prisma.price.create({
      data: {
        id: uuidv4(),
        pharmacyProductId: productId,
        price,
        stockStatus,
        source: 'saas',
      },
    });
  }
}
