# FarmaciaCompare Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the full monorepo, stand up all services with Docker Compose, implement auth (register/login/JWT/Google OAuth), and wire the database schema — giving every subsequent phase a working foundation to build on.

**Architecture:** Turborepo monorepo with pnpm workspaces. Three Next.js apps (web, dashboard, admin), one NestJS API gateway, shared Prisma schema, Docker Compose for local dev. Services communicate via HTTP. Redis for session tokens. No Elasticsearch yet (added in Phase 4).

**Tech Stack:** Node.js 20, pnpm 9, Turborepo 2, Next.js 14 (App Router), NestJS 10, Prisma 5, PostgreSQL 16, Redis 7, Docker Compose, TypeScript 5, Zod, NextAuth.js 5, bcryptjs, @nestjs/jwt.

**Prerequisites:** Docker Desktop installed, Node.js 20+ installed, pnpm installed (`npm i -g pnpm`).

---

## Chunk 1: Monorepo Scaffold

### Task 1: Initialize the monorepo

**Files:**
- Create: `package.json` (root)
- Create: `pnpm-workspace.yaml`
- Create: `turbo.json`
- Create: `.gitignore`
- Create: `.nvmrc`
- Create: `.env.example`

- [ ] **Step 1: Create the root directory and initialize git**

```bash
cd ~/Documents/Projects
mkdir farmacia-compare && cd farmacia-compare
git init
echo "20" > .nvmrc
```

- [ ] **Step 2: Create root `package.json`**

```json
{
  "name": "farmacia-compare",
  "private": true,
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "test": "turbo test",
    "lint": "turbo lint",
    "db:generate": "turbo db:generate",
    "db:push": "turbo db:push",
    "db:migrate": "turbo db:migrate"
  },
  "devDependencies": {
    "turbo": "^2.0.0",
    "typescript": "^5.4.0",
    "@types/node": "^20.0.0"
  },
  "engines": {
    "node": ">=20",
    "pnpm": ">=9"
  },
  "packageManager": "pnpm@9.0.0"
}
```

- [ ] **Step 3: Create `pnpm-workspace.yaml`**

```yaml
packages:
  - "apps/*"
  - "services/*"
  - "packages/*"
  - "mobile/*"
```

- [ ] **Step 4: Create `turbo.json`**

```json
{
  "$schema": "https://turbo.build/schema.json",
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "!.next/cache/**", "dist/**"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "test": {
      "dependsOn": ["^build"]
    },
    "lint": {},
    "db:generate": { "cache": false },
    "db:push": { "cache": false },
    "db:migrate": { "cache": false }
  }
}
```

- [ ] **Step 5: Create `.gitignore`**

```gitignore
# Dependencies
node_modules/
.pnp
.pnp.js

# Build outputs
.next/
dist/
build/
*.tsbuildinfo

# Environment
.env
.env.local
.env.*.local
!.env.example

# Logs
*.log
npm-debug.log*

# OS
.DS_Store
Thumbs.db

# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/

# Docker
*.env.docker

# Turbo
.turbo/

# IDE
.idea/
.vscode/settings.json
```

- [ ] **Step 6: Create `.env.example`**

```bash
# Database
DATABASE_URL=postgresql://farmacia:farmacia@localhost:5432/farmaciacompare

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=change-me-in-production-use-256-bit-random-string
JWT_REFRESH_SECRET=change-me-refresh-use-different-256-bit-string
JWT_EXPIRES_IN=15m
JWT_REFRESH_EXPIRES_IN=7d

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# App URLs
NEXT_PUBLIC_APP_URL=http://localhost:3000
NEXT_PUBLIC_DASHBOARD_URL=http://localhost:3001
NEXT_PUBLIC_ADMIN_URL=http://localhost:3002
NEXT_PUBLIC_API_URL=http://localhost:4000
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=change-me-nextauth-secret

# API Gateway
API_GATEWAY_PORT=4000

# AWS (leave empty for local dev)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=farmacia-compare-uploads
```

- [ ] **Step 7: Install root dependencies**

