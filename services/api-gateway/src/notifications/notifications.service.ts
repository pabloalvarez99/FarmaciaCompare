import { Injectable, Logger } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  async checkPriceAlerts() {
    const activeAlerts = await prisma.priceAlert.findMany({
      where: { isActive: true },
      include: {
        user: { select: { pushToken: true, email: true } },
        medication: { select: { name: true } },
      },
    });

    const triggered = [];

    for (const alert of activeAlerts) {
      const lowestPrice = await prisma.price.findFirst({
        where: {
          pharmacyProduct: {
            medicationId: alert.medicationId,
            ...(alert.pharmacyId ? { pharmacyId: alert.pharmacyId } : {}),
          },
        },
        orderBy: { price: 'asc' },
      });

      if (!lowestPrice) continue;
      if (lowestPrice.price <= alert.targetPrice) {
        triggered.push({
          alertId: alert.id,
          medicationName: alert.medication.name,
          currentPrice: lowestPrice.price,
          targetPrice: alert.targetPrice,
          userEmail: alert.user.email,
          pushToken: alert.user.pushToken,
        });

        await prisma.priceAlert.update({
          where: { id: alert.id },
          data: { lastTriggered: new Date() },
        });
      }
    }

    this.logger.log(`Price alert check: ${triggered.length} triggered out of ${activeAlerts.length}`);
    return triggered;
  }
}
