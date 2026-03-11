# FarmaciaCompare Phase 9 — Scale & Ops Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Production-harden the platform with Kubernetes deployments, Terraform AWS infrastructure, GitHub Actions CI/CD, Elasticsearch search indexing, observability (logs + metrics + traces), and upgrade the job queue to BullMQ.

**Architecture:** AWS EKS for Kubernetes, RDS PostgreSQL (multi-AZ), ElastiCache Redis, OpenSearch (managed Elasticsearch), S3 for uploads, CloudFront CDN, ACM SSL certificates. GitHub Actions builds Docker images → pushes to ECR → deploys to EKS.

**Tech Stack:** Terraform, AWS EKS/RDS/ElastiCache/OpenSearch/S3/CloudFront, Docker, Kubernetes (Helm), GitHub Actions, Prometheus + Grafana, OpenTelemetry, BullMQ, Elasticsearch 8.

**Prerequisites:** Phases 1–8 complete and working locally.

---

## Chunk 1: Elasticsearch Integration

### Task 1: Replace DB search with Elasticsearch

**Files:**
- Create: `services/api-gateway/src/search/search.module.ts`
- Create: `services/api-gateway/src/search/search.service.ts`
- Create: `workers/ingestion/src/es_indexer.py`

- [ ] **Step 1: Install Elasticsearch client**

```bash
cd services/api-gateway
pnpm add @elastic/elasticsearch
```

- [ ] **Step 2: Create `services/api-gateway/src/search/search.service.ts`**

```typescript
import { Injectable, OnModuleInit } from '@nestjs/common';
import { Client } from '@elastic/elasticsearch';

const INDEX = 'medications';

@Injectable()
export class SearchService implements OnModuleInit {
  private client = new Client({
    node: process.env.ELASTICSEARCH_URL ?? 'http://localhost:9200',
  });

  async onModuleInit() {
    await this.ensureIndex();
  }

  async ensureIndex() {
    const exists = await this.client.indices.exists({ index: INDEX });
    if (!exists) {
      await this.client.indices.create({
        index: INDEX,
        mappings: {
          properties: {
            id: { type: 'keyword' },
            name: {
              type: 'text',
              analyzer: 'spanish',
              fields: { keyword: { type: 'keyword' } },
            },
            activeIngredientName: { type: 'text', analyzer: 'spanish' },
            brandNames: { type: 'text', analyzer: 'spanish' },
            dosage: { type: 'keyword' },
            pharmaceuticalForm: { type: 'keyword' },
            prescriptionRequired: { type: 'boolean' },
            lowestPrice: { type: 'integer' },
            pharmacyCount: { type: 'integer' },
          },
        },
        settings: {
          analysis: {
            analyzer: {
              spanish: {
                tokenizer: 'standard',
                filter: ['lowercase', 'asciifolding', 'spanish_stop'],
              },
            },
            filter: {
              spanish_stop: { type: 'stop', stopwords: '_spanish_' },
            },
          },
        },
      });
    }
  }

  async search(query: string, page = 1, limit = 20) {
    const from = (page - 1) * limit;
    const result = await this.client.search({
      index: INDEX,
      from,
      size: limit,
      query: query
        ? {
            multi_match: {
              query,
              fields: ['name^3', 'brandNames^2', 'activeIngredientName^2', 'dosage'],
              fuzziness: 'AUTO',
              type: 'best_fields',
            },
          }
        : { match_all: {} },
    });

    return {
      results: result.hits.hits.map((h) => h._source),
      total: typeof result.hits.total === 'number'
        ? result.hits.total
        : result.hits.total?.value ?? 0,
      page,
      limit,
    };
  }

  async indexMedication(medication: {
    id: string;
    name: string;
    activeIngredientName: string;
    brandNames: string[];
    dosage: string;
    pharmaceuticalForm: string;
    prescriptionRequired: boolean;
    lowestPrice: number | null;
    pharmacyCount: number;
  }) {
    await this.client.index({
      index: INDEX,
      id: medication.id,
      document: medication,
    });
  }

  async bulkIndex(medications: any[]) {
    const operations = medications.flatMap((med) => [
      { index: { _index: INDEX, _id: med.id } },
      med,
    ]);
    await this.client.bulk({ operations });
    await this.client.indices.refresh({ index: INDEX });
  }
}
```

- [ ] **Step 3: Create Python ES indexer**

