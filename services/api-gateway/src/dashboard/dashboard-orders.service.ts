import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class DashboardOrdersService {
  async getPendingOrders(pharmacyId: string) {
    return prisma.order.findMany({
      where: {
        pharmacyId,
        status: { in: ['pending', 'confirmed', 'preparing'] },
      },
      include: {
        user: { select: { name: true, email: true } },
        items: {
          include: {
            medication: { select: { name: true } },
          },
        },
      },
      orderBy: { createdAt: 'desc' },
    });
  }

  async updateOrderStatus(
    pharmacyId: string,
    orderId: string,
    status: string,
  ) {
    await prisma.order.findFirstOrThrow({
      where: { id: orderId, pharmacyId },
    });
    return prisma.order.update({
      where: { id: orderId },
      data: { status },
    });
  }
}
