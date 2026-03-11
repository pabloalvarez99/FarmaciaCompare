# FarmaciaCompare Phase 6 — Pharmacy SaaS Dashboard

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build the pharmacy-facing SaaS dashboard — a separate Next.js app where pharmacies manage their inventory, update prices, handle orders, and view analytics. This is the primary B2B revenue product.

**Architecture:** Separate Next.js 14 app (`apps/dashboard`). Same API Gateway but hits pharmacy-scoped endpoints protected by `pharmacy_admin` role. Real-time order notifications via Server-Sent Events (SSE). Analytics via Prisma aggregations.

**Tech Stack:** Next.js 14 (App Router), Shadcn/UI, @tanstack/react-query, Recharts (analytics charts), react-hook-form, NestJS SSE for live order updates.

**Prerequisites:** Phases 1–5 complete.

---

## Chunk 1: Dashboard App Scaffold

### Task 1: Create pharmacy dashboard app

**Files:**
- Create: `apps/dashboard/` (Next.js 14)
- Create: `apps/dashboard/src/app/layout.tsx`
- Create: `apps/dashboard/src/app/(auth)/login/page.tsx`
- Create: `apps/dashboard/src/app/(dashboard)/layout.tsx`
- Create: `apps/dashboard/src/app/(dashboard)/page.tsx`
- Create: `apps/dashboard/src/components/Sidebar.tsx`

- [ ] **Step 1: Create Next.js dashboard app**

```bash
cd apps
npx create-next-app@latest dashboard --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-git
cd dashboard
npx shadcn@latest init
npx shadcn@latest add button input badge card skeleton dialog table tabs
pnpm add @tanstack/react-query recharts @tanstack/react-table lucide-react
```

- [ ] **Step 2: Create Sidebar navigation**