```python
# workers/ingestion/src/es_indexer.py
from elasticsearch import AsyncElasticsearch
from sqlalchemy import select, text
from .db import AsyncSessionLocal
import os

ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")

async def index_all_medications():
    es = AsyncElasticsearch([ES_URL])
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT
                m.id,
                m.name,
                ai.name AS active_ingredient_name,
                m.dosage,
                m.pharmaceutical_form,
                m.prescription_required,
                ARRAY_AGG(DISTINCT mn.name) AS brand_names,
                MIN(p.price) AS lowest_price,
                COUNT(DISTINCT pp.pharmacy_id) AS pharmacy_count
            FROM medications m
            LEFT JOIN active_ingredients ai ON ai.id = m.active_ingredient_id
            LEFT JOIN medication_names mn ON mn.medication_id = m.id
            LEFT JOIN pharmacy_products pp ON pp.medication_id = m.id AND pp.is_active = true
            LEFT JOIN LATERAL (
                SELECT price FROM prices
                WHERE pharmacy_product_id = pp.id
                ORDER BY recorded_at DESC LIMIT 1
            ) p ON true
            GROUP BY m.id, ai.name
        """))

        operations = []
        for row in result:
            doc = {
                "id": str(row[0]),
                "name": row[1],
                "activeIngredientName": row[2],
                "dosage": row[3],
                "pharmaceuticalForm": row[4],
                "prescriptionRequired": row[5],
                "brandNames": [n for n in (row[6] or []) if n],
                "lowestPrice": row[7],
                "pharmacyCount": row[8] or 0,
            }
            operations.append({"index": {"_index": "medications", "_id": doc["id"]}})
            operations.append(doc)

        if operations:
            await es.bulk(operations=operations)
            await es.indices.refresh(index="medications")
            print(f"Indexed {len(operations) // 2} medications")

    await es.close()
```

- [ ] **Step 4: Replace DB search with Elasticsearch in MedicationsController**

Update `search()` in `medications.service.ts` to call `SearchService.search()` instead of Prisma.

- [ ] **Step 5: Commit**

```bash
git add services/api-gateway/src/search/ workers/ingestion/src/es_indexer.py
git commit -m "feat: integrate Elasticsearch for medication full-text search with Spanish analyzer"
```

---

## Chunk 2: Dockerfiles

### Task 2: Production Dockerfiles for each service

**Files:**
- Create: `services/api-gateway/Dockerfile`
- Create: `apps/web/Dockerfile`
- Create: `workers/scraper/Dockerfile`
- Create: `workers/ingestion/Dockerfile`

- [ ] **Step 1: Create `services/api-gateway/Dockerfile`**

```dockerfile
FROM node:20-alpine AS base
RUN npm install -g pnpm

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/database/package.json ./packages/database/
COPY packages/shared-types/package.json ./packages/shared-types/
COPY packages/config/package.json ./packages/config/
COPY services/api-gateway/package.json ./services/api-gateway/
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm --filter api-gateway build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/services/api-gateway/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/packages ./packages
EXPOSE 4000
CMD ["node", "dist/main.js"]
```

- [ ] **Step 2: Create `apps/web/Dockerfile`**

```dockerfile
FROM node:20-alpine AS base
RUN npm install -g pnpm

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared-types/package.json ./packages/shared-types/
COPY packages/config/package.json ./packages/config/
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm --filter web build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /app/apps/web/public ./apps/web/public
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
```

- [ ] **Step 3: Create `workers/scraper/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install poetry
COPY workers/scraper/pyproject.toml workers/scraper/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi
# Install Playwright browsers
RUN poetry run playwright install chromium
RUN poetry run playwright install-deps chromium
COPY workers/scraper/src ./src
CMD ["poetry", "run", "scraper", "start-scheduler"]
```

- [ ] **Step 4: Test builds locally**

```bash
docker build -f services/api-gateway/Dockerfile -t farmacia-api .
docker build -f apps/web/Dockerfile -t farmacia-web .
docker build -f workers/scraper/Dockerfile -t farmacia-scraper .
```

Expected: All images build without errors.

- [ ] **Step 5: Commit**

```bash
git add services/api-gateway/Dockerfile apps/web/Dockerfile workers/
git commit -m "chore: add production Dockerfiles for all services"
```

---

## Chunk 3: Kubernetes Manifests

### Task 3: K8s deployment manifests