```bash
pnpm install
```

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "chore: initialize turborepo monorepo scaffold"
```

---

### Task 2: Create shared TypeScript config package

**Files:**
- Create: `packages/config/package.json`
- Create: `packages/config/tsconfig.base.json`
- Create: `packages/config/tsconfig.nextjs.json`
- Create: `packages/config/tsconfig.nestjs.json`

- [ ] **Step 1: Create the package**

```bash
mkdir -p packages/config
```

- [ ] **Step 2: Create `packages/config/package.json`**

```json
{
  "name": "@farmacia/config",
  "version": "0.0.1",
  "private": true,
  "files": ["tsconfig.base.json", "tsconfig.nextjs.json", "tsconfig.nestjs.json"]
}
```

- [ ] **Step 3: Create `packages/config/tsconfig.base.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  }
}
```

- [ ] **Step 4: Create `packages/config/tsconfig.nextjs.json`**

```json
{
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "target": "ES2017",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["dom", "dom.iterable", "ESNext"],
    "jsx": "preserve",
    "noEmit": true,
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

- [ ] **Step 5: Create `packages/config/tsconfig.nestjs.json`**

```json
{
  "extends": "./tsconfig.base.json",
  "compilerOptions": {
    "module": "CommonJS",
    "moduleResolution": "Node",
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "outDir": "./dist",
    "rootDir": "./src"
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add packages/
git commit -m "chore: add shared TypeScript config package"
```

---

### Task 3: Create shared types package

**Files:**
- Create: `packages/shared-types/package.json`
- Create: `packages/shared-types/tsconfig.json`
- Create: `packages/shared-types/src/index.ts`
- Create: `packages/shared-types/src/medication.ts`
- Create: `packages/shared-types/src/pharmacy.ts`
- Create: `packages/shared-types/src/user.ts`
- Create: `packages/shared-types/src/order.ts`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p packages/shared-types/src
```

- [ ] **Step 2: Create `packages/shared-types/package.json`**

```json
{
  "name": "@farmacia/shared-types",
  "version": "0.0.1",
  "private": true,
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "scripts": {
    "build": "tsc",
    "dev": "tsc --watch"
  },
  "devDependencies": {
    "@farmacia/config": "workspace:*",
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 3: Create `packages/shared-types/tsconfig.json`**

```json
{
  "extends": "@farmacia/config/tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 4: Create `packages/shared-types/src/user.ts`**

```typescript
export type UserRole = 'user' | 'pharmacy_admin' | 'admin';

export interface User {
  id: string;
  email: string;
  name: string | null;
  phone: string | null;
  avatarUrl: string | null;
  role: UserRole;
  emailVerified: boolean;
  createdAt: Date;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}
```

- [ ] **Step 5: Create `packages/shared-types/src/medication.ts`**

```typescript
export type PharmaceuticalForm =
  | 'comprimido'
  | 'capsula'
  | 'jarabe'
  | 'solucion'
  | 'inyectable'
  | 'crema'
  | 'gel'
  | 'colirio'
  | 'supositorio'
  | 'parche'
  | 'otro';

export interface ActiveIngredient {
  id: string;
  name: string;
  atcCode: string | null;
}

export interface Medication {
  id: string;
  name: string;
  activeIngredient: ActiveIngredient;
  dosage: string;
  pharmaceuticalForm: PharmaceuticalForm;
  prescriptionRequired: boolean;
  ispRegistration: string | null;
}

export interface MedicationPrice {
  pharmacyId: string;
  pharmacyName: string;
  pharmacyChain: string | null;
  price: number;
  originalPrice: number | null;
  discountPct: number | null;
  stockStatus: 'in_stock' | 'low_stock' | 'out_of_stock';
  recordedAt: Date;
}

export interface MedicationSearchResult {
  id: string;
  name: string;
  activeIngredientName: string;
  dosage: string;
  pharmaceuticalForm: string;
  prescriptionRequired: boolean;
  lowestPrice: number | null;
  highestPrice: number | null;
  pharmacyCount: number;
}
```

- [ ] **Step 6: Create `packages/shared-types/src/pharmacy.ts`**

```typescript
export type PharmacyChain =
  | 'cruz_verde'
  | 'salcobrand'
  | 'ahumada'
  | 'dr_simi'
  | 'independent';

export interface Pharmacy {
  id: string;
  name: string;
  chain: PharmacyChain | null;
  type: 'chain' | 'independent';
  address: string | null;
  city: string | null;
  region: string | null;
  lat: number | null;
  lng: number | null;
  phone: string | null;
  logoUrl: string | null;
  hasDelivery: boolean;
  hasPickup: boolean;
  rating: number | null;
  ratingCount: number;
}
```

- [ ] **Step 7: Create `packages/shared-types/src/order.ts`**

```typescript
export type OrderType = 'delivery' | 'pickup';
export type OrderStatus =
  | 'pending'
  | 'confirmed'
  | 'preparing'
  | 'ready'
  | 'dispatched'
  | 'delivered'
  | 'cancelled';
export type PaymentMethod = 'webpay' | 'mercadopago' | 'cash';
export type PaymentStatus = 'pending' | 'paid' | 'failed' | 'refunded';

export interface OrderItem {
  id: string;
  pharmacyProductId: string;
  medicationId: string | null;
  quantity: number;
  unitPrice: number;
  subtotal: number;
}

export interface Order {
  id: string;
  userId: string;
  pharmacyId: string;
  type: OrderType;
  status: OrderStatus;
  subtotal: number;
  deliveryFee: number;
  total: number;
  paymentMethod: PaymentMethod | null;
  paymentStatus: PaymentStatus;
  items: OrderItem[];
  createdAt: Date;
  updatedAt: Date;
}
```

- [ ] **Step 8: Create `packages/shared-types/src/index.ts`**

```typescript
export * from './user';
export * from './medication';
export * from './pharmacy';
export * from './order';
```

- [ ] **Step 9: Build the package**

```bash
cd packages/shared-types && pnpm build
```

Expected: `dist/` directory created with `.js` and `.d.ts` files.

- [ ] **Step 10: Commit**

```bash
cd ../..
git add packages/shared-types/
git commit -m "feat: add shared TypeScript types package"
```

---

## Chunk 2: Database Package

### Task 4: Set up Prisma schema

**Files:**
- Create: `packages/database/package.json`
- Create: `packages/database/tsconfig.json`
- Create: `packages/database/prisma/schema.prisma`
- Create: `packages/database/src/index.ts`
- Create: `packages/database/src/client.ts`

- [ ] **Step 1: Create package structure**

```bash
mkdir -p packages/database/prisma packages/database/src
```

- [ ] **Step 2: Create `packages/database/package.json`**

```json
{
  "name": "@farmacia/database",
  "version": "0.0.1",
  "private": true,
  "main": "./src/index.ts",
  "scripts": {
    "db:generate": "prisma generate",
    "db:push": "prisma db push",
    "db:migrate": "prisma migrate dev",
    "db:migrate:prod": "prisma migrate deploy",
    "db:studio": "prisma studio"
  },
  "dependencies": {
    "@prisma/client": "^5.14.0"
  },
  "devDependencies": {
    "@farmacia/config": "workspace:*",
    "prisma": "^5.14.0",
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 3: Create `packages/database/prisma/schema.prisma`**

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model ActiveIngredient {
  id          String       @id @default(uuid())
  name        String       @unique
  ispCode     String?      @unique @map("isp_code")
  atcCode     String?      @map("atc_code")
  createdAt   DateTime     @default(now()) @map("created_at")
  medications Medication[]

  @@map("active_ingredients")
}

model Medication {
  id                   String            @id @default(uuid())
  name                 String
  activeIngredientId   String?           @map("active_ingredient_id")
  activeIngredient     ActiveIngredient? @relation(fields: [activeIngredientId], references: [id])
  dosage               String
  pharmaceuticalForm   String            @map("pharmaceutical_form")
  concentration        String?
  routeOfAdministration String?          @map("route_of_administration")
  prescriptionRequired Boolean           @default(false) @map("prescription_required")
  ispRegistration      String?           @map("isp_registration")
  createdAt            DateTime          @default(now()) @map("created_at")
  updatedAt            DateTime          @updatedAt @map("updated_at")
  names                MedicationName[]
  pharmacyProducts     PharmacyProduct[]
  orderItems           OrderItem[]
  priceAlerts          PriceAlert[]

  @@map("medications")
}

model MedicationName {
  id             String     @id @default(uuid())
  medicationId   String     @map("medication_id")
  medication     Medication @relation(fields: [medicationId], references: [id], onDelete: Cascade)
  name           String
  nameType       String     @map("name_type")
  laboratory     String?
  normalizedName String     @map("normalized_name")
  createdAt      DateTime   @default(now()) @map("created_at")

  @@unique([medicationId, normalizedName])
  @@index([normalizedName])
  @@map("medication_names")
}

model Pharmacy {
  id           String           @id @default(uuid())
  name         String
  chain        String?
  type         String
  rut          String?          @unique
  address      String?
  city         String?
  region       String?
  lat          Decimal?         @db.Decimal(10, 8)
  lng          Decimal?         @db.Decimal(11, 8)
  phone        String?
  email        String?
  website      String?
  logoUrl      String?          @map("logo_url")
  isActive     Boolean          @default(true) @map("is_active")
  hasDelivery  Boolean          @default(false) @map("has_delivery")
  hasPickup    Boolean          @default(true) @map("has_pickup")
  rating       Decimal?         @db.Decimal(2, 1)
  ratingCount  Int              @default(0) @map("rating_count")
  saasPlan     String?          @map("saas_plan")
  saasActive   Boolean          @default(false) @map("saas_active")
  createdAt    DateTime         @default(now()) @map("created_at")
  updatedAt    DateTime         @updatedAt @map("updated_at")
  products     PharmacyProduct[]
  orders       Order[]
  staff        PharmacyStaff[]
  priceAlerts  PriceAlert[]
  scrapingJobs ScrapingJob[]

  @@map("pharmacies")
}

model PharmacyProduct {
  id           String      @id @default(uuid())
  pharmacyId   String      @map("pharmacy_id")
  pharmacy     Pharmacy    @relation(fields: [pharmacyId], references: [id], onDelete: Cascade)
  medicationId String?     @map("medication_id")
  medication   Medication? @relation(fields: [medicationId], references: [id])
  sku          String
  rawName      String      @map("raw_name")
  brand        String?
  laboratory   String?
  barcode      String?
  source       String
  isActive     Boolean     @default(true) @map("is_active")
  createdAt    DateTime    @default(now()) @map("created_at")
  updatedAt    DateTime    @updatedAt @map("updated_at")
  prices       Price[]
  orderItems   OrderItem[]

  @@unique([pharmacyId, sku])
  @@map("pharmacy_products")
}

model Price {
  id                String          @id @default(uuid())
  pharmacyProductId String          @map("pharmacy_product_id")
  pharmacyProduct   PharmacyProduct @relation(fields: [pharmacyProductId], references: [id], onDelete: Cascade)
  price             Int
  originalPrice     Int?            @map("original_price")
  discountPct       Int?            @map("discount_pct") @db.SmallInt
  stockStatus       String?         @map("stock_status")
  stockQuantity     Int?            @map("stock_quantity")
  recordedAt        DateTime        @default(now()) @map("recorded_at")
  source            String

  @@index([pharmacyProductId, recordedAt(sort: Desc)])
  @@map("prices")
}

model User {
  id            String          @id @default(uuid())
  email         String          @unique
  name          String?
  phone         String?
  passwordHash  String?         @map("password_hash")
  googleId      String?         @unique @map("google_id")
  avatarUrl     String?         @map("avatar_url")
  rut           String?
  address       String?
  city          String?
  region        String?
  role          String          @default("user")
  isActive      Boolean         @default(true) @map("is_active")
  emailVerified Boolean         @default(false) @map("email_verified")
  createdAt     DateTime        @default(now()) @map("created_at")
  updatedAt     DateTime        @updatedAt @map("updated_at")
  orders        Order[]
  priceAlerts   PriceAlert[]
  prescriptions Prescription[]
  pharmacyStaff PharmacyStaff[]

  @@map("users")
}

model RefreshToken {
  id        String   @id @default(uuid())
  userId    String   @map("user_id")
  token     String   @unique
  expiresAt DateTime @map("expires_at")
  createdAt DateTime @default(now()) @map("created_at")

  @@index([userId])
  @@map("refresh_tokens")
}

model PriceAlert {
  id            String     @id @default(uuid())
  userId        String     @map("user_id")
  user          User       @relation(fields: [userId], references: [id], onDelete: Cascade)
  medicationId  String     @map("medication_id")
  medication    Medication @relation(fields: [medicationId], references: [id], onDelete: Cascade)
  pharmacyId    String?    @map("pharmacy_id")
  pharmacy      Pharmacy?  @relation(fields: [pharmacyId], references: [id])
  targetPrice   Int        @map("target_price")
  isActive      Boolean    @default(true) @map("is_active")
  lastTriggered DateTime?  @map("last_triggered")
  createdAt     DateTime   @default(now()) @map("created_at")

  @@map("price_alerts")
}

model Order {
  id               String         @id @default(uuid())
  userId           String         @map("user_id")
  user             User           @relation(fields: [userId], references: [id])
  pharmacyId       String         @map("pharmacy_id")
  pharmacy         Pharmacy       @relation(fields: [pharmacyId], references: [id])
  type             String
  status           String         @default("pending")
  subtotal         Int
  deliveryFee      Int            @default(0) @map("delivery_fee")
  total            Int
  deliveryAddress  String?        @map("delivery_address")
  deliveryLat      Decimal?       @map("delivery_lat") @db.Decimal(10, 8)
  deliveryLng      Decimal?       @map("delivery_lng") @db.Decimal(11, 8)
  estimatedDelivery DateTime?     @map("estimated_delivery")
  paymentMethod    String?        @map("payment_method")
  paymentStatus    String         @default("pending") @map("payment_status")
  paymentToken     String?        @map("payment_token")
  notes            String?
  createdAt        DateTime       @default(now()) @map("created_at")
  updatedAt        DateTime       @updatedAt @map("updated_at")
  items            OrderItem[]
  prescription     Prescription?

  @@map("orders")
}

model OrderItem {
  id                String          @id @default(uuid())
  orderId           String          @map("order_id")
  order             Order           @relation(fields: [orderId], references: [id], onDelete: Cascade)
  pharmacyProductId String          @map("pharmacy_product_id")
  pharmacyProduct   PharmacyProduct @relation(fields: [pharmacyProductId], references: [id])
  medicationId      String?         @map("medication_id")
  medication        Medication?     @relation(fields: [medicationId], references: [id])
  quantity          Int
  unitPrice         Int             @map("unit_price")
  subtotal          Int

  @@map("order_items")
}

model Prescription {
  id           String    @id @default(uuid())
  userId       String    @map("user_id")
  user         User      @relation(fields: [userId], references: [id])
  orderId      String?   @unique @map("order_id")
  order        Order?    @relation(fields: [orderId], references: [id])
  fileUrl      String    @map("file_url")
  status       String    @default("pending")
  notes        String?
  verifiedById String?   @map("verified_by_id")
  createdAt    DateTime  @default(now()) @map("created_at")

  @@map("prescriptions")
}

model ScrapingJob {
  id           String    @id @default(uuid())
  pharmacyId   String?   @map("pharmacy_id")
  pharmacy     Pharmacy? @relation(fields: [pharmacyId], references: [id])
  pharmacyChain String   @map("pharmacy_chain")
  status       String    @default("pending")
  startedAt    DateTime? @map("started_at")
  finishedAt   DateTime? @map("finished_at")
  itemsScraped Int       @default(0) @map("items_scraped")
  itemsUpdated Int       @default(0) @map("items_updated")
  errors       Json?
  createdAt    DateTime  @default(now()) @map("created_at")

  @@map("scraping_jobs")
}

model PharmacyStaff {
  id         String   @id @default(uuid())
  userId     String   @map("user_id")
  user       User     @relation(fields: [userId], references: [id])
  pharmacyId String   @map("pharmacy_id")
  pharmacy   Pharmacy @relation(fields: [pharmacyId], references: [id])
  role       String   @default("staff")
  createdAt  DateTime @default(now()) @map("created_at")

  @@unique([userId, pharmacyId])
  @@map("pharmacy_staff")
}
```

- [ ] **Step 4: Create `packages/database/src/client.ts`**

```typescript
import { PrismaClient } from '@prisma/client';

const globalForPrisma = globalThis as unknown as {
  prisma: PrismaClient | undefined;
};

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['query', 'error', 'warn'] : ['error'],
  });

if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;

export type { PrismaClient } from '@prisma/client';
```

- [ ] **Step 5: Create `packages/database/src/index.ts`**

```typescript
export { prisma } from './client';
export type { PrismaClient } from './client';
export * from '@prisma/client';
```

- [ ] **Step 6: Install Prisma and generate client**

```bash
cd packages/database
pnpm install
pnpm db:generate
```

Expected: `node_modules/.prisma/client` generated.

- [ ] **Step 7: Commit**

```bash
cd ../..
git add packages/database/
git commit -m "feat: add Prisma schema and database package with full data model"
```

---

## Chunk 3: Docker Infrastructure

### Task 5: Docker Compose for local development

**Files:**
- Create: `infra/docker/docker-compose.yml`
- Create: `infra/docker/docker-compose.test.yml`
- Create: `infra/docker/postgres/init.sql`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p infra/docker/postgres
```

- [ ] **Step 2: Create `infra/docker/postgres/init.sql`**

```sql
-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create test database
CREATE DATABASE farmaciacompare_test;
```

- [ ] **Step 3: Create `infra/docker/docker-compose.yml`**

```yaml
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    container_name: farmacia_postgres
    environment:
      POSTGRES_USER: farmacia
      POSTGRES_PASSWORD: farmacia
      POSTGRES_DB: farmaciacompare
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U farmacia -d farmaciacompare"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: farmacia_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  elasticsearch:
    image: elasticsearch:8.13.0
    container_name: farmacia_elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 10s
      timeout: 10s
      retries: 10

volumes:
  postgres_data:
  redis_data:
  es_data:
```

- [ ] **Step 4: Create `infra/docker/docker-compose.test.yml`**

```yaml
version: '3.9'

services:
  postgres_test:
    image: postgres:16-alpine
    container_name: farmacia_postgres_test
    environment:
      POSTGRES_USER: farmacia
      POSTGRES_PASSWORD: farmacia
      POSTGRES_DB: farmaciacompare_test
    ports:
      - "5433:5432"
    tmpfs:
      - /var/lib/postgresql/data

  redis_test:
    image: redis:7-alpine
    container_name: farmacia_redis_test
    ports:
      - "6380:6379"
```

- [ ] **Step 5: Start Docker services**

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

Expected output:
```
✔ Container farmacia_postgres       Started
✔ Container farmacia_redis          Started
✔ Container farmacia_elasticsearch  Started
```

- [ ] **Step 6: Run database migrations**

```bash
cp .env.example .env
# Edit .env if needed — defaults should work for local Docker
cd packages/database
pnpm db:push
```

Expected: All tables created in PostgreSQL.

- [ ] **Step 7: Verify the database**

```bash
docker exec farmacia_postgres psql -U farmacia -d farmaciacompare -c "\dt"
```

Expected: List of all 14 tables.

- [ ] **Step 8: Commit**

```bash
cd ../..
git add infra/
git commit -m "chore: add Docker Compose local dev infrastructure"
```

---

## Chunk 4: API Gateway Service

### Task 6: Scaffold NestJS API Gateway

**Files:**
- Create: `services/api-gateway/package.json`
- Create: `services/api-gateway/tsconfig.json`
- Create: `services/api-gateway/src/main.ts`
- Create: `services/api-gateway/src/app.module.ts`
- Create: `services/api-gateway/src/app.controller.ts`

- [ ] **Step 1: Create NestJS app**

```bash
cd services
npx @nestjs/cli new api-gateway --package-manager pnpm --skip-git
cd api-gateway
# Remove default app.service.ts and app.controller.spec.ts if you want clean start
```

- [ ] **Step 2: Update `services/api-gateway/package.json` to use workspace packages**

Add to dependencies:
```json
{
  "dependencies": {
    "@farmacia/database": "workspace:*",
    "@farmacia/shared-types": "workspace:*",
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nestjs/platform-express": "^10.0.0",
    "@nestjs/jwt": "^10.0.0",
    "@nestjs/passport": "^10.0.0",
    "@nestjs/config": "^3.0.0",
    "@nestjs/throttler": "^5.0.0",
    "passport": "^0.7.0",
    "passport-jwt": "^4.0.0",
    "passport-google-oauth20": "^2.0.0",
    "bcryptjs": "^2.4.3",
    "class-validator": "^0.14.0",
    "class-transformer": "^0.5.0",
    "helmet": "^7.0.0",
    "ioredis": "^5.3.0",
    "zod": "^3.23.0",
    "reflect-metadata": "^0.2.0",
    "rxjs": "^7.8.0"
  }
}
```

- [ ] **Step 3: Create `services/api-gateway/src/main.ts`**

```typescript
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';
import helmet from 'helmet';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.use(helmet());
  app.enableCors({
    origin: [
      process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000',
      process.env.NEXT_PUBLIC_DASHBOARD_URL ?? 'http://localhost:3001',
      process.env.NEXT_PUBLIC_ADMIN_URL ?? 'http://localhost:3002',
    ],
    credentials: true,
  });

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  app.setGlobalPrefix('api/v1');

  const port = process.env.API_GATEWAY_PORT ?? 4000;
  await app.listen(port);
  console.log(`API Gateway running on port ${port}`);
}

bootstrap();
```

- [ ] **Step 4: Create `services/api-gateway/src/app.module.ts`**

```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '../../.env',
    }),
    ThrottlerModule.forRoot([
      {
        name: 'short',
        ttl: 1000,
        limit: 10,
      },
      {
        name: 'medium',
        ttl: 60000,
        limit: 100,
      },
    ]),
  ],
  controllers: [AppController],
})
export class AppModule {}
```

- [ ] **Step 5: Create `services/api-gateway/src/app.controller.ts`**

```typescript
import { Controller, Get } from '@nestjs/common';

@Controller()
export class AppController {
  @Get('health')
  health() {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }
}
```

- [ ] **Step 6: Install and start the service**

```bash
cd services/api-gateway
pnpm install
pnpm start:dev
```

- [ ] **Step 7: Test health endpoint**

```bash
curl http://localhost:4000/api/v1/health
```

Expected: `{"status":"ok","timestamp":"..."}`

- [ ] **Step 8: Commit**

```bash
cd ../..
git add services/api-gateway/
git commit -m "feat: scaffold NestJS API gateway with health endpoint"
```

---

## Chunk 5: Authentication

### Task 7: Implement auth — register and login

**Files:**
- Create: `services/api-gateway/src/auth/auth.module.ts`
- Create: `services/api-gateway/src/auth/auth.controller.ts`
- Create: `services/api-gateway/src/auth/auth.service.ts`
- Create: `services/api-gateway/src/auth/dto/register.dto.ts`
- Create: `services/api-gateway/src/auth/dto/login.dto.ts`
- Create: `services/api-gateway/src/auth/strategies/jwt.strategy.ts`
- Create: `services/api-gateway/src/auth/guards/jwt-auth.guard.ts`
- Create: `services/api-gateway/src/auth/guards/roles.guard.ts`
- Create: `services/api-gateway/src/auth/decorators/current-user.decorator.ts`
- Create: `services/api-gateway/src/auth/decorators/roles.decorator.ts`
- Create: `services/api-gateway/test/auth.e2e-spec.ts`

- [ ] **Step 1: Write the failing e2e tests first (TDD)**

Create `services/api-gateway/test/auth.e2e-spec.ts`:

```typescript
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';

describe('Auth (e2e)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true, transform: true }));
    app.setGlobalPrefix('api/v1');
    await app.init();
  });

  afterAll(async () => {
    await app.close();
  });

  describe('POST /api/v1/auth/register', () => {
    it('should register a new user and return tokens', async () => {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({
          email: `test+${Date.now()}@example.com`,
          password: 'Password123!',
          name: 'Test User',
        });

      expect(res.status).toBe(201);
      expect(res.body).toHaveProperty('accessToken');
      expect(res.body).toHaveProperty('refreshToken');
      expect(res.body).toHaveProperty('user');
      expect(res.body.user).not.toHaveProperty('passwordHash');
    });

    it('should reject duplicate email', async () => {
      const email = `dupe+${Date.now()}@example.com`;
      await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email, password: 'Password123!', name: 'User' });

      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email, password: 'Password123!', name: 'User' });

      expect(res.status).toBe(409);
    });

    it('should reject invalid email', async () => {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email: 'not-an-email', password: 'Password123!', name: 'User' });

      expect(res.status).toBe(400);
    });

    it('should reject weak password', async () => {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email: 'test@example.com', password: '123', name: 'User' });

      expect(res.status).toBe(400);
    });
  });

  describe('POST /api/v1/auth/login', () => {
    const email = `login+${Date.now()}@example.com`;
    const password = 'Password123!';

    beforeAll(async () => {
      await request(app.getHttpServer())
        .post('/api/v1/auth/register')
        .send({ email, password, name: 'Login Test' });
    });

    it('should login and return tokens', async () => {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({ email, password });

      expect(res.status).toBe(200);
      expect(res.body).toHaveProperty('accessToken');
    });

    it('should reject wrong password', async () => {
      const res = await request(app.getHttpServer())
        .post('/api/v1/auth/login')
        .send({ email, password: 'wrongpassword' });

      expect(res.status).toBe(401);
    });
  });
});
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
cd services/api-gateway
pnpm test:e2e -- --testPathPattern=auth
```

Expected: FAIL — auth routes don't exist yet.

- [ ] **Step 3: Create `services/api-gateway/src/auth/dto/register.dto.ts`**

```typescript
import { IsEmail, IsString, MinLength, MaxLength, Matches } from 'class-validator';

export class RegisterDto {
  @IsEmail()
  email: string;

  @IsString()
  @MinLength(8)
  @MaxLength(50)
  @Matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/, {
    message: 'Password must contain at least one uppercase letter, one lowercase letter, and one number',
  })
  password: string;

  @IsString()
  @MinLength(2)
  @MaxLength(100)
  name: string;
}
```

- [ ] **Step 4: Create `services/api-gateway/src/auth/dto/login.dto.ts`**

```typescript
import { IsEmail, IsString } from 'class-validator';

export class LoginDto {
  @IsEmail()
  email: string;

  @IsString()
  password: string;
}
```

- [ ] **Step 5: Create `services/api-gateway/src/auth/strategies/jwt.strategy.ts`**

```typescript
import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { prisma } from '@farmacia/database';

export interface JwtPayload {
  sub: string;
  email: string;
  role: string;
}

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor() {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: process.env.JWT_SECRET!,
    });
  }

  async validate(payload: JwtPayload) {
    const user = await prisma.user.findUnique({
      where: { id: payload.sub },
      select: { id: true, email: true, name: true, role: true, isActive: true },
    });

    if (!user || !user.isActive) {
      throw new UnauthorizedException();
    }

    return user;
  }
}
```

- [ ] **Step 6: Create `services/api-gateway/src/auth/guards/jwt-auth.guard.ts`**

```typescript
import { Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {}
```

- [ ] **Step 7: Create `services/api-gateway/src/auth/guards/roles.guard.ts`**

```typescript
import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { ROLES_KEY } from '../decorators/roles.decorator';

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (!requiredRoles) return true;

    const { user } = context.switchToHttp().getRequest();
    return requiredRoles.includes(user.role);
  }
}
```

- [ ] **Step 8: Create `services/api-gateway/src/auth/decorators/current-user.decorator.ts`**

```typescript
import { createParamDecorator, ExecutionContext } from '@nestjs/common';

export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext) => {
    const request = ctx.switchToHttp().getRequest();
    return request.user;
  },
);
```

- [ ] **Step 9: Create `services/api-gateway/src/auth/decorators/roles.decorator.ts`**

```typescript
import { SetMetadata } from '@nestjs/common';

export const ROLES_KEY = 'roles';
export const Roles = (...roles: string[]) => SetMetadata(ROLES_KEY, roles);
```

- [ ] **Step 10: Create `services/api-gateway/src/auth/auth.service.ts`**

```typescript
import {
  Injectable,
  ConflictException,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { prisma } from '@farmacia/database';
import * as bcrypt from 'bcryptjs';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';
import { AuthTokens } from '@farmacia/shared-types';

@Injectable()
export class AuthService {
  constructor(private readonly jwtService: JwtService) {}

  async register(dto: RegisterDto): Promise<AuthTokens & { user: object }> {
    const existing = await prisma.user.findUnique({ where: { email: dto.email } });
    if (existing) {
      throw new ConflictException('Email already in use');
    }

    const passwordHash = await bcrypt.hash(dto.password, 12);
    const user = await prisma.user.create({
      data: {
        email: dto.email,
        name: dto.name,
        passwordHash,
      },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        createdAt: true,
      },
    });

    const tokens = await this.generateTokens(user.id, user.email, user.role);
    return { ...tokens, user };
  }

  async login(dto: LoginDto): Promise<AuthTokens & { user: object }> {
    const user = await prisma.user.findUnique({
      where: { email: dto.email },
      select: {
        id: true,
        email: true,
        name: true,
        role: true,
        passwordHash: true,
        isActive: true,
      },
    });

    if (!user || !user.passwordHash || !user.isActive) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const valid = await bcrypt.compare(dto.password, user.passwordHash);
    if (!valid) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const tokens = await this.generateTokens(user.id, user.email, user.role);
    const { passwordHash: _, ...safeUser } = user;
    return { ...tokens, user: safeUser };
  }

  async refreshTokens(refreshToken: string): Promise<AuthTokens> {
    const stored = await prisma.refreshToken.findUnique({
      where: { token: refreshToken },
    });

    if (!stored || stored.expiresAt < new Date()) {
      throw new UnauthorizedException('Invalid refresh token');
    }

    await prisma.refreshToken.delete({ where: { id: stored.id } });

    const user = await prisma.user.findUniqueOrThrow({
      where: { id: stored.userId },
      select: { id: true, email: true, role: true },
    });

    return this.generateTokens(user.id, user.email, user.role);
  }

  private async generateTokens(
    userId: string,
    email: string,
    role: string,
  ): Promise<AuthTokens> {
    const payload = { sub: userId, email, role };

    const [accessToken, refreshToken] = await Promise.all([
      this.jwtService.signAsync(payload, {
        secret: process.env.JWT_SECRET,
        expiresIn: process.env.JWT_EXPIRES_IN ?? '15m',
      }),
      this.jwtService.signAsync(payload, {
        secret: process.env.JWT_REFRESH_SECRET,
        expiresIn: process.env.JWT_REFRESH_EXPIRES_IN ?? '7d',
      }),
    ]);

    // Store refresh token
    const expiresAt = new Date();
    expiresAt.setDate(expiresAt.getDate() + 7);

    await prisma.refreshToken.create({
      data: { userId, token: refreshToken, expiresAt },
    });

    return {
      accessToken,
      refreshToken,
      expiresIn: 900, // 15 minutes in seconds
    };
  }
}
```

- [ ] **Step 11: Create `services/api-gateway/src/auth/auth.controller.ts`**

```typescript
import { Controller, Post, Body, HttpCode, HttpStatus } from '@nestjs/common';
import { AuthService } from './auth.service';
import { RegisterDto } from './dto/register.dto';
import { LoginDto } from './dto/login.dto';

@Controller('auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Post('register')
  register(@Body() dto: RegisterDto) {
    return this.authService.register(dto);
  }

  @Post('login')
  @HttpCode(HttpStatus.OK)
  login(@Body() dto: LoginDto) {
    return this.authService.login(dto);
  }

  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  refresh(@Body('refreshToken') refreshToken: string) {
    return this.authService.refreshTokens(refreshToken);
  }
}
```

- [ ] **Step 12: Create `services/api-gateway/src/auth/auth.module.ts`**

```typescript
import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { PassportModule } from '@nestjs/passport';
import { AuthController } from './auth.controller';
import { AuthService } from './auth.service';
import { JwtStrategy } from './strategies/jwt.strategy';

@Module({
  imports: [
    PassportModule,
    JwtModule.register({}), // Secrets passed per-call for flexibility
  ],
  controllers: [AuthController],
  providers: [AuthService, JwtStrategy],
  exports: [AuthService, JwtStrategy],
})
export class AuthModule {}
```

- [ ] **Step 13: Register AuthModule in AppModule**

Edit `services/api-gateway/src/app.module.ts`:

```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';
import { AuthModule } from './auth/auth.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '../../.env',
    }),
    ThrottlerModule.forRoot([
      { name: 'short', ttl: 1000, limit: 10 },
      { name: 'medium', ttl: 60000, limit: 100 },
    ]),
    AuthModule,
  ],
  controllers: [AppController],
})
export class AppModule {}
```

- [ ] **Step 14: Run e2e tests to verify they pass**

```bash
cd services/api-gateway
DATABASE_URL=postgresql://farmacia:farmacia@localhost:5432/farmaciacompare_test pnpm test:e2e -- --testPathPattern=auth
```

Expected: All auth tests PASS.

- [ ] **Step 15: Commit**

```bash
cd ../..
git add services/api-gateway/src/auth/ services/api-gateway/test/
git commit -m "feat: implement JWT auth with register, login, and refresh token"
```

---

## Chunk 6: Next.js Web App Scaffold

### Task 8: Scaffold the consumer web app

**Files:**
- Create: `apps/web/` (Next.js 14 App Router)
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/lib/api-client.ts`
- Create: `apps/web/src/middleware.ts`

- [ ] **Step 1: Create Next.js app**

```bash
cd apps
npx create-next-app@latest web \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-git
```

- [ ] **Step 2: Add workspace dependencies to `apps/web/package.json`**

```json
{
  "dependencies": {
    "@farmacia/shared-types": "workspace:*",
    "next-auth": "^5.0.0-beta",
    "axios": "^1.7.0",
    "zustand": "^4.5.0",
    "@tanstack/react-query": "^5.40.0",
    "react-hook-form": "^7.51.0",
    "zod": "^3.23.0",
    "@hookform/resolvers": "^3.3.0",
    "lucide-react": "^0.383.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.3.0"
  }
}
```

- [ ] **Step 3: Create `apps/web/src/lib/api-client.ts`**

```typescript
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api/v1';

export const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// Attach auth token from localStorage if present
apiClient.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('accessToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Auto-refresh on 401
apiClient.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refreshToken = localStorage.getItem('refreshToken');
      if (refreshToken) {
        try {
          const { data } = await apiClient.post('/auth/refresh', { refreshToken });
          localStorage.setItem('accessToken', data.accessToken);
          localStorage.setItem('refreshToken', data.refreshToken);
          original.headers.Authorization = `Bearer ${data.accessToken}`;
          return apiClient(original);
        } catch {
          localStorage.removeItem('accessToken');
          localStorage.removeItem('refreshToken');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  },
);
```

- [ ] **Step 4: Update `apps/web/src/app/layout.tsx`**

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'FarmaciaCompare — Compara precios de medicamentos en Chile',
  description:
    'Compara precios de medicamentos en todas las farmacias de Chile. Cruz Verde, Salcobrand, Ahumada, Dr. Simi y más.',
  keywords: 'medicamentos, farmacias, Chile, precios, comparar, paracetamol, ibuprofeno',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
```

- [ ] **Step 5: Create placeholder `apps/web/src/app/page.tsx`**

```tsx
export default function HomePage() {
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-20 text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          FarmaciaCompare
        </h1>
        <p className="text-xl text-gray-600">
          Compara precios de medicamentos en todas las farmacias de Chile
        </p>
        <p className="text-sm text-gray-400 mt-8">🚧 En construcción — Phase 4</p>
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Run the web app**

```bash
cd apps/web
pnpm install
pnpm dev
```

Expected: App running at `http://localhost:3000`.

- [ ] **Step 7: Verify it loads in browser**

Open `http://localhost:3000` — should show the placeholder homepage.

- [ ] **Step 8: Commit**

```bash
cd ../..
git add apps/web/
git commit -m "feat: scaffold Next.js consumer web app with API client"
```

---

## Chunk 7: Phase 1 Integration Verification

### Task 9: Verify full stack works end-to-end

- [ ] **Step 1: Ensure all Docker services are healthy**

```bash
docker compose -f infra/docker/docker-compose.yml ps
```

Expected: postgres, redis, elasticsearch all `healthy`.

- [ ] **Step 2: Start API Gateway**

```bash
cd services/api-gateway && pnpm start:dev
```

Expected: `API Gateway running on port 4000`

- [ ] **Step 3: Register a test user via curl**

```bash
curl -X POST http://localhost:4000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@farmaciacompare.cl","password":"Password123!","name":"Test User"}'
```

Expected: JSON with `accessToken`, `refreshToken`, and `user`.

- [ ] **Step 4: Login with the same user**

```bash
curl -X POST http://localhost:4000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@farmaciacompare.cl","password":"Password123!"}'
```

Expected: JSON with `accessToken`.

- [ ] **Step 5: Test auth middleware — protected route**

```bash
# Without token (should fail)
curl http://localhost:4000/api/v1/users/me
# Expected: 401 Unauthorized

# With token
TOKEN="<accessToken from login response>"
curl http://localhost:4000/api/v1/users/me \
  -H "Authorization: Bearer $TOKEN"
# Expected: User object (once /users/me is implemented in Phase 4)
```

- [ ] **Step 6: Run all e2e tests**

```bash
cd services/api-gateway
pnpm test:e2e
```

Expected: All tests PASS.

- [ ] **Step 7: Final Phase 1 commit**

```bash
cd ../..
git add .
git commit -m "chore: Phase 1 complete — monorepo, database, auth, dev infrastructure"
```

---

## Phase 1 Complete

**What was built:**
- Turborepo monorepo with pnpm workspaces
- Shared TypeScript types package
- Full Prisma schema with all domain tables
- Docker Compose (PostgreSQL 16, Redis 7, Elasticsearch 8)
- NestJS API Gateway with JWT auth (register, login, refresh)
- Next.js 14 consumer app scaffold

**Next:** Start Phase 2 — Data Ingestion (ISP dataset import and medication normalization engine).

See: `docs/superpowers/plans/2026-03-11-farmaciacompare-phase-2-ingestion.md`
