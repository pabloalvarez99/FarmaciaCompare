import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class PharmaciesService {
  async listActive() {
    return prisma.pharmacy.findMany({
      where: { isActive: true },
      select: {
        id: true,
        name: true,
        chain: true,
        address: true,
        city: true,
        region: true,
        phone: true,
        lat: true,
        lng: true,
        isActive: true,
        hasDelivery: true,
        hasPickup: true,
        rating: true,
        ratingCount: true,
      },
      orderBy: { name: 'asc' },
    });
  }

  async getById(id: string) {
    return prisma.pharmacy.findUnique({
      where: { id },
      select: {
        id: true,
        name: true,
        chain: true,
        address: true,
        city: true,
        region: true,
        phone: true,
        email: true,
        website: true,
        lat: true,
        lng: true,
        isActive: true,
        hasDelivery: true,
        hasPickup: true,
        rating: true,
        ratingCount: true,
        logoUrl: true,
      },
    });
  }
}
