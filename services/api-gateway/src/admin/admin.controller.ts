import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
  UseGuards,
  DefaultValuePipe,
  ParseIntPipe,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { Roles } from '../auth/decorators/roles.decorator';
import { RolesGuard } from '../auth/guards/roles.guard';
import { CatalogService } from './catalog.service';
import { ScraperMonitorService } from './scraper-monitor.service';
import { AnomalyDetectorService } from './anomaly-detector.service';
import { PharmacyAdminService } from './pharmacy-admin.service';

@Controller('admin')
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles('admin')
export class AdminController {
  constructor(
    private readonly catalogService: CatalogService,
    private readonly scraperService: ScraperMonitorService,
    private readonly anomalyService: AnomalyDetectorService,
    private readonly pharmacyService: PharmacyAdminService,
  ) {}

  @Get('catalog')
  searchCatalog(
    @Query('q') q = '',
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
  ) {
    return this.catalogService.searchMedications(q, page);
  }

  @Get('catalog/unmatched')
  getUnmatched(
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
  ) {
    return this.catalogService.getUnmatchedProducts(page);
  }

  @Post('catalog/link')
  linkProduct(@Body() data: { productId: string; medicationId: string }) {
    return this.catalogService.linkProduct(data.productId, data.medicationId);
  }

  @Post('catalog/merge')
  mergeMedications(@Body() data: { sourceId: string; targetId: string }) {
    return this.catalogService.mergeMedications(data.sourceId, data.targetId);
  }

  @Get('scrapers/jobs')
  getScraperJobs() {
    return this.scraperService.getRecentJobs();
  }

  @Get('scrapers/stats')
  getScraperStats() {
    return this.scraperService.getStats();
  }

  @Get('anomalies')
  getAnomalies() {
    return this.anomalyService.detectPriceAnomalies();
  }

  @Get('pharmacies')
  listPharmacies(
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
  ) {
    return this.pharmacyService.listPharmacies(page);
  }

  @Post('pharmacies')
  createPharmacy(
    @Body() data: { name: string; chain?: string; type: string; address?: string },
  ) {
    return this.pharmacyService.createPharmacy(data);
  }

  @Post('pharmacies/:id/staff')
  addStaff(
    @Param('id') pharmacyId: string,
    @Body() data: { userId: string; role?: string },
  ) {
    return this.pharmacyService.addStaff(pharmacyId, data.userId, data.role);
  }
}
