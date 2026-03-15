# =============================================================================
# iHouse Core — Production Dockerfile
# Phase 275 — Deployment Readiness Audit
# =============================================================================
#
# Multi-stage build:
#   Stage 1 (builder)  — install Python deps into a venv
#   Stage 2 (runtime)  — copy venv + source, run uvicorn
#
# Build:   docker build -t ihouse-core .
# Run:     docker run --env-file .env -p 8000:8000 ihouse-core
#
# Health:  GET /health  → 200 ok | 200 degraded | 503 unhealthy
# Ready:   GET /readiness → 200 ready | 503 not ready
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder

WORKDIR /build

# Install system deps needed for some Python packages (cffi, cryptography)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Create venv and install deps
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime

# Labels
LABEL org.opencontainers.image.title="iHouse Core"
LABEL org.opencontainers.image.description="Deterministic property operations platform"
LABEL org.opencontainers.image.vendor="iHouse"

# Non-root user for security
RUN groupadd -r ihouse && useradd -r -g ihouse -d /app -s /sbin/nologin ihouse

WORKDIR /app

# Copy venv from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source — ONLY src/ (the live production codebase)
# Note: app/ is the old Phase 13C SQLite entrypoint — NOT used in production.
COPY src/ ./src/

# Set PYTHONPATH so imports resolve correctly
ENV PYTHONPATH="/app/src"

# Python settings for containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Default port
ENV PORT=8000

# Switch to non-root user
USER ihouse

# Expose port
EXPOSE ${PORT}

# Health check — built-in Docker HEALTHCHECK
# Checks /health endpoint every 30s, marks unhealthy after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run uvicorn — production mode (no reload, workers configurable via UVICORN_WORKERS)
CMD ["sh", "-c", \
    "uvicorn main:app \
     --host 0.0.0.0 \
     --port ${PORT:-8000} \
     --workers ${UVICORN_WORKERS:-2} \
     --log-level info \
     --access-log \
     --no-use-colors"]
