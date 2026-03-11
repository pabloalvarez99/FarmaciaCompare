# FarmaciaCompare — Master Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the most advanced medication price comparison and pharmacy marketplace in Chile, designed to scale across Latin America.

**Architecture:** Monorepo with Turborepo housing Next.js frontends (consumer app, pharmacy dashboard, admin panel), NestJS microservices behind an API Gateway, Python scraping workers, and shared infrastructure via Docker/Kubernetes. All services communicate via REST internally and expose a unified GraphQL gateway to clients.

**Tech Stack:** Next.js 14 (App Router), NestJS, TypeScript, PostgreSQL + Prisma, Elasticsearch, Redis + BullMQ, Python + Playwright, React Native (Expo), WebPay Plus, MercadoPago, AWS (EKS + RDS + ElastiCache + OpenSearch), Docker, Kubernetes, Terraform.

---

## Phase Roadmap

| Phase | Name | Deliverable |
|-------|------|-------------|
| 1 | Foundation | Monorepo, DB schema, auth, API gateway, Docker |
| 2 | Data Ingestion | ISP dataset import, medication normalization engine |
| 3 | Price Collection | Playwright scrapers, VTEX/Magento API connectors |
| 4 | Core Web App | Medication search, price comparison, pharmacy map |
| 5 | Commerce | Orders, WebPay Plus, MercadoPago, delivery, prescriptions |
| 6 | Pharmacy SaaS | Dashboard, inventory, price management, analytics |
| 7 | Admin Panel | Catalog management, scraper monitoring, fraud detection |
| 8 | Mobile App | React Native (Expo) iOS + Android |
| 9 | Scale & Ops | Kubernetes, Terraform, observability, CI/CD |

**Start with Phase 1.** Each phase has a dedicated plan file at `docs/superpowers/plans/2026-03-11-farmaciacompare-phase-N-<name>.md`.

---

## Monorepo Structure

```
farmacia-compare/
├── apps/
│   ├── web/                          # Next.js 14 — consumer app
│   ├── dashboard/                    # Next.js 14 — pharmacy SaaS dashboard
│   └── admin/                        # Next.js 14 — admin panel
├── mobile/
│   └── app/                          # React Native (Expo)
├── services/
│   ├── api-gateway/                  # NestJS — GraphQL + REST gateway
│   ├── user-service/                 # NestJS — auth, profiles, alerts
│   ├── pharmacy-service/             # NestJS — pharmacy data, ratings
│   ├── product-service/              # NestJS — medication catalog
│   ├── price-service/                # NestJS — price tracking, history
│   ├── order-service/                # NestJS — orders, payments
│   ├── search-service/               # NestJS — Elasticsearch integration
│   ├── notification-service/         # NestJS — email, push, SMS
│   └── delivery-service/             # NestJS — delivery logistics
├── workers/
│   ├── scraper/                      # Python — Playwright scrapers
│   │   ├── pharmacies/
│   │   │   ├── cruz_verde.py
│   │   │   ├── salcobrand.py
│   │   │   ├── ahumada.py
│   │   │   └── dr_simi.py
│   │   ├── connectors/               # VTEX / Magento / Shopify API
│   │   │   ├── vtex_connector.py
│   │   │   ├── magento_connector.py
│   │   │   └── shopify_connector.py
│   │   ├── normalizer.py             # Price data normalizer
│   │   └── scheduler.py             # APScheduler cron
│   └── ingestion/                    # Python — ISP dataset importer
│       ├── isp_importer.py
│       ├── drug_normalizer.py
│       └── synonym_mapper.py
├── packages/
│   ├── shared-types/                 # TypeScript types shared across apps
│   ├── ui/                           # Shared Shadcn/UI component library
│   ├── database/                     # Prisma schema + migrations
│   └── config/                       # ESLint, TypeScript base configs
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml        # Local dev — all services
│   │   └── docker-compose.test.yml   # Test environment
│   ├── k8s/                          # Kubernetes manifests
│   └── terraform/                    # AWS infrastructure as code
├── docs/
│   ├── api/                          # OpenAPI specs
│   ├── architecture/                 # Architecture decision records
│   └── superpowers/
│       └── plans/
├── package.json                      # pnpm workspace root
├── pnpm-workspace.yaml
├── turbo.json
└── .env.example
```

---

## Database Schema (PostgreSQL + Prisma)

> Canonical reference for all services. Lives in `packages/database/prisma/schema.prisma`.

### Core Tables

