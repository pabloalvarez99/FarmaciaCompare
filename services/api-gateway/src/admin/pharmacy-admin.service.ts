import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class PharmacyAdminService {
  async listPharmacies(page = 1, limit = 50) {
    const [pharmacies, total] = await Promise.all([
      prisma.pharmacy.findMany({
        include: { _count: { select: { products: true, orders: true } } },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { name: 'asc' },
      }),
      prisma.pharmacy.count(),
    ]);
    return { pharmacies, total, page, totalPages: Math.ceil(total / limit) };
  }

  async createPharmacy(data: {
    name: string;
    chain?: string;
    type: string;
    address?: string;
    phone?: string;
    email?: string;
  }) {
    return prisma.pharmacy.create({ data });
  }

  async addStaff(pharmacyId: string, userId: string, role = 'pharmacy_admin') {
    return prisma.pharmacyStaff.create({
      data: { pharmacyId, userId, role },
    });
  }
}
