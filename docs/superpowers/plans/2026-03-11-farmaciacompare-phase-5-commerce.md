# FarmaciaCompare Phase 5 — Commerce Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement the full purchase flow — cart, order creation, WebPay Plus (Transbank) and MercadoPago payment integrations, delivery/pickup selection, and prescription upload.

**Architecture:** NestJS OrderService handles order lifecycle. Payments processed via official Transbank SDK and MercadoPago SDK. Prescriptions stored in AWS S3 (local MinIO in dev). Order status managed as a state machine.

**Tech Stack:** NestJS, `transbank-sdk` (Node.js), `mercadopago` npm package, MinIO (local S3 substitute), @aws-sdk/client-s3, Multer, BullMQ for async prescription review queues.

**Prerequisites:** Phase 1 + 4 complete (auth, medications, price data live).

---

## Chunk 1: Order Service

### Task 1: Order creation and management

**Files:**
- Create: `services/api-gateway/src/orders/orders.module.ts`
- Create: `services/api-gateway/src/orders/orders.service.ts`
- Create: `services/api-gateway/src/orders/orders.controller.ts`
- Create: `services/api-gateway/src/orders/dto/create-order.dto.ts`
- Create: `services/api-gateway/src/orders/order-state-machine.ts`
- Create: `services/api-gateway/test/orders.e2e-spec.ts`

- [ ] **Step 1: Write failing e2e tests**

```typescript
// services/api-gateway/test/orders.e2e-spec.ts
describe('Orders (e2e)', () => {
  it('POST /orders should create a pickup order', async () => {
    const res = await request(app.getHttpServer())
      .post('/api/v1/orders')
      .set('Authorization', `Bearer ${userToken}`)
      .send({
        pharmacyId: testPharmacyId,
        type: 'pickup',
        items: [{ pharmacyProductId: testProductId, quantity: 1 }],
      });
    expect(res.status).toBe(201);
    expect(res.body.status).toBe('pending');
    expect(res.body.type).toBe('pickup');
  });

  it('should reject order with out-of-stock item', async () => {
    // Out-of-stock product test
    const res = await request(app.getHttpServer())
      .post('/api/v1/orders')
      .set('Authorization', `Bearer ${userToken}`)
      .send({
        pharmacyId: testPharmacyId,
        type: 'pickup',
        items: [{ pharmacyProductId: outOfStockProductId, quantity: 1 }],
      });
    expect(res.status).toBe(400);
  });
});
```

- [ ] **Step 2: Create `services/api-gateway/src/orders/order-state-machine.ts`**

```typescript
// Valid transitions
export const ORDER_TRANSITIONS: Record<string, string[]> = {
  pending:    ['confirmed', 'cancelled'],
  confirmed:  ['preparing', 'cancelled'],
  preparing:  ['ready'],          // pickup orders
  ready:      ['delivered'],      // pickup: customer picks up
  dispatched: ['delivered'],      // delivery orders
  delivered:  [],
  cancelled:  [],
};

export function canTransition(from: string, to: string): boolean {
  return ORDER_TRANSITIONS[from]?.includes(to) ?? false;
}
```

- [ ] **Step 3: Create `services/api-gateway/src/orders/dto/create-order.dto.ts`**

```typescript
import { IsUUID, IsEnum, IsArray, ValidateNested, IsInt, Min, IsOptional, IsString } from 'class-validator';
import { Type } from 'class-transformer';

class OrderItemDto {
  @IsUUID() pharmacyProductId: string;
  @IsInt() @Min(1) quantity: number;
}

export class CreateOrderDto {
  @IsUUID() pharmacyId: string;
  @IsEnum(['delivery', 'pickup']) type: 'delivery' | 'pickup';

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => OrderItemDto)
  items: OrderItemDto[];

  @IsOptional() @IsString() deliveryAddress?: string;
  @IsOptional() @IsString() notes?: string;
}
```

- [ ] **Step 4: Implement `services/api-gateway/src/orders/orders.service.ts`**