```sql
-- Active pharmaceutical ingredient (canonical drug)
CREATE TABLE active_ingredients (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,   -- "Paracetamol"
    isp_code        TEXT UNIQUE,
    atc_code        TEXT,                   -- WHO ATC code
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Canonical medication entity (normalized)
CREATE TABLE medications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT NOT NULL,              -- "Paracetamol 500mg Comprimido"
    active_ingredient_id    UUID REFERENCES active_ingredients(id),
    dosage                  TEXT NOT NULL,              -- "500mg"
    pharmaceutical_form     TEXT NOT NULL,              -- "Comprimido", "Jarabe"
    concentration           TEXT,
    route_of_administration TEXT,
    prescription_required   BOOLEAN DEFAULT FALSE,
    isp_registration        TEXT,                       -- ISP sanitary registration #
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- Brand names / aliases (many per medication)
CREATE TABLE medication_names (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    medication_id   UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,                     -- "Tapsin", "Panadol"
    name_type       TEXT NOT NULL,                     -- 'brand', 'generic', 'alias'
    laboratory      TEXT,
    normalized_name TEXT NOT NULL,                     -- lowercase, no accents, trimmed
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(medication_id, normalized_name)
);
CREATE INDEX idx_medication_names_normalized ON medication_names(normalized_name);

-- Pharmacies
CREATE TABLE pharmacies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    chain           TEXT,                              -- 'cruz_verde', 'salcobrand', etc.
    type            TEXT NOT NULL,                     -- 'chain', 'independent'
    rut             TEXT UNIQUE,
    address         TEXT,
    city            TEXT,
    region          TEXT,
    lat             DECIMAL(10, 8),
    lng             DECIMAL(11, 8),
    phone           TEXT,
    email           TEXT,
    website         TEXT,
    logo_url        TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    has_delivery    BOOLEAN DEFAULT FALSE,
    has_pickup      BOOLEAN DEFAULT TRUE,
    rating          DECIMAL(2,1),
    rating_count    INTEGER DEFAULT 0,
    saas_plan       TEXT,                             -- null | 'basic' | 'pro' | 'enterprise'
    saas_active     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Pharmacy product listings (link between pharmacy and medication)
CREATE TABLE pharmacy_products (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id     UUID NOT NULL REFERENCES pharmacies(id) ON DELETE CASCADE,
    medication_id   UUID REFERENCES medications(id),   -- null if not yet matched
    sku             TEXT NOT NULL,
    raw_name        TEXT NOT NULL,                     -- original name from source
    brand           TEXT,
    laboratory      TEXT,
    barcode         TEXT,
    source          TEXT NOT NULL,                     -- 'scraper', 'api', 'saas', 'isp'
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(pharmacy_id, sku)
);

-- Price records (append-only history)
CREATE TABLE prices (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_product_id UUID NOT NULL REFERENCES pharmacy_products(id) ON DELETE CASCADE,
    price               INTEGER NOT NULL,              -- CLP (centavos avoided, CLP has no decimals)
    original_price      INTEGER,                       -- before discount
    discount_pct        SMALLINT,
    stock_status        TEXT,                          -- 'in_stock', 'low_stock', 'out_of_stock'
    stock_quantity      INTEGER,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source              TEXT NOT NULL                  -- 'scraper', 'api', 'saas'
);
CREATE INDEX idx_prices_product_recorded ON prices(pharmacy_product_id, recorded_at DESC);

-- Latest price materialized view (updated by trigger)
CREATE MATERIALIZED VIEW current_prices AS
SELECT DISTINCT ON (pharmacy_product_id)
    pharmacy_product_id,
    price,
    original_price,
    discount_pct,
    stock_status,
    recorded_at
FROM prices
ORDER BY pharmacy_product_id, recorded_at DESC;
CREATE UNIQUE INDEX ON current_prices(pharmacy_product_id);

-- Users
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    name            TEXT,
    phone           TEXT,
    password_hash   TEXT,                              -- null for OAuth users
    google_id       TEXT UNIQUE,
    avatar_url      TEXT,
    rut             TEXT,
    address         TEXT,
    city            TEXT,
    region          TEXT,
    role            TEXT NOT NULL DEFAULT 'user',      -- 'user', 'pharmacy_admin', 'admin'
    is_active       BOOLEAN DEFAULT TRUE,
    email_verified  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Price alerts
CREATE TABLE price_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    medication_id   UUID NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
    pharmacy_id     UUID REFERENCES pharmacies(id),    -- null = any pharmacy
    target_price    INTEGER NOT NULL,                  -- alert when price <= this
    is_active       BOOLEAN DEFAULT TRUE,
    last_triggered  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Orders
CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id),
    pharmacy_id         UUID NOT NULL REFERENCES pharmacies(id),
    type                TEXT NOT NULL,                 -- 'delivery', 'pickup'
    status              TEXT NOT NULL DEFAULT 'pending',
                                                       -- pending, confirmed, preparing,
                                                       -- ready, dispatched, delivered, cancelled
    subtotal            INTEGER NOT NULL,              -- CLP
    delivery_fee        INTEGER DEFAULT 0,
    total               INTEGER NOT NULL,
    delivery_address    TEXT,
    delivery_lat        DECIMAL(10,8),
    delivery_lng        DECIMAL(11,8),
    estimated_delivery  TIMESTAMPTZ,
    payment_method      TEXT,                          -- 'webpay', 'mercadopago', 'cash'
    payment_status      TEXT DEFAULT 'pending',
    payment_token       TEXT,
    notes               TEXT,
    prescription_id     UUID,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE order_items (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id            UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    pharmacy_product_id UUID NOT NULL REFERENCES pharmacy_products(id),
    medication_id       UUID REFERENCES medications(id),
    quantity            INTEGER NOT NULL,
    unit_price          INTEGER NOT NULL,
    subtotal            INTEGER NOT NULL
);

-- Prescriptions
CREATE TABLE prescriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    order_id        UUID REFERENCES orders(id),
    file_url        TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',            -- pending, verified, rejected
    notes           TEXT,
    verified_by     UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Scraping jobs
CREATE TABLE scraping_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pharmacy_id     UUID REFERENCES pharmacies(id),
    pharmacy_chain  TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',            -- pending, running, completed, failed
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    items_scraped   INTEGER DEFAULT 0,
    items_updated   INTEGER DEFAULT 0,
    errors          JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Pharmacy staff (SaaS dashboard users)
CREATE TABLE pharmacy_staff (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    pharmacy_id     UUID NOT NULL REFERENCES pharmacies(id),
    role            TEXT NOT NULL DEFAULT 'staff',     -- 'owner', 'admin', 'staff'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, pharmacy_id)
);
```

