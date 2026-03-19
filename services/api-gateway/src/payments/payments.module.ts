import { Module } from '@nestjs/common';
import { PaymentsController } from './payments.controller';
import { PaymentsService } from './payments.service';
import { WebpayService } from './webpay.service';
import { MercadoPagoService } from './mercadopago.service';

@Module({
  controllers: [PaymentsController],
  providers: [PaymentsService, WebpayService, MercadoPagoService],
  exports: [PaymentsService],
})
export class PaymentsModule {}
