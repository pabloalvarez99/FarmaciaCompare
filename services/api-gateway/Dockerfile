FROM node:20-alpine AS base
RUN npm install -g pnpm@9

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
COPY --from=deps /app/packages/database/node_modules ./packages/database/node_modules
COPY --from=deps /app/packages/shared-types/node_modules ./packages/shared-types/node_modules
COPY --from=deps /app/packages/config/node_modules ./packages/config/node_modules
COPY --from=deps /app/services/api-gateway/node_modules ./services/api-gateway/node_modules
COPY . .
RUN pnpm --filter @farmacia/database db:generate || true
RUN pnpm --filter api-gateway build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/services/api-gateway/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/packages ./packages
EXPOSE 4000
CMD ["node", "dist/main.js"]