---

## API Contract Summary

> Full OpenAPI spec lives in `docs/api/openapi.yaml`. This is the contract surface.

### API Gateway — Public Endpoints

```
# Auth
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/google
POST   /api/v1/auth/logout

# Medication Search
GET    /api/v1/medications/search?q=&page=&limit=
GET    /api/v1/medications/:id
GET    /api/v1/medications/:id/prices          # all pharmacy prices
GET    /api/v1/medications/:id/price-history   # 30-day chart data

# Pharmacies
GET    /api/v1/pharmacies?lat=&lng=&radius=&city=
GET    /api/v1/pharmacies/:id
GET    /api/v1/pharmacies/:id/products

# Orders
POST   /api/v1/orders
GET    /api/v1/orders/:id
GET    /api/v1/orders (user's orders)
POST   /api/v1/orders/:id/cancel

# Payments
POST   /api/v1/payments/webpay/init
POST   /api/v1/payments/webpay/confirm
POST   /api/v1/payments/mercadopago/create
POST   /api/v1/payments/mercadopago/webhook

# Alerts
POST   /api/v1/alerts
GET    /api/v1/alerts
DELETE /api/v1/alerts/:id

# Prescriptions
POST   /api/v1/prescriptions (multipart/form-data)

# User Profile
GET    /api/v1/users/me
PUT    /api/v1/users/me
```

### Pharmacy Dashboard API

```
# Products
GET    /api/v1/dashboard/products
POST   /api/v1/dashboard/products
PUT    /api/v1/dashboard/products/:id
DELETE /api/v1/dashboard/products/:id

# Prices
PUT    /api/v1/dashboard/products/:id/price

# Orders
GET    /api/v1/dashboard/orders
PUT    /api/v1/dashboard/orders/:id/status

# Analytics
GET    /api/v1/dashboard/analytics/sales
GET    /api/v1/dashboard/analytics/views
```

---

## Data Flow Architecture

```
ISP Public Data
     │
     ▼
[Python Ingestion Worker]
     │ normalize + deduplicate
     ▼
medications + medication_names (PostgreSQL)

Pharmacy Websites
     │
     ├─► [Playwright Scrapers] ──────────────────┐
     │                                           │
     └─► [API Connectors (VTEX/Magento)] ────────┤
                                                 │
Pharmacy SaaS Push API ──────────────────────────┤
                                                 ▼
                                    [Price Normalizer Worker]
                                            │
                                      Drug Matching
                                   (active ingredient +
                                    dosage + form fuzzy match)
                                            │
                                            ▼
                            pharmacy_products + prices (PostgreSQL)
                                            │
                                            ▼
                                 [Elasticsearch Indexer]
                                            │
                                            ▼
                                  Search Service (NestJS)
                                            │
                                            ▼
                                    API Gateway (NestJS)
                                            │
                             ┌──────────────┴──────────────┐
                             ▼                             ▼
                        Web App (Next.js)          Mobile (Expo)
```