```tsx
// apps/dashboard/src/components/Sidebar.tsx
'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { LayoutDashboard, Package, Tag, ShoppingBag, BarChart3, Settings } from 'lucide-react';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Resumen', icon: LayoutDashboard },
  { href: '/dashboard/productos', label: 'Productos', icon: Package },
  { href: '/dashboard/precios', label: 'Precios', icon: Tag },
  { href: '/dashboard/pedidos', label: 'Pedidos', icon: ShoppingBag },
  { href: '/dashboard/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/dashboard/configuracion', label: 'Configuración', icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 border-r bg-white h-screen fixed left-0 top-0 flex flex-col">
      <div className="px-6 py-5 border-b">
        <h1 className="font-bold text-lg text-blue-600">FarmaciaCompare</h1>
        <p className="text-xs text-muted-foreground">Panel de Farmacia</p>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              pathname === href
                ? 'bg-blue-50 text-blue-700 font-medium'
                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 3: Create dashboard layout**

```tsx
// apps/dashboard/src/app/(dashboard)/layout.tsx
import { Sidebar } from '@/components/Sidebar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <main className="flex-1 ml-60 p-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/dashboard/
git commit -m "feat: scaffold pharmacy SaaS dashboard app with sidebar navigation"
```

---

## Chunk 2: Inventory Management

### Task 2: Product and price management

**Files:**
- Create: `services/api-gateway/src/dashboard/dashboard.module.ts`
- Create: `services/api-gateway/src/dashboard/inventory.service.ts`
- Create: `services/api-gateway/src/dashboard/inventory.controller.ts`
- Create: `apps/dashboard/src/app/(dashboard)/productos/page.tsx`
- Create: `apps/dashboard/src/app/(dashboard)/precios/page.tsx`

### Backend — Dashboard API Endpoints

- [ ] **Step 1: Create `services/api-gateway/src/dashboard/inventory.service.ts`**

```typescript
import { Injectable, ForbiddenException } from '@nestjs/common';
import { prisma } from '@farmacia/database';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class InventoryService {
  async getPharmacyForUser(userId: string): Promise<string> {
    const staff = await prisma.pharmacyStaff.findFirst({ where: { userId } });
    if (!staff) throw new ForbiddenException('Not a pharmacy staff member');
    return staff.pharmacyId;
  }

  async getProducts(pharmacyId: string, page = 1, limit = 50) {
    const [products, total] = await Promise.all([
      prisma.pharmacyProduct.findMany({
        where: { pharmacyId },
        include: {
          medication: { include: { activeIngredient: true } },
          prices: { orderBy: { recordedAt: 'desc' }, take: 1 },
        },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { rawName: 'asc' },
      }),
      prisma.pharmacyProduct.count({ where: { pharmacyId } }),
    ]);
    return { products, total, page, totalPages: Math.ceil(total / limit) };
  }

  async upsertProduct(pharmacyId: string, data: {
    sku: string; rawName: string; brand?: string; laboratory?: string; barcode?: string;
  }) {
    return prisma.pharmacyProduct.upsert({
      where: { pharmacyId_sku: { pharmacyId, sku: data.sku } },
      update: { rawName: data.rawName, brand: data.brand, laboratory: data.laboratory, barcode: data.barcode, isActive: true },
      create: { id: uuidv4(), pharmacyId, source: 'saas', isActive: true, ...data },
    });
  }

  async updatePrice(pharmacyId: string, productId: string, price: number, stockStatus = 'in_stock') {
    // Verify ownership
    await prisma.pharmacyProduct.findFirstOrThrow({ where: { id: productId, pharmacyId } });

    return prisma.price.create({
      data: {
        id: uuidv4(),
        pharmacyProductId: productId,
        price,
        stockStatus,
        source: 'saas',
      },
    });
  }

  async bulkImportCsv(pharmacyId: string, csvData: string) {
    // Parse CSV: sku,name,price,stock
    const lines = csvData.split('\n').slice(1); // skip header
    const results = { created: 0, updated: 0, errors: 0 };

    for (const line of lines) {
      const [sku, rawName, priceStr, stock] = line.split(',').map((s) => s.trim());
      if (!sku || !rawName) continue;
      try {
        await this.upsertProduct(pharmacyId, { sku, rawName });
        const product = await prisma.pharmacyProduct.findUniqueOrThrow({
          where: { pharmacyId_sku: { pharmacyId, sku } },
        });
        const price = parseInt(priceStr?.replace(/[^0-9]/g, '') ?? '0');
        if (price > 0) {
          await this.updatePrice(pharmacyId, product.id, price, stock || 'in_stock');
        }
        results.created++;
      } catch {
        results.errors++;
      }
    }
    return results;
  }
}
```

- [ ] **Step 2: Create controller with routes**

```typescript
// GET  /dashboard/products
// POST /dashboard/products
// PUT  /dashboard/products/:id/price
// POST /dashboard/products/bulk-import
// All routes: @UseGuards(JwtAuthGuard), @Roles('pharmacy_admin')
```

### Frontend — Products Page

- [ ] **Step 3: Create `apps/dashboard/src/app/(dashboard)/productos/page.tsx`**

Full product list with:
- Search/filter input
- DataTable (react-table) with columns: SKU, Name, Current Price, Stock, Linked Medication
- "Update Price" action button opening a Dialog
- "Bulk Import CSV" button

Key patterns:
```tsx
const { data, isLoading } = useQuery({
  queryKey: ['dashboard', 'products', page],
  queryFn: () => dashboardApiClient.get('/dashboard/products', { params: { page } }).then(r => r.data),
});
```

- [ ] **Step 4: Commit**

```bash
git add services/api-gateway/src/dashboard/ apps/dashboard/src/app/(dashboard)/productos/
git commit -m "feat: implement pharmacy inventory management with bulk CSV import"
```

---

## Chunk 3: Order Management + Live Updates

### Task 3: Pharmacy order queue with SSE

**Files:**
- Create: `services/api-gateway/src/dashboard/orders-sse.controller.ts`
- Create: `apps/dashboard/src/app/(dashboard)/pedidos/page.tsx`
- Create: `apps/dashboard/src/hooks/useOrderStream.ts`

- [ ] **Step 1: Create SSE endpoint for live orders**

```typescript
// services/api-gateway/src/dashboard/orders-sse.controller.ts
import { Controller, Sse, UseGuards } from '@nestjs/common';
import { Observable, interval, switchMap } from 'rxjs';
import { map } from 'rxjs/operators';
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import { InventoryService } from './inventory.service';
import { DashboardOrdersService } from './dashboard-orders.service';

@Controller('dashboard')
@UseGuards(JwtAuthGuard)
export class OrdersSseController {
  constructor(
    private readonly inventoryService: InventoryService,
    private readonly ordersService: DashboardOrdersService,
  ) {}

