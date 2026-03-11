# FarmaciaCompare Phase 7 — Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build the internal admin panel for FarmaciaCompare staff — catalog management, scraper job monitoring, pharmacy onboarding, price anomaly detection, and fraud detection.

**Architecture:** Third Next.js app (`apps/admin`). Protected by `admin` role. Price anomaly detection runs as a NestJS scheduled task (cron). Scraper status pulled from `scraping_jobs` table.

**Tech Stack:** Next.js 14, Shadcn/UI, @tanstack/react-table, Recharts, NestJS @nestjs/schedule.

**Prerequisites:** Phases 1–6 complete.

---

## Chunk 1: Admin App Scaffold

### Task 1: Create admin app with auth guard

- [ ] **Step 1: Create Next.js admin app**

```bash
cd apps
npx create-next-app@latest admin --typescript --tailwind --eslint --app --src-dir --import-alias "@/*" --no-git
cd admin
npx shadcn@latest init
npx shadcn@latest add button input badge card table tabs dialog alert
pnpm add @tanstack/react-table @tanstack/react-query recharts lucide-react
```

- [ ] **Step 2: Add admin middleware guard**

```typescript
// apps/admin/src/middleware.ts
import { NextRequest, NextResponse } from 'next/server';

export function middleware(req: NextRequest) {
  const token = req.cookies.get('adminToken');
  if (!token && !req.nextUrl.pathname.startsWith('/login')) {
    return NextResponse.redirect(new URL('/login', req.url));
  }
  return NextResponse.next();
}

export const config = { matcher: ['/((?!_next|login|api).*)'] };
```

- [ ] **Step 3: Commit**

```bash
git add apps/admin/
git commit -m "chore: scaffold admin panel app"
```

---

## Chunk 2: Catalog Management

### Task 2: Medication catalog management

**Files:**
- Create: `services/api-gateway/src/admin/admin.module.ts`
- Create: `services/api-gateway/src/admin/catalog.service.ts`
- Create: `services/api-gateway/src/admin/catalog.controller.ts`
- Create: `apps/admin/src/app/(admin)/catalogo/page.tsx`
- Create: `apps/admin/src/app/(admin)/catalogo/[id]/page.tsx`

- [ ] **Step 1: Create `catalog.service.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class CatalogService {
  async searchMedications(query: string, page = 1, limit = 50) {
    const where = query
      ? {
          OR: [
            { name: { contains: query, mode: 'insensitive' as const } },
            { ispRegistration: { contains: query } },
            { activeIngredient: { name: { contains: query, mode: 'insensitive' as const } } },
          ],
        }
      : {};

    const [meds, total] = await Promise.all([
      prisma.medication.findMany({
        where,
        include: {
          activeIngredient: true,
          names: true,
          _count: { select: { pharmacyProducts: true } },
        },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { name: 'asc' },
      }),
      prisma.medication.count({ where }),
    ]);

    return { meds, total, page, totalPages: Math.ceil(total / limit) };
  }

  async getUnmatchedProducts(page = 1, limit = 50) {
    // Products scraped but not yet linked to a canonical medication
    return prisma.pharmacyProduct.findMany({
      where: { medicationId: null, isActive: true },
      include: { pharmacy: { select: { name: true, chain: true } } },
      skip: (page - 1) * limit,
      take: limit,
    });
  }

  async linkProduct(productId: string, medicationId: string) {
    return prisma.pharmacyProduct.update({
      where: { id: productId },
      data: { medicationId },
    });
  }

  async mergeMedications(sourceId: string, targetId: string) {
    // Reassign all pharmacyProducts, names, and priceAlerts from source to target
    await prisma.$transaction([
      prisma.pharmacyProduct.updateMany({ where: { medicationId: sourceId }, data: { medicationId: targetId } }),
      prisma.medicationName.updateMany({ where: { medicationId: sourceId }, data: { medicationId: targetId } }),
      prisma.priceAlert.updateMany({ where: { medicationId: sourceId }, data: { medicationId: targetId } }),
      prisma.medication.delete({ where: { id: sourceId } }),
    ]);
  }
}
```

- [ ] **Step 2: Build admin catalog pages**

`/catalogo` — searchable table of all medications with unmatched product count badge
`/catalogo/[id]` — medication detail with link/merge actions for unmatched products

- [ ] **Step 3: Commit**

```bash
git add services/api-gateway/src/admin/ apps/admin/
git commit -m "feat: implement admin catalog management with product linking and merging"
```

---

## Chunk 3: Scraper Monitoring

### Task 3: Scraper job dashboard

**Files:**
- Create: `services/api-gateway/src/admin/scraper-monitor.service.ts`
- Create: `apps/admin/src/app/(admin)/scrapers/page.tsx`

