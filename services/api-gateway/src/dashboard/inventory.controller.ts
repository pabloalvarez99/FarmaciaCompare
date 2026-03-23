import {
  Controller,
  Get,
  Post,
  Put,
  Body,
  Param,
  Query,
  Sse,
  UseGuards,
  DefaultValuePipe,
  ParseIntPipe,
} from '@nestjs/common';
import { Observable, interval, map, startWith } from 'rxjs';
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

  @Get('overview')
  async getOverview(@CurrentUser() user: any) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    const [products, pendingOrders, analytics] = await Promise.all([
      this.inventoryService.getProducts(pharmacyId, 1),
      this.ordersService.getPendingOrders(pharmacyId),
      this.analyticsService.getSalesAnalytics(pharmacyId, 30),
    ]);
    return {
      totalProducts: products.total ?? 0,
      pendingOrders: pendingOrders.length,
      revenue30d: analytics.totalRevenue ?? 0,
      orderCount30d: analytics.totalOrders ?? 0,
    };
  }

  @Get('settings')
  async getSettings(@CurrentUser() user: any) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.inventoryService.getPharmacySettings(pharmacyId);
  }

  @Put('settings')
  async updateSettings(
    @CurrentUser() user: any,
    @Body()
    data: {
      name?: string;
      address?: string;
      city?: string;
      phone?: string;
      email?: string;
      hasDelivery?: boolean;
      hasPickup?: boolean;
    },
  ) {
    const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
    return this.inventoryService.updatePharmacySettings(pharmacyId, data);
  }

  @Sse('orders/stream')
  orderStream(): Observable<MessageEvent> {
    return interval(10000).pipe(
      startWith(0),
      map(() => ({
        data: JSON.stringify({ type: 'heartbeat', timestamp: new Date().toISOString() }),
      } as MessageEvent)),
    );
  }
}
