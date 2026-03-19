import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class MercadoPagoService {
  private readonly logger = new Logger(MercadoPagoService.name);
  private readonly accessToken: string;

  constructor(private configService: ConfigService) {
    this.accessToken = configService.get('MERCADOPAGO_ACCESS_TOKEN', 'TEST-TOKEN');
  }

  async createPreference(orderId: string, amount: number, description: string) {
    const frontendUrl = this.configService.get('FRONTEND_URL', 'http://localhost:3000');
    const apiUrl = this.configService.get('API_URL', 'http://localhost:4000');

    const response = await fetch('https://api.mercadopago.com/checkout/preferences', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.accessToken}`,
      },
      body: JSON.stringify({
        items: [{
          id: orderId,
          title: description,
          quantity: 1,
          unit_price: amount,
          currency_id: 'CLP',
        }],
        external_reference: orderId,
        back_urls: {
          success: `${frontendUrl}/pedidos/${orderId}?status=success`,
          failure: `${frontendUrl}/pedidos/${orderId}?status=failure`,
          pending: `${frontendUrl}/pedidos/${orderId}?status=pending`,
        },
        notification_url: `${apiUrl}/api/v1/payments/mercadopago/webhook`,
        auto_return: 'approved',
      }),
    });

    if (!response.ok) {
      this.logger.error(`MercadoPago preference failed: ${response.status}`);
      throw new Error('MercadoPago preference creation failed');
    }

    const data = await response.json();
    return { preferenceId: data.id, initPoint: data.init_point };
  }

  async getPayment(paymentId: string) {
    const response = await fetch(`https://api.mercadopago.com/v1/payments/${paymentId}`, {
      headers: { Authorization: `Bearer ${this.accessToken}` },
    });

    if (!response.ok) {
      throw new Error('MercadoPago payment lookup failed');
    }

    return response.json();
  }
}
