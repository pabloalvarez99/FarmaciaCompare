FROM node:20-alpine AS base
RUN npm install -g pnpm@9

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages/database/package.json ./packages/database/
COPY packages/shared-types/package.json ./packages/shared-types/
COPY packages/config/package.json ./packages/config/
COPY services/api-gateway/package.json ./services/api-gateway/
# apps/* are importers in pnpm-lock.yaml. --frozen-lockfile refuses to install
# when a workspace member listed in the lockfile has no manifest on disk.
COPY apps/web/package.json ./apps/web/
COPY apps/admin/package.json ./apps/admin/
COPY apps/dashboard/package.json ./apps/dashboard/
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/packages/database/node_modules ./packages/database/node_modules
COPY --from=deps /app/packages/shared-types/node_modules ./packages/shared-types/node_modules
# packages/config ships only tsconfig files — it has no dependencies, so pnpm
# creates no node_modules for it and COPYing one fails the build.
COPY --from=deps /app/services/api-gateway/node_modules ./services/api-gateway/node_modules
COPY . .
# The gateway imports @farmacia/database and @farmacia/shared-types, whose
# package.json point at ./dist. Those dists are gitignored, so they must be
# compiled here or `nest build` fails with TS2307 "Cannot find module".
RUN pnpm --filter @farmacia/database db:generate
RUN pnpm --filter @farmacia/shared-types build
RUN pnpm --filter @farmacia/database build
RUN pnpm --filter api-gateway build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# Prisma's query engine links against libssl at runtime; the slim node image
# does not ship it.
RUN apk add --no-cache openssl
# Keep the workspace layout. pnpm puts the gateway's dependencies in
# services/api-gateway/node_modules (only root-level deps live in /app/node_modules),
# and those are symlinks into /app/node_modules/.pnpm. Running the bundle from
# /app/dist would resolve against /app/node_modules and miss @nestjs/core; from
# /app/services/api-gateway/dist Node walks up and finds the right tree.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/packages ./packages
COPY --from=build /app/services/api-gateway/node_modules ./services/api-gateway/node_modules
COPY --from=build /app/services/api-gateway/dist ./services/api-gateway/dist
# Cloud Run injects PORT; 8080 is its default and what the container advertises.
ENV PORT=8080
EXPOSE 8080
CMD ["node", "services/api-gateway/dist/main.js"]
