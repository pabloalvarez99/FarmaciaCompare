import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { prisma } from '@farmacia/database';

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  @Cron(CronExpression.EVERY_HOUR)
  async handlePriceAlertCron() {
    this.logger.log('Running scheduled price alert check...');
    const triggered = await this.checkPriceAlerts();
    if (triggered.length > 0) {
      this.logger.log(`Sending ${triggered.length} price alert notifications`);
      for (const alert of triggered) {
        await this.sendNotification(alert);
      }
    }
  }

  async checkPriceAlerts() {
    const activeAlerts = await prisma.priceAlert.findMany({
      where: { isActive: true },
      include: {
        user: { select: { id: true, pushToken: true, email: true } },
        medication: { select: { name: true } },
      },
    });

    const triggered = [];

    for (const alert of activeAlerts) {
      const lowestPrice = await prisma.price.findFirst({
        where: {
          pharmacyProduct: {
            medicationId: alert.medicationId,
            isActive: true,
            ...(alert.pharmacyId ? { pharmacyId: alert.pharmacyId } : {}),
          },
        },
        orderBy: { price: 'asc' },
      });

      if (!lowestPrice) continue;
      if (lowestPrice.price <= alert.targetPrice) {
        triggered.push({
          alertId: alert.id,
          userId: alert.user.id,
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

    this.logger.log(
      `Price alert check: ${triggered.length} triggered out of ${activeAlerts.length}`,
    );
    return triggered;
  }

  private async sendNotification(alert: {
    pushToken: string | null;
    userEmail: string;
    medicationName: string;
    currentPrice: number;
    targetPrice: number;
  }) {
    // Expo Push Notification
    if (alert.pushToken) {
      try {
        await fetch('https://exp.host/--/api/v2/push/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            to: alert.pushToken,
            title: 'Alerta de precio',
            body: `${alert.medicationName} bajó a $${alert.currentPrice.toLocaleString('es-CL')} (meta: $${alert.targetPrice.toLocaleString('es-CL')})`,
            data: { type: 'price_alert' },
          }),
        });
      } catch (e) {
        this.logger.error(`Failed to send push to ${alert.pushToken}: ${e}`);
      }
    }
  }
}
