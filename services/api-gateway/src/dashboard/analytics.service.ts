import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class AnalyticsService {
  async getSalesAnalytics(pharmacyId: string, days = 30) {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const orders = await prisma.order.findMany({
      where: {
        pharmacyId,
        status: {
          in: ['delivered', 'confirmed', 'preparing', 'ready'],
        },
        createdAt: { gte: since },
      },
      include: { items: true },
    });

    const totalRevenue = orders.reduce((sum, o) => sum + o.total, 0);
    const totalOrders = orders.length;
    const avgOrderValue =
      totalOrders > 0 ? Math.round(totalRevenue / totalOrders) : 0;

    const dailySales: Record<string, { revenue: number; orders: number }> = {};
    for (const order of orders) {
      const day = order.createdAt.toISOString().split('T')[0];
      dailySales[day] = dailySales[day] ?? { revenue: 0, orders: 0 };
      dailySales[day].revenue += order.total;
      dailySales[day].orders++;
    }

    return {
      totalRevenue,
      totalOrders,
      avgOrderValue,
      dailySales: Object.entries(dailySales)
        .map(([date, v]) => ({ date, ...v }))
        .sort((a, b) => a.date.localeCompare(b.date)),
    };
  }
}
