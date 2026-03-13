# =============================================================================
# iHouse UI — Production Dockerfile
# Phase 465 — Docker Build Validation
# =============================================================================
#
# Multi-stage build:
#   Stage 1 (deps)     — install npm dependencies
#   Stage 2 (builder)  — build Next.js standalone output
#   Stage 3 (runner)   — copy standalone + static, run with node
#
# Requires: next.config.ts must have output: "standalone"
#
# Build:   docker build -t ihouse-ui .
# Run:     docker run -p 3000:3000 ihouse-ui
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Dependencies
# ---------------------------------------------------------------------------
FROM node:22-alpine AS deps

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm ci --omit=dev

# ---------------------------------------------------------------------------
# Stage 2: Builder
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# Copy deps from previous stage
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build environment variables (build-time only)
ENV NEXT_TELEMETRY_DISABLED=1

# Build the app
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 3: Runner
# ---------------------------------------------------------------------------
FROM node:22-alpine AS runner

WORKDIR /app

# Labels
LABEL org.opencontainers.image.title="iHouse UI"
LABEL org.opencontainers.image.description="Domaniqo property management frontend"

# Non-root user for security
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone output from builder
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Runtime environment
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

# Start the server
CMD ["node", "server.js"]
