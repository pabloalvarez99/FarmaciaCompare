import { Controller, Post, Body, Query, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { PaymentsService } from './payments.service';
import { CurrentUser } from '../auth/decorators/current-user.decorator';

@Controller('payments')
export class PaymentsController {
  constructor(private readonly paymentsService: PaymentsService) {}

  @Post('webpay/init')
  @UseGuards(JwtAuthGuard)
  async initWebpay(
    @Body('orderId') orderId: string,
    @CurrentUser() user: any,
  ) {
    return this.paymentsService.initWebpay(orderId, user.id);
  }

  @Post('webpay/confirm')
  async confirmWebpay(@Query('token_ws') token: string) {
    return this.paymentsService.confirmWebpay(token);
  }

  @Post('mercadopago/create')
  @UseGuards(JwtAuthGuard)
  async createMercadoPago(
    @Body('orderId') orderId: string,
    @CurrentUser() user: any,
  ) {
    return this.paymentsService.createMercadoPagoPreference(orderId, user.id);
  }

  @Post('mercadopago/webhook')
  async mercadoPagoWebhook(@Body() payload: any) {
    return this.paymentsService.handleMercadoPagoWebhook(payload);
  }
}
