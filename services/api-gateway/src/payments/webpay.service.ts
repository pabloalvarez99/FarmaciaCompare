import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

// Transbank WebPay Plus integration
// Uses transbank-sdk when available, falls back to HTTP calls
@Injectable()
export class WebpayService {
  private readonly logger = new Logger(WebpayService.name);
  private readonly isProduction: boolean;
  private readonly commerceCode: string;
  private readonly apiKey: string;

  constructor(private configService: ConfigService) {
    this.isProduction = configService.get('NODE_ENV') === 'production';
    this.commerceCode = configService.get('WEBPAY_COMMERCE_CODE', '597055555532');
    this.apiKey = configService.get(
      'WEBPAY_API_KEY',
      '579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C',
    );
  }

  private get baseUrl(): string {
    return this.isProduction
      ? 'https://webpay3g.transbank.cl'
      : 'https://webpay3gint.transbank.cl';
  }

  async initTransaction(orderId: string, amount: number, returnUrl: string) {
    const response = await fetch(`${this.baseUrl}/rswebpaytransaction/api/webpay/v1.2/transactions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Tbk-Api-Key-Id': this.commerceCode,
        'Tbk-Api-Key-Secret': this.apiKey,
      },
      body: JSON.stringify({
        buy_order: orderId,
        session_id: orderId,
        amount,
        return_url: returnUrl,
      }),
    });

    if (!response.ok) {
      this.logger.error(`WebPay init failed: ${response.status}`);
      throw new Error('WebPay transaction init failed');
    }

    const data = await response.json() as Record<string, any>;
    return { token: data.token as string, url: data.url as string };
  }

  async confirmTransaction(token: string) {
    const response = await fetch(`${this.baseUrl}/rswebpaytransaction/api/webpay/v1.2/transactions/${token}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Tbk-Api-Key-Id': this.commerceCode,
        'Tbk-Api-Key-Secret': this.apiKey,
      },
    });

    if (!response.ok) {
      this.logger.error(`WebPay confirm failed: ${response.status}`);
      throw new Error('WebPay transaction confirm failed');
    }

    const data = await response.json() as Record<string, any>;
    return {
      authCode: data.authorization_code as string,
      cardLast4: (data.card_detail as Record<string, any>)?.card_number?.slice(-4) as string | undefined,
      status: data.status as string,
      responseCode: data.response_code as number,
      amount: data.amount as number,
      buyOrder: data.buy_order as string,
    };
  }
}
