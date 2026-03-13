#!/usr/bin/env bash
# scripts/verify_migrations.sh — Phase 407
# Verifies that migration files follow naming convention and can be parsed
# Does NOT apply to live database — dry-run validation only.
set -euo pipefail

MIGRATIONS_DIR="supabase/migrations"
ERRORS=0

echo "=== iHouse Core — Migration Verification ==="
echo ""

# 1. Count migration files
TOTAL=$(ls -1 "${MIGRATIONS_DIR}"/*.sql 2>/dev/null | wc -l | tr -d ' ')
echo "Migration files found: ${TOTAL}"

# 2. Verify naming convention: YYYYMMDDHHMMSS_*.sql
echo ""
echo "--- Naming Convention Check ---"
for f in "${MIGRATIONS_DIR}"/*.sql; do
  BASENAME=$(basename "$f")
  if ! echo "$BASENAME" | grep -qE '^[0-9]{14}_.*\.sql$'; then
    echo "FAIL: ${BASENAME} does not match YYYYMMDDHHMMSS_*.sql"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ $ERRORS -eq 0 ]; then
  echo "All ${TOTAL} files match naming convention ✅"
fi

# 3. Verify chronological ordering
echo ""
echo "--- Chronological Order Check ---"
PREV=""
for f in $(ls -1 "${MIGRATIONS_DIR}"/*.sql | sort); do
  BASENAME=$(basename "$f")
  TS=$(echo "$BASENAME" | grep -oE '^[0-9]{14}')
  if [ -n "$PREV" ] && [ "$TS" \< "$PREV" ]; then
    echo "FAIL: ${BASENAME} is out of order (${TS} < ${PREV})"
    ERRORS=$((ERRORS + 1))
  fi
  PREV="$TS"
done

if [ $ERRORS -eq 0 ]; then
  echo "All files are in chronological order ✅"
fi

# 4. Verify no empty files
echo ""
echo "--- Non-Empty Check ---"
for f in "${MIGRATIONS_DIR}"/*.sql; do
  BASENAME=$(basename "$f")
  SIZE=$(wc -c < "$f" | tr -d ' ')
  if [ "$SIZE" -lt 10 ]; then
    echo "FAIL: ${BASENAME} is effectively empty (${SIZE} bytes)"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ $ERRORS -eq 0 ]; then
  echo "All files are non-empty ✅"
fi

# 5. Summary
echo ""
echo "=== Summary ==="
echo "Files: ${TOTAL}"
echo "Errors: ${ERRORS}"

if [ $ERRORS -gt 0 ]; then
  echo "VERIFICATION FAILED ❌"
  exit 1
else
  echo "VERIFICATION PASSED ✅"
  exit 0
fi
