#!/usr/bin/env bash
# scripts/validate_env.sh — Phase 419
# Validates that all required environment variables are set.
# Exit code 0 = all OK, 1 = missing variables.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

REQUIRED_VARS=(
    SUPABASE_URL
    SUPABASE_KEY
    SUPABASE_SERVICE_ROLE_KEY
    IHOUSE_ENV
    IHOUSE_JWT_SECRET
    IHOUSE_ACCESS_TOKEN_SECRET
)

OPTIONAL_VARS=(
    IHOUSE_CORS_ORIGINS
    IHOUSE_LINE_TOKEN
    IHOUSE_WHATSAPP_TOKEN
    IHOUSE_TELEGRAM_TOKEN
    IHOUSE_SMS_API_KEY
    IHOUSE_EMAIL_API_KEY
    NEXT_PUBLIC_API_URL
    NEXT_PUBLIC_SUPABASE_URL
    NEXT_PUBLIC_SUPABASE_ANON_KEY
)

echo "╔══════════════════════════════════════════════╗"
echo "║    iHouse Core — Environment Validator       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

MISSING=0

echo "── Required ──────────────────────────────────"
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -n "${!var:-}" ]]; then
        printf "  ${GREEN}✓${NC} %s\n" "$var"
    else
        printf "  ${RED}✗${NC} %s ${RED}(MISSING)${NC}\n" "$var"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
echo "── Optional ──────────────────────────────────"
for var in "${OPTIONAL_VARS[@]}"; do
    if [[ -n "${!var:-}" ]]; then
        printf "  ${GREEN}✓${NC} %s\n" "$var"
    else
        printf "  ${YELLOW}○${NC} %s ${YELLOW}(not set)${NC}\n" "$var"
    fi
done

echo ""
if [[ $MISSING -gt 0 ]]; then
    echo -e "${RED}✗ $MISSING required variable(s) missing.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All required variables set.${NC}"
    exit 0
fi