```typescript
import { Injectable, BadRequestException, NotFoundException } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { CreateOrderDto } from './dto/create-order.dto';
import { canTransition } from './order-state-machine';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class OrdersService {
  async create(userId: string, dto: CreateOrderDto) {
    // Validate pharmacy exists
    const pharmacy = await prisma.pharmacy.findUniqueOrThrow({ where: { id: dto.pharmacyId } });

    // Validate all products belong to pharmacy and are in stock
    const productIds = dto.items.map((i) => i.pharmacyProductId);
    const products = await prisma.pharmacyProduct.findMany({
      where: { id: { in: productIds }, pharmacyId: dto.pharmacyId },
      include: { prices: { orderBy: { recordedAt: 'desc' }, take: 1 } },
    });

    if (products.length !== dto.items.length) {
      throw new BadRequestException('One or more products not found in this pharmacy');
    }

    const outOfStock = products.find((p) => p.prices[0]?.stockStatus === 'out_of_stock');
    if (outOfStock) {
      throw new BadRequestException(`Product ${outOfStock.rawName} is out of stock`);
    }

    // Calculate totals
    const items = dto.items.map((item) => {
      const product = products.find((p) => p.id === item.pharmacyProductId)!;
      const unitPrice = product.prices[0]?.price ?? 0;
      return { ...item, unitPrice, subtotal: unitPrice * item.quantity, medicationId: product.medicationId };
    });

    const subtotal = items.reduce((sum, i) => sum + i.subtotal, 0);
    const deliveryFee = dto.type === 'delivery' ? 2990 : 0; // Base delivery fee CLP
    const total = subtotal + deliveryFee;

    // Create order
    const order = await prisma.order.create({
      data: {
        id: uuidv4(),
        userId,
        pharmacyId: dto.pharmacyId,
        type: dto.type,
        status: 'pending',
        subtotal,
        deliveryFee,
        total,
        deliveryAddress: dto.deliveryAddress,
        notes: dto.notes,
        items: {
          create: items.map((item) => ({
            id: uuidv4(),
            pharmacyProductId: item.pharmacyProductId,
            medicationId: item.medicationId,
            quantity: item.quantity,
            unitPrice: item.unitPrice,
            subtotal: item.subtotal,
          })),
        },
      },
      include: { items: true, pharmacy: { select: { name: true } } },
    });

    return order;
  }

  async findAllForUser(userId: string) {
    return prisma.order.findMany({
      where: { userId },
      include: { pharmacy: { select: { name: true, chain: true } }, items: true },
      orderBy: { createdAt: 'desc' },
    });
  }

  async findById(id: string, userId: string) {
    const order = await prisma.order.findFirstOrThrow({
      where: { id, userId },
      include: { pharmacy: true, items: { include: { medication: true } } },
    });
    return order;
  }

  async cancel(id: string, userId: string) {
    const order = await prisma.order.findFirstOrThrow({ where: { id, userId } });
    if (!canTransition(order.status, 'cancelled')) {
      throw new BadRequestException(`Cannot cancel order in status: ${order.status}`);
    }
    return prisma.order.update({ where: { id }, data: { status: 'cancelled' } });
  }
}
```

- [ ] **Step 5: Add GET/POST routes, wire module, run tests**

```bash
cd services/api-gateway && pnpm test:e2e -- --testPathPattern=orders
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
git add services/api-gateway/src/orders/ services/api-gateway/test/
git commit -m "feat: implement order creation with validation and state machine"
```

---

## Chunk 2: WebPay Plus Integration

### Task 2: Transbank WebPay Plus payment flow

**Files:**
- Create: `services/api-gateway/src/payments/payments.module.ts`
- Create: `services/api-gateway/src/payments/payments.service.ts`
- Create: `services/api-gateway/src/payments/webpay.service.ts`
- Create: `services/api-gateway/src/payments/payments.controller.ts`

- [ ] **Step 1: Install Transbank SDK**

```bash
cd services/api-gateway && pnpm add transbank-sdk
```

- [ ] **Step 2: Create `services/api-gateway/src/payments/webpay.service.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { WebpayPlus, Environment, Options } from 'transbank-sdk';

@Injectable()
export class WebpayService {
  private tx: WebpayPlus.Transaction;

  constructor() {
    // Use integration credentials in dev, production credentials in prod
    const isProduction = process.env.NODE_ENV === 'production';
    this.tx = isProduction
      ? new WebpayPlus.Transaction(
          new Options(
            process.env.WEBPAY_COMMERCE_CODE!,
            process.env.WEBPAY_API_KEY!,
            Environment.Production,
          ),
        )
      : new WebpayPlus.Transaction(); // Uses integration defaults
  }

  async initTransaction(orderId: string, amount: number, returnUrl: string) {
    const response = await this.tx.create(
      orderId,          // buyOrder (our orderId)
      orderId,          // sessionId
      amount,
      returnUrl,
    );
    return {
      token: response.token,
      url: response.url,
    };
  }

  async confirmTransaction(token: string) {
    const response = await this.tx.commit(token);
    return {
      authCode: response.authorization_code,
      cardLast4: response.card_detail?.card_number?.slice(-4),
      status: response.status,
      responseCode: response.response_code,
      amount: response.amount,
      buyOrder: response.buy_order,
    };
  }
}
```