---

## Medication Normalization Strategy

The drug matching problem is solved in two layers:

**Layer 1 — ISP Import (ground truth)**
- Import ISP dataset which contains canonical: active ingredient, dosage, pharmaceutical form, laboratory, sanitary registration
- Each row becomes one `medication` + one or more `medication_names`

**Layer 2 — Scraped Product Matching**
When a scraper captures a raw product name like `"TAPSIN FORTE 500MG C/20 COMP"`:

1. **Text normalization:** lowercase, remove accents, strip units/quantities
2. **Synonym lookup:** check `medication_names.normalized_name`
3. **Fuzzy match:** if no exact match, use trigram similarity (`pg_trgm`) against names
4. **Active ingredient extraction:** regex patterns for known drugs
5. **Dosage extraction:** regex for `500mg`, `250 mg`, `0.5g`
6. **Form extraction:** keyword list (comprimido, cápsula, jarabe, ampolla, etc.)
7. **Confidence score:** if score > 0.85, auto-link; if < 0.85, flag for manual review

```sql
-- Enable trigram extension for fuzzy matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_medication_names_trgm ON medication_names
USING gin(normalized_name gin_trgm_ops);
```

---

## Phase Plans Index

| Phase | Plan File | Status |
|-------|-----------|--------|
| 1 — Foundation | `2026-03-11-farmaciacompare-phase-1-foundation.md` | ✅ Written |
| 2 — Data Ingestion | `2026-03-11-farmaciacompare-phase-2-ingestion.md` | 📋 TODO |
| 3 — Price Collection | `2026-03-11-farmaciacompare-phase-3-scrapers.md` | 📋 TODO |
| 4 — Core Web App | `2026-03-11-farmaciacompare-phase-4-web.md` | 📋 TODO |
| 5 — Commerce | `2026-03-11-farmaciacompare-phase-5-commerce.md` | 📋 TODO |
| 6 — Pharmacy SaaS | `2026-03-11-farmaciacompare-phase-6-saas.md` | 📋 TODO |
| 7 — Admin Panel | `2026-03-11-farmaciacompare-phase-7-admin.md` | 📋 TODO |
| 8 — Mobile App | `2026-03-11-farmaciacompare-phase-8-mobile.md` | 📋 TODO |
| 9 — Scale & Ops | `2026-03-11-farmaciacompare-phase-9-scale.md` | 📋 TODO |

---

## Monetization Architecture

```
Revenue Stream 1 — Pharmacy SaaS Subscriptions
├── Basic (free)     → 1 branch, manual price updates, basic analytics
├── Pro ($49/mo)     → 3 branches, bulk import, advanced analytics, priority listing
└── Enterprise ($199/mo) → unlimited branches, API access, dedicated support

Revenue Stream 2 — Sponsored Listings
└── Pharmacy pays to appear first in search results for given medications
    Stored in: pharmacy_ad_campaigns table

Revenue Stream 3 — Transaction Commission
└── 2-3% on each order placed through the platform
    Tracked in: order payment metadata

Revenue Stream 4 — Price Data API
└── B2B data sales to insurance companies, health analytics firms
    Gated by API key with rate limits (packages/api-gateway/src/guards)

Revenue Stream 5 — Pharmacy Advertising Banners
└── Display in web/mobile app — managed via admin panel
```

---

## Security Architecture

- **Auth:** JWT access tokens (15m TTL) + refresh tokens (7d TTL, stored in httpOnly cookie)
- **OAuth:** Google OAuth via NextAuth.js
- **API Gateway:** Rate limiting (100 req/min public, 1000 req/min authenticated) via Redis
- **Payments:** Never store card data. Transbank and MercadoPago handle PCI-DSS compliance
- **File uploads:** Prescriptions go to S3 with signed URLs, scanned for malware via ClamAV lambda
- **HTTPS:** TLS everywhere, HSTS, Cloudflare proxy
- **Secrets:** AWS Secrets Manager, never in code/env files in production
- **Database:** Row-level encryption for PII (Prisma field encryption), connection via SSL
- **CORS:** Whitelist of known app domains only
- **Input validation:** Zod on all API inputs (NestJS pipes)
- **SQL injection:** Prisma parameterized queries only
- **XSS:** Content-Security-Policy headers, Next.js built-in escaping