**Files:**
- Create: `infra/k8s/api-gateway/deployment.yaml`
- Create: `infra/k8s/api-gateway/service.yaml`
- Create: `infra/k8s/api-gateway/hpa.yaml`
- Create: `infra/k8s/web/deployment.yaml`
- Create: `infra/k8s/ingress.yaml`
- Create: `infra/k8s/namespace.yaml`

- [ ] **Step 1: Create namespace**

```yaml
# infra/k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: farmacia-compare
  labels:
    app: farmacia-compare
```

- [ ] **Step 2: Create API Gateway deployment**

```yaml
# infra/k8s/api-gateway/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: farmacia-compare
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
        - name: api-gateway
          image: <ECR_REGISTRY>/farmacia-api:latest
          ports:
            - containerPort: 4000
          env:
            - name: NODE_ENV
              value: production
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: farmacia-secrets
                  key: database-url
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: farmacia-secrets
                  key: redis-url
            - name: JWT_SECRET
              valueFrom:
                secretKeyRef:
                  name: farmacia-secrets
                  key: jwt-secret
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: 4000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/v1/health
              port: 4000
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-gateway-hpa
  namespace: farmacia-compare
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-gateway
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

- [ ] **Step 3: Create Nginx Ingress**

```yaml
# infra/k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: farmacia-ingress
  namespace: farmacia-compare
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
    - hosts:
        - farmaciacompare.cl
        - api.farmaciacompare.cl
        - dashboard.farmaciacompare.cl
      secretName: farmacia-tls
  rules:
    - host: farmaciacompare.cl
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: web
                port:
                  number: 3000
    - host: api.farmaciacompare.cl
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-gateway
                port:
                  number: 4000
```

- [ ] **Step 4: Commit**

```bash
git add infra/k8s/
git commit -m "chore: add Kubernetes deployment manifests with HPA and Ingress"
```

---

## Chunk 4: GitHub Actions CI/CD

### Task 4: CI/CD pipeline

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: farmacia
          POSTGRES_PASSWORD: farmacia
          POSTGRES_DB: farmaciacompare_test
        ports: ["5433:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        ports: ["6380:6379"]

    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - name: Install dependencies
        run: pnpm install --frozen-lockfile

      - name: Generate Prisma client
        run: pnpm --filter @farmacia/database db:generate

      - name: Build shared packages
        run: pnpm --filter @farmacia/shared-types build --filter @farmacia/config build

      - name: Run API Gateway tests
        run: pnpm --filter api-gateway test:e2e
        env:
          DATABASE_URL: postgresql://farmacia:farmacia@localhost:5433/farmaciacompare_test
          REDIS_URL: redis://localhost:6380
          JWT_SECRET: test-secret-key
          JWT_REFRESH_SECRET: test-refresh-secret

      - name: Lint
        run: pnpm lint

  python-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install poetry
      - run: cd workers/ingestion && poetry install && poetry run pytest -v
      - run: cd workers/scraper && poetry install && poetry run pytest -v
```

- [ ] **Step 2: Create `.github/workflows/deploy.yml`**

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to ECR
        id: ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push API Gateway
        run: |
          docker build -f services/api-gateway/Dockerfile -t ${{ steps.ecr.outputs.registry }}/farmacia-api:${{ github.sha }} .
          docker push ${{ steps.ecr.outputs.registry }}/farmacia-api:${{ github.sha }}

      - name: Build and push Web App
        run: |
          docker build -f apps/web/Dockerfile -t ${{ steps.ecr.outputs.registry }}/farmacia-web:${{ github.sha }} .
          docker push ${{ steps.ecr.outputs.registry }}/farmacia-web:${{ github.sha }}

  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Update kubeconfig
        run: aws eks update-kubeconfig --name farmacia-compare --region us-east-1

      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/api-gateway api-gateway=${{ steps.ecr.outputs.registry }}/farmacia-api:${{ github.sha }} -n farmacia-compare
          kubectl set image deployment/web web=${{ steps.ecr.outputs.registry }}/farmacia-web:${{ github.sha }} -n farmacia-compare
          kubectl rollout status deployment/api-gateway -n farmacia-compare
          kubectl rollout status deployment/web -n farmacia-compare
