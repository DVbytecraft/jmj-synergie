# =============================================================================
#  JMJ Synergie — Frontend Dockerfile (multi-stage)
#  Build : docker build --build-arg NEXT_PUBLIC_API_URL=/api/v1 -t jmj-frontend .
# =============================================================================

# ── Stage 1 : dépendances ────────────────────────────────────────────────────
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app

# Copier les deux fichiers de lock pour un install reproductible (npm ci)
COPY package.json package-lock.json ./

# npm ci : install strictement depuis le lock file, plus rapide et déterministe
RUN npm ci --prefer-offline

# ── Stage 2 : build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Variables publiques injectées au build (côté navigateur)
ARG NEXT_PUBLIC_API_URL=/api/v1
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

RUN npm run build

# ── Stage 3 : runner de production ───────────────────────────────────────────
FROM node:20-alpine AS production

RUN apk add --no-cache libc6-compat wget

WORKDIR /app

# Utilisateur non-root pour limiter la surface d'attaque
RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

# Copier uniquement les artefacts nécessaires (standalone output)
COPY --from=builder /app/public                          ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static     ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

# Healthcheck sur la route /api/health créée dans l'app Next.js
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD wget -qO- http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