- [ ] **Step 1: Create `scraper-monitor.service.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { prisma } from '@farmacia/database';

@Injectable()
export class ScraperMonitorService {
  async getRecentJobs(limit = 100) {
    return prisma.scrapingJob.findMany({
      include: { pharmacy: { select: { name: true } } },
      orderBy: { createdAt: 'desc' },
      take: limit,
    });
  }

  async getStats() {
    const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const [total, completed, failed, running] = await Promise.all([
      prisma.scrapingJob.count({ where: { createdAt: { gte: since24h } } }),
      prisma.scrapingJob.count({ where: { status: 'completed', createdAt: { gte: since24h } } }),
      prisma.scrapingJob.count({ where: { status: 'failed', createdAt: { gte: since24h } } }),
      prisma.scrapingJob.count({ where: { status: 'running' } }),
    ]);

    const avgDuration = await prisma.$queryRaw<[{ avg: number }]>`
      SELECT EXTRACT(EPOCH FROM AVG(finished_at - started_at))::int AS avg
      FROM scraping_jobs
      WHERE status = 'completed'
        AND finished_at IS NOT NULL
        AND created_at >= ${since24h}
    `;

    return { total, completed, failed, running, avgDurationSeconds: avgDuration[0]?.avg ?? 0 };
  }

  async getPriceUpdateStats() {
    const since24h = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return prisma.price.count({ where: { recordedAt: { gte: since24h } } });
  }
}
```

- [ ] **Step 2: Build scraper monitoring page**

Show:
- KPI cards: jobs today, success rate, running now, prices updated in 24h
- Table: recent jobs with status badge, duration, items scraped, errors
- Auto-refresh every 30 seconds via `useQuery` with `refetchInterval: 30000`

- [ ] **Step 3: Commit**

```bash
git add services/api-gateway/src/admin/ apps/admin/
git commit -m "feat: implement scraper monitoring dashboard with job stats"
```

---

## Chunk 4: Price Anomaly Detection

### Task 4: Detect and alert on abnormal price changes

**Files:**
- Create: `services/api-gateway/src/admin/anomaly-detector.service.ts`
- Modify: `services/api-gateway/src/app.module.ts` (add ScheduleModule)

**Algorithm:** For each medication, calculate the 7-day rolling average price per pharmacy. Flag any new price that deviates by more than 50% from the rolling average.

- [ ] **Step 1: Install scheduler**

```bash
pnpm add @nestjs/schedule
```

- [ ] **Step 2: Implement `anomaly-detector.service.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { prisma } from '@farmacia/database';
import { Loguru as logger } from '@nestjs/common';

@Injectable()
export class AnomalyDetectorService {
  @Cron(CronExpression.EVERY_HOUR)
  async detectPriceAnomalies() {
    const threshold = 0.50; // 50% deviation triggers alert
    const lookbackDays = 7;
    const since = new Date();
    since.setDate(since.getDate() - lookbackDays);

    // Get pharmacy products with recent price history
    const products = await prisma.pharmacyProduct.findMany({
      where: { isActive: true, medicationId: { not: null } },
      include: {
        prices: {
          where: { recordedAt: { gte: since } },
          orderBy: { recordedAt: 'desc' },
        },
      },
    });

    const anomalies: Array<{
      productId: string;
      currentPrice: number;
      avgPrice: number;
      deviationPct: number;
    }> = [];

    for (const product of products) {
      if (product.prices.length < 3) continue; // Need enough history

      const latestPrice = product.prices[0].price;
      const historicalPrices = product.prices.slice(1).map((p) => p.price);
      const avg = historicalPrices.reduce((a, b) => a + b, 0) / historicalPrices.length;

      if (avg === 0) continue;
      const deviation = Math.abs(latestPrice - avg) / avg;

      if (deviation > threshold) {
        anomalies.push({
          productId: product.id,
          currentPrice: latestPrice,
          avgPrice: Math.round(avg),
          deviationPct: Math.round(deviation * 100),
        });
      }
    }

    if (anomalies.length > 0) {
      console.warn(`[AnomalyDetector] Found ${anomalies.length} price anomalies`);
      // TODO Phase 9: send to monitoring/alerting system
    }

    return anomalies;
  }
}
```

- [ ] **Step 3: Add anomalies endpoint and admin UI**

`GET /admin/anomalies` — returns current anomalies with medication name, pharmacy, current price vs average.

Admin page `/anomalias` — table with flag/dismiss actions.

- [ ] **Step 4: Commit**

```bash
git add services/api-gateway/src/admin/
git commit -m "feat: implement hourly price anomaly detection with 50% threshold"
```

---

## Chunk 5: Pharmacy Onboarding

### Task 5: Admin pharmacy management

**Files:**
- Create: `apps/admin/src/app/(admin)/farmacias/page.tsx`
- Create: `apps/admin/src/app/(admin)/farmacias/nueva/page.tsx`

- [ ] **Step 1: Create pharmacy management endpoints**

```typescript
// POST /admin/pharmacies — create pharmacy
// PUT  /admin/pharmacies/:id — update pharmacy details
// POST /admin/pharmacies/:id/activate-saas — activate SaaS plan
// POST /admin/pharmacies/:id/staff — add staff user
```

- [ ] **Step 2: Build pharmacy management pages**

`/farmacias` — table of all pharmacies with SaaS plan badge, active/inactive toggle
`/farmacias/nueva` — form to onboard a new pharmacy (name, chain, address, SaaS plan)

- [ ] **Step 3: Commit**

```bash
git add apps/admin/ services/api-gateway/src/admin/
git commit -m "feat: implement admin pharmacy onboarding and SaaS plan management"
```

---

## Phase 7 Complete

**What was built:**
- Admin panel (`apps/admin`) with auth guard
- Catalog management: search, link unmatched products, merge duplicate medications
- Scraper monitoring dashboard with job stats and auto-refresh
- Hourly price anomaly detection (50% deviation threshold)
- Pharmacy onboarding and SaaS plan management

**Next:** Phase 8 — Mobile App (React Native Expo).
