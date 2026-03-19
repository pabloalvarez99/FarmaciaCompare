import { Module } from '@nestjs/common';
import { DashboardController } from './inventory.controller';
import { InventoryService } from './inventory.service';
import { DashboardOrdersService } from './dashboard-orders.service';
import { AnalyticsService } from './analytics.service';

@Module({
  controllers: [DashboardController],
  providers: [InventoryService, DashboardOrdersService, AnalyticsService],
})
export class DashboardModule {}
