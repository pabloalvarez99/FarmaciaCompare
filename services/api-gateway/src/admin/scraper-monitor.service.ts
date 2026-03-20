import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class ScraperMonitorService {
  async getRecentJobs(limit = 100) {
    return prisma.scrapingJob.findMany({
      include: { pharmacy: { select: { name: true } } },
      orderBy: { createdAt: 'desc' },
      take: limit,
    });
  }

  async getStats() {
    const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const [total, completed, failed, running] = await Promise.all([
      prisma.scrapingJob.count({
        where: { createdAt: { gte: since24h } },
      }),
      prisma.scrapingJob.count({
        where: { status: 'completed', createdAt: { gte: since24h } },
      }),
      prisma.scrapingJob.count({
        where: { status: 'failed', createdAt: { gte: since24h } },
      }),
      prisma.scrapingJob.count({
        where: { status: 'running' },
      }),
    ]);
    return { total, completed, failed, running };
  }

  async getPriceUpdateCount() {
    const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return prisma.price.count({
      where: { recordedAt: { gte: since24h } },
    });
  }
}
