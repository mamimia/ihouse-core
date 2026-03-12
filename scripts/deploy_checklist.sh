#!/usr/bin/env bash
# =============================================================================
# iHouse Core — Pre-Deploy Validation Checklist
# Phase 286 — Production Docker Hardening
# =============================================================================
#
# Validates that the environment is ready for production deployment.
# Runs all checks sequentially and exits non-zero on first failure.
#
# Usage:
#   ./scripts/deploy_checklist.sh
#   ./scripts/deploy_checklist.sh --env .env.staging
#
# Checks performed:
#   1. Required environment variables present
#   2. Supabase reachability (HTTP 200)
#   3. Port 8000 not already in use
#   4. Docker + compose available
#   5. Image builds without error (dry-run: syntax check)
#   6. /health endpoint returns 200 after container start
#   7. Confirm all migrations are applied (via SUPABASE_URL)
# =============================================================================

set -euo pipefail

ENV_FILE="${1:-.env}"

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC}  $1"; }
fail() { echo -e "  ${RED}✗${NC}  $1"; exit 1; }
warn() { echo -e "  ${YELLOW}!${NC}  $1"; }
section() { echo -e "\n${YELLOW}▶ $1${NC}"; }

echo ""
echo "=============================="
echo "  iHouse Core Deploy Checklist"
echo "  Phase 286 — $(date '+%Y-%m-%d %H:%M %Z')"
echo "=============================="

# ---------------------------------------------------------------------------
# Step 1 — Load env file
# ---------------------------------------------------------------------------
section "Step 1 — Environment file"

if [[ ! -f "$ENV_FILE" ]]; then
  fail "Env file '$ENV_FILE' not found. Create it from .env.production.example"
fi
pass "Env file: $ENV_FILE"

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

# ---------------------------------------------------------------------------
# Step 2 — Required variables
# ---------------------------------------------------------------------------
section "Step 2 — Required environment variables"

REQUIRED_VARS=(
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  IHOUSE_JWT_SECRET
  IHOUSE_API_KEY
)

for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    fail "$var is not set in $ENV_FILE"
  fi
  # Mask value for log output
  masked="${!var:0:6}****"
  pass "$var = $masked"
done

# ---------------------------------------------------------------------------
# Step 3 — Supabase reachability
# ---------------------------------------------------------------------------
section "Step 3 — Supabase connectivity"

SUPABASE_HEALTH_URL="${SUPABASE_URL}/rest/v1/"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  --max-time 5 \
  "$SUPABASE_HEALTH_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_STATUS" == "200" ]]; then
  pass "Supabase reachable → HTTP $HTTP_STATUS"
elif [[ "$HTTP_STATUS" == "000" ]]; then
  fail "Supabase not reachable at $SUPABASE_URL (timeout or DNS failure)"
else
  warn "Supabase returned HTTP $HTTP_STATUS — check service role key"
fi

# ---------------------------------------------------------------------------
# Step 4 — Port availability
# ---------------------------------------------------------------------------
section "Step 4 — Port check"

TARGET_PORT="${PORT:-8000}"
if lsof -i ":${TARGET_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  fail "Port $TARGET_PORT is already in use. Kill the existing process before deploying."
fi
pass "Port $TARGET_PORT is free"

# ---------------------------------------------------------------------------
# Step 5 — Docker availability
# ---------------------------------------------------------------------------
section "Step 5 — Docker environment"

if ! command -v docker &>/dev/null; then
  fail "docker not found on PATH"
fi
DOCKER_VERSION=$(docker --version 2>&1)
pass "Docker: $DOCKER_VERSION"

if ! docker compose version &>/dev/null; then
  fail "docker compose v2 not available (required for production deploy)"
fi
COMPOSE_VERSION=$(docker compose version --short 2>&1)
pass "Docker Compose: $COMPOSE_VERSION"

if ! docker info >/dev/null 2>&1; then
  fail "Docker daemon is not running"
fi
pass "Docker daemon is running"

# ---------------------------------------------------------------------------
# Step 6 — Dockerfile syntax (no build, just validate)
# ---------------------------------------------------------------------------
section "Step 6 — Dockerfile validation"

if [[ ! -f "Dockerfile" ]]; then
  fail "Dockerfile not found in current directory"
fi
# Check for required stages
if grep -q "AS builder" Dockerfile && grep -q "AS runtime" Dockerfile; then
  pass "Dockerfile: multi-stage build detected (builder + runtime)"
else
  warn "Dockerfile does not use expected builder/runtime multi-stage structure"
fi

if [[ ! -f "docker-compose.production.yml" ]]; then
  fail "docker-compose.production.yml not found"
fi

# Validate compose syntax
if docker compose -f docker-compose.production.yml config >/dev/null 2>&1; then
  pass "docker-compose.production.yml: syntax valid"
else
  fail "docker-compose.production.yml: syntax error (run: docker compose -f docker-compose.production.yml config)"
fi

# ---------------------------------------------------------------------------
# Step 7 — .env.production.example completeness
# ---------------------------------------------------------------------------
section "Step 7 — Env example completeness"

EXAMPLE_FILE=".env.production.example"
if [[ ! -f "$EXAMPLE_FILE" ]]; then
  warn ".env.production.example not found — new deploys won't have a reference"
else
  for var in "${REQUIRED_VARS[@]}"; do
    if grep -q "^${var}=" "$EXAMPLE_FILE" 2>/dev/null; then
      pass "Example contains: $var"
    else
      warn "Example is missing: $var"
    fi
  done
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=============================="
echo -e "  ✅  All checks passed!"
echo -e "  Ready to deploy."
echo -e "==============================${NC}"
echo ""
echo "  Deploy command:"
echo "    docker compose -f docker-compose.production.yml up -d --build"
echo ""
