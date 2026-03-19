import {
  Controller,
  Get,
  Post,
  Put,
  Body,
  Param,
  Query,
  UseGuards,
  DefaultValuePipe,
  ParseIntPipe,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import { InventoryService } from './inventory.service';
import { DashboardOrdersService } from './dashboard-orders.service';
import { AnalyticsService } from './analytics.service';

@Controller('dashboard')
@UseGuards(JwtAuthGuard)
export class DashboardController {
  constructor(
    private readonly inventoryService: InventoryService,
    private readonly ordersService: DashboardOrdersService,
    private readonly analyticsService: AnalyticsService,
  ) {}

  @Get('products')
  async getProducts(
    @CurrentUser() user: any,
    @Query('page', new DefaultValuePipe(1), ParseIntPipe) page: number,
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.inventoryService.getProducts(pharmacyId, page);
  }

  @Post('products')
  async createProduct(
    @CurrentUser() user: any,
    @Body() data: { sku: string; rawName: string; brand?: string },
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.inventoryService.upsertProduct(pharmacyId, data);
  }

  @Put('products/:id/price')
  async updatePrice(
    @CurrentUser() user: any,
    @Param('id') productId: string,
    @Body() data: { price: number; stockStatus?: string },
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.inventoryService.updatePrice(
      pharmacyId,
      productId,
      data.price,
      data.stockStatus,
    );
  }

  @Get('orders')
  async getOrders(@CurrentUser() user: any) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.ordersService.getPendingOrders(pharmacyId);
  }

  @Put('orders/:id/status')
  async updateOrderStatus(
    @CurrentUser() user: any,
    @Param('id') orderId: string,
    @Body('status') status: string,
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.ordersService.updateOrderStatus(pharmacyId, orderId, status);
  }

  @Get('analytics')
  async getAnalytics(
    @CurrentUser() user: any,
    @Query('days', new DefaultValuePipe(30), ParseIntPipe) days: number,
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.analyticsService.getSalesAnalytics(pharmacyId, days);
  }
}
