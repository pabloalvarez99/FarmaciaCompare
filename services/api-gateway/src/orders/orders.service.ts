import { Injectable, BadRequestException } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { CreateOrderDto } from './dto/create-order.dto';
import { canTransition } from './order-state-machine';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class OrdersService {
  async create(userId: string, dto: CreateOrderDto) {
    await prisma.pharmacy.findUniqueOrThrow({ where: { id: dto.pharmacyId } });
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
    const items = dto.items.map((item) => {
      const product = products.find((p) => p.id === item.pharmacyProductId)!;
      const unitPrice = product.prices[0]?.price ?? 0;
      return { ...item, unitPrice, subtotal: unitPrice * item.quantity, medicationId: product.medicationId };
    });
    const subtotal = items.reduce((sum, i) => sum + i.subtotal, 0);
    const deliveryFee = dto.type === 'delivery' ? 2990 : 0;
    const total = subtotal + deliveryFee;
    const order = await prisma.order.create({
      data: {
        id: uuidv4(), userId, pharmacyId: dto.pharmacyId, type: dto.type, status: 'pending',
        subtotal, deliveryFee, total, deliveryAddress: dto.deliveryAddress, notes: dto.notes,
        items: {
          create: items.map((item) => ({
            id: uuidv4(), pharmacyProductId: item.pharmacyProductId, medicationId: item.medicationId,
            quantity: item.quantity, unitPrice: item.unitPrice, subtotal: item.subtotal,
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
    return prisma.order.findFirstOrThrow({
      where: { id, userId },
      include: { pharmacy: true, items: { include: { medication: true } } },
    });
  }

  async cancel(id: string, userId: string) {
    const order = await prisma.order.findFirstOrThrow({ where: { id, userId } });
    if (!canTransition(order.status, 'cancelled')) {
      throw new BadRequestException(`Cannot cancel order in status: ${order.status}`);
    }
    return prisma.order.update({ where: { id }, data: { status: 'cancelled' } });
  }

  async updateStatus(id: string, newStatus: string) {
    const order = await prisma.order.findUniqueOrThrow({ where: { id } });
    if (!canTransition(order.status, newStatus)) {
      throw new BadRequestException(`Cannot transition from ${order.status} to ${newStatus}`);
    }
    return prisma.order.update({ where: { id }, data: { status: newStatus } });
  }
}