```

- [ ] **Step 3: Commit**

```bash
git add .github/
git commit -m "chore: add GitHub Actions CI/CD pipeline with ECR + EKS deployment"
```

---

## Chunk 5: Terraform AWS Infrastructure

### Task 5: Terraform for AWS infrastructure

**Files:**
- Create: `infra/terraform/main.tf`
- Create: `infra/terraform/variables.tf`
- Create: `infra/terraform/outputs.tf`
- Create: `infra/terraform/modules/eks/main.tf`
- Create: `infra/terraform/modules/rds/main.tf`

- [ ] **Step 1: Create `infra/terraform/main.tf`**

```hcl
terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket = "farmacia-compare-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  name    = "farmacia-compare"
  cidr    = "10.0.0.0/16"
  azs     = ["us-east-1a", "us-east-1b", "us-east-1c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
  enable_nat_gateway = true
  single_nat_gateway = false  # HA NAT
}

# EKS
module "eks" {
  source          = "terraform-aws-modules/eks/aws"
  version         = "~> 20.0"
  cluster_name    = "farmacia-compare"
  cluster_version = "1.29"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  eks_managed_node_groups = {
    main = {
      instance_types = ["t3.medium"]
      min_size = 2
      max_size = 10
      desired_size = 3
    }
  }
}

# RDS PostgreSQL
module "db" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"
  identifier = "farmacia-compare"
  engine = "postgres"
  engine_version = "16"
  instance_class = "db.t3.medium"
  allocated_storage = 50
  max_allocated_storage = 500
  db_name  = "farmaciacompare"
  username = "farmacia"
  manage_master_user_password = true
  multi_az = true
  deletion_protection = true
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = module.vpc.database_subnet_group
}

# ElastiCache Redis
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "farmacia-redis"
  description          = "FarmaciaCompare Redis"
  node_type            = "cache.t3.micro"
  num_cache_clusters   = 2
  automatic_failover_enabled = true
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]
}

# S3 for uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "farmacia-compare-uploads-${var.environment}"
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

- [ ] **Step 2: Run Terraform**

```bash
cd infra/terraform
terraform init
terraform plan -out=tfplan
# Review plan, then:
terraform apply tfplan
```

- [ ] **Step 3: Commit**

```bash
git add infra/terraform/
git commit -m "chore: add Terraform infrastructure for AWS EKS + RDS + ElastiCache + S3"
```

---

## Chunk 6: Observability

### Task 6: Logging, metrics, and tracing

- [ ] **Step 1: Add structured logging with Pino**

```bash
cd services/api-gateway && pnpm add pino pino-http @opentelemetry/api
```

Replace `console.log` calls with Pino logger.

- [ ] **Step 2: Add Prometheus metrics endpoint**

```bash
pnpm add @willsoto/nestjs-prometheus prom-client
```

Expose `GET /metrics` with:
- `http_requests_total` (counter)
- `http_request_duration_ms` (histogram)
- `active_scraping_jobs` (gauge)
- `price_records_total` (counter)

- [ ] **Step 3: Add Grafana dashboard to Docker Compose (dev)**

```yaml
# infra/docker/docker-compose.yml additions:
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3100:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
```

- [ ] **Step 4: Commit**

```bash
git add services/api-gateway/ infra/docker/
git commit -m "feat: add structured logging, Prometheus metrics, and Grafana dashboard"
```

---

## Phase 9 Complete — Platform Complete

**What was built:**
- Elasticsearch full-text search with Spanish analyzer
- Production Dockerfiles for all services
- Kubernetes manifests with HPA (auto-scaling 2–10 pods)
- GitHub Actions CI/CD → ECR → EKS deployment
- Terraform for full AWS infrastructure (EKS, RDS multi-AZ, ElastiCache, S3)
- Prometheus metrics + Grafana dashboards
- Structured JSON logging

---

## Final Checklist Before Launch

- [ ] All 9 phases complete and tested
- [ ] Terraform infra provisioned in AWS
- [ ] DNS pointing to CloudFront / Load Balancer
- [ ] SSL certificates via ACM
- [ ] Database migrations run in production
- [ ] ISP dataset imported (Phase 2)
- [ ] Scrapers tested and collecting prices
- [ ] Elasticsearch indexed
- [ ] WebPay Plus production credentials configured
- [ ] MercadoPago production credentials configured
- [ ] Google OAuth production credentials configured
- [ ] Monitoring and alerting configured (PagerDuty / Opsgenie)
- [ ] Load testing performed (target: 1000 concurrent users)
- [ ] Security audit completed (OWASP top 10)
- [ ] Privacy policy and terms of service published (GDPR/Chilean law compliance)
