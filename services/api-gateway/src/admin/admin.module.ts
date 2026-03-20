import { Module } from '@nestjs/common';
import { AdminController } from './admin.controller';
import { CatalogService } from './catalog.service';
import { ScraperMonitorService } from './scraper-monitor.service';
import { AnomalyDetectorService } from './anomaly-detector.service';
import { PharmacyAdminService } from './pharmacy-admin.service';

@Module({
  controllers: [AdminController],
  providers: [
    CatalogService,
    ScraperMonitorService,
    AnomalyDetectorService,
    PharmacyAdminService,
  ],
})
export class AdminModule {}