  @Sse('orders/stream')
  orderStream(@CurrentUser() user: any): Observable<MessageEvent> {
    // Poll DB every 5 seconds for new orders — simple and reliable
    return interval(5000).pipe(
      switchMap(async () => {
        const pharmacyId = await this.inventoryService.getPharmacyForUser(user.id);
        return this.ordersService.getPendingOrders(pharmacyId);
      }),
      map((orders) => ({ data: JSON.stringify(orders) } as MessageEvent)),
    );
  }
}
```

- [ ] **Step 2: Create `apps/dashboard/src/hooks/useOrderStream.ts`**

```typescript
'use client';
import { useEffect, useState } from 'react';

export function useOrderStream(token: string) {
  const [orders, setOrders] = useState<any[]>([]);

  useEffect(() => {
    const es = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL}/dashboard/orders/stream`,
      { withCredentials: true }
    );

    es.onmessage = (e) => {
      setOrders(JSON.parse(e.data));
    };

    return () => es.close();
  }, [token]);

  return orders;
}
```

- [ ] **Step 3: Commit**

```bash
git add services/api-gateway/src/dashboard/ apps/dashboard/
git commit -m "feat: implement order queue with SSE live updates for pharmacy dashboard"
```

---

## Chunk 4: Analytics Dashboard

### Task 4: Sales and views analytics

**Files:**
- Create: `services/api-gateway/src/dashboard/analytics.service.ts`
- Create: `apps/dashboard/src/app/(dashboard)/analytics/page.tsx`

- [ ] **Step 1: Create `analytics.service.ts`**

```typescript
async getSalesAnalytics(pharmacyId: string, days = 30) {
  const since = new Date();
  since.setDate(since.getDate() - days);

  const orders = await prisma.order.findMany({
    where: {
      pharmacyId,
      status: { in: ['delivered', 'confirmed', 'preparing', 'ready'] },
      createdAt: { gte: since },
    },
    include: { items: true },
  });

  const totalRevenue = orders.reduce((sum, o) => sum + o.total, 0);
  const totalOrders = orders.length;
  const avgOrderValue = totalOrders > 0 ? Math.round(totalRevenue / totalOrders) : 0;

  // Group by day
  const dailySales: Record<string, { revenue: number; orders: number }> = {};
  for (const order of orders) {
    const day = order.createdAt.toISOString().split('T')[0];
    dailySales[day] = dailySales[day] ?? { revenue: 0, orders: 0 };
    dailySales[day].revenue += order.total;
    dailySales[day].orders++;
  }

  // Top selling products
  const productCounts: Record<string, { name: string; quantity: number; revenue: number }> = {};
  for (const order of orders) {
    for (const item of order.items) {
      const id = item.pharmacyProductId;
      productCounts[id] = productCounts[id] ?? { name: item.pharmacyProductId, quantity: 0, revenue: 0 };
      productCounts[id].quantity += item.quantity;
      productCounts[id].revenue += item.subtotal;
    }
  }

  return {
    totalRevenue,
    totalOrders,
    avgOrderValue,
    dailySales: Object.entries(dailySales).map(([date, v]) => ({ date, ...v })).sort((a, b) => a.date.localeCompare(b.date)),
    topProducts: Object.values(productCounts).sort((a, b) => b.revenue - a.revenue).slice(0, 10),
  };
}
```

- [ ] **Step 2: Build analytics page with Recharts**

Key charts:
- `<LineChart>` for daily revenue (last 30 days)
- `<BarChart>` for top products by revenue
- KPI cards: total revenue, total orders, average order value

- [ ] **Step 3: Commit**

```bash
git add services/api-gateway/src/dashboard/ apps/dashboard/
git commit -m "feat: implement analytics dashboard with revenue charts and KPIs"
```

---

## Phase 6 Complete

**What was built:**
- Pharmacy SaaS dashboard (`apps/dashboard`) with Sidebar navigation
- Inventory management with bulk CSV import
- Price update flow (pharmacy pushes prices → creates price record)
- Live order queue via SSE
- Analytics with daily revenue + top products charts

**Next:** Phase 7 — Admin Panel (catalog management, scraper monitoring, fraud detection).
