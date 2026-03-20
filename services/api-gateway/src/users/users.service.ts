import { Injectable, NotFoundException } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class UsersService {
  async getProfile(userId: string) {
    const user = await prisma.user.findUnique({
      where: { id: userId },
      select: {
        id: true,
        email: true,
        name: true,
        phone: true,
        avatarUrl: true,
        rut: true,
        address: true,
        city: true,
        region: true,
        role: true,
        emailVerified: true,
        createdAt: true,
      },
    });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async updateProfile(
    userId: string,
    data: { name?: string; phone?: string; address?: string; city?: string; region?: string },
  ) {
    return prisma.user.update({
      where: { id: userId },
      data,
      select: {
        id: true,
        email: true,
        name: true,
        phone: true,
        address: true,
        city: true,
        region: true,
      },
    });
  }

  async updatePushToken(userId: string, pushToken: string) {
    await prisma.user.update({
      where: { id: userId },
      data: { pushToken },
    });
    return { success: true };
  }

  async getPriceAlerts(userId: string) {
    return prisma.priceAlert.findMany({
      where: { userId, isActive: true },
      include: {
        medication: { select: { id: true, name: true, dosage: true } },
        pharmacy: { select: { id: true, name: true, chain: true } },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async createPriceAlert(
    userId: string,
    data: { medicationId: string; targetPrice: number; pharmacyId?: string },
  ) {
    return prisma.priceAlert.create({
      data: {
        userId,
        medicationId: data.medicationId,
        targetPrice: data.targetPrice,
        pharmacyId: data.pharmacyId ?? null,
      },
      include: {
        medication: { select: { name: true } },
      },
    });
  }

  async deletePriceAlert(userId: string, alertId: string) {
    await prisma.priceAlert.updateMany({
      where: { id: alertId, userId },
      data: { isActive: false },
    });
    return { success: true };
  }
}