- [ ] **Step 3: Create `services/api-gateway/src/payments/payments.controller.ts`**

```typescript
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

  // WebPay redirects here after payment — no auth required (token in query)
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
```

- [ ] **Step 4: Implement `payments.service.ts`** with order lookup, payment init, and status update logic (follows the pattern of WebpayService above — validate user owns order, call WebpayService, update order paymentStatus + paymentToken).

- [ ] **Step 5: Add MercadoPago integration**

```bash
pnpm add mercadopago
```

MP flow: create a Preference → return `init_point` URL → handle IPN webhook → verify payment → update order.

- [ ] **Step 6: Commit**

```bash
git add services/api-gateway/src/payments/
git commit -m "feat: implement WebPay Plus and MercadoPago payment integrations"
```

---

## Chunk 3: Prescription Upload

### Task 3: Prescription file upload to S3/MinIO

**Files:**
- Create: `services/api-gateway/src/prescriptions/prescriptions.module.ts`
- Create: `services/api-gateway/src/prescriptions/prescriptions.service.ts`
- Create: `services/api-gateway/src/prescriptions/prescriptions.controller.ts`
- Modify: `infra/docker/docker-compose.yml` (add MinIO service)

- [ ] **Step 1: Add MinIO to Docker Compose (local S3)**

```yaml
# Add to infra/docker/docker-compose.yml
  minio:
    image: minio/minio
    container_name: farmacia_minio
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
```

Add to `.env.example`:
```bash
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=farmacia-uploads
```

- [ ] **Step 2: Install AWS SDK**

```bash
pnpm add @aws-sdk/client-s3 @aws-sdk/s3-request-presigner multer @types/multer
```

- [ ] **Step 3: Implement `prescriptions.service.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { prisma } from '@farmacia/database';
import { v4 as uuidv4 } from 'uuid';
import * as path from 'path';

@Injectable()
export class PrescriptionsService {
  private s3 = new S3Client({
    region: process.env.AWS_REGION ?? 'us-east-1',
    endpoint: process.env.S3_ENDPOINT,
    forcePathStyle: true, // Required for MinIO
    credentials: {
      accessKeyId: process.env.S3_ACCESS_KEY ?? '',
      secretAccessKey: process.env.S3_SECRET_KEY ?? '',
    },
  });

  async upload(userId: string, file: Express.Multer.File, orderId?: string) {
    const ext = path.extname(file.originalname);
    const key = `prescriptions/${userId}/${uuidv4()}${ext}`;

    await this.s3.send(
      new PutObjectCommand({
        Bucket: process.env.S3_BUCKET ?? 'farmacia-uploads',
        Key: key,
        Body: file.buffer,
        ContentType: file.mimetype,
      }),
    );

    const fileUrl = `${process.env.S3_ENDPOINT}/${process.env.S3_BUCKET}/${key}`;

    const prescription = await prisma.prescription.create({
      data: {
        id: uuidv4(),
        userId,
        orderId: orderId ?? null,
        fileUrl,
        status: 'pending',
      },
    });

    return prescription;
  }

  async findAllForUser(userId: string) {
    return prisma.prescription.findMany({ where: { userId }, orderBy: { createdAt: 'desc' } });
  }
}
```

- [ ] **Step 4: Create controller with Multer upload interceptor**

```typescript
@Post()
@UseGuards(JwtAuthGuard)
@UseInterceptors(FileInterceptor('file', { limits: { fileSize: 10 * 1024 * 1024 } }))
async upload(
  @UploadedFile() file: Express.Multer.File,
  @CurrentUser() user: any,
  @Body('orderId') orderId?: string,
) {
  if (!file) throw new BadRequestException('No file uploaded');
  const allowed = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
  if (!allowed.includes(file.mimetype)) {
    throw new BadRequestException('Only JPEG, PNG, WebP, or PDF files allowed');
  }
  return this.prescriptionsService.upload(user.id, file, orderId);
}
```

- [ ] **Step 5: Commit**

```bash
git add services/api-gateway/src/prescriptions/ infra/docker/
git commit -m "feat: implement prescription upload to S3/MinIO with order linking"
```

---

## Phase 5 Complete

**What was built:**
- Order creation with product validation, stock check, and pricing
- Order state machine (pending → confirmed → preparing → delivered)
- WebPay Plus integration (Transbank Chile)
- MercadoPago integration
- Prescription upload to S3/MinIO
- MinIO in Docker Compose for local dev

**Next:** Phase 6 — Pharmacy SaaS Dashboard.
