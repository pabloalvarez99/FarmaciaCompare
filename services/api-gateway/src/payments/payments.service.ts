import { Injectable, BadRequestException } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { WebpayService } from './webpay.service';
import { MercadoPagoService } from './mercadopago.service';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class PaymentsService {
  constructor(
    private readonly webpayService: WebpayService,
    private readonly mercadoPagoService: MercadoPagoService,
    private readonly configService: ConfigService,
  ) {}

  async initWebpay(orderId: string, userId: string) {
    const order = await prisma.order.findFirstOrThrow({ where: { id: orderId, userId } });
    if (order.status !== 'pending') {
      throw new BadRequestException('Order is not pending');
    }

    const apiUrl = this.configService.get('API_URL', 'http://localhost:4000');
    const returnUrl = `${apiUrl}/api/v1/payments/webpay/confirm`;
    const result = await this.webpayService.initTransaction(orderId, order.total, returnUrl);

    await prisma.order.update({
      where: { id: orderId },
      data: { paymentMethod: 'webpay', paymentToken: result.token },
    });

    return result;
  }

  async confirmWebpay(token: string) {
    const result = await this.webpayService.confirmTransaction(token);

    if (result.responseCode === 0) {
      await prisma.order.update({
        where: { id: result.buyOrder },
        data: { status: 'confirmed', paymentStatus: 'paid' },
      });
      return { success: true, orderId: result.buyOrder };
    }

    await prisma.order.update({
      where: { id: result.buyOrder },
      data: { paymentStatus: 'failed' },
    });
    return { success: false, orderId: result.buyOrder };
  }

  async createMercadoPagoPreference(orderId: string, userId: string) {
    const order = await prisma.order.findFirstOrThrow({
      where: { id: orderId, userId },
      include: { pharmacy: { select: { name: true } } },
    });

    if (order.status !== 'pending') {
      throw new BadRequestException('Order is not pending');
    }

    const description = `Pedido FarmaciaCompare - ${order.pharmacy.name}`;
    const result = await this.mercadoPagoService.createPreference(orderId, order.total, description);

    await prisma.order.update({
      where: { id: orderId },
      data: { paymentMethod: 'mercadopago' },
    });

    return result;
  }

  async handleMercadoPagoWebhook(payload: any) {
    if (payload.type === 'payment') {
      const payment = await this.mercadoPagoService.getPayment(payload.data.id);
      const orderId = payment.external_reference;

      if (payment.status === 'approved') {
        await prisma.order.update({
          where: { id: orderId },
          data: { status: 'confirmed', paymentStatus: 'paid' },
        });
      }
    }
    return { received: true };
  }
}
