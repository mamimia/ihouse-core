#!/usr/bin/env bash
set -euo pipefail

OUT="artifacts/notebooklm_sources"

mkdir -p "$OUT"

cp docs/core/BOOT.md "$OUT/BOOT.md"
cp docs/core/current-snapshot.md "$OUT/current-snapshot.md"
cp docs/core/governance.md "$OUT/governance.md"

if [ -f docs/core/architecture.md ]; then
  cp docs/core/architecture.md "$OUT/architecture.md"
fi

cp artifacts/supabase/schema.sql "$OUT/supabase_schema.sql"
cp artifacts/supabase/schema.hash.txt "$OUT/supabase_schema.hash.txt"

if [ -f artifacts/supabase/registries.sql ]; then
  cp artifacts/supabase/registries.sql "$OUT/supabase_registries.sql"
fi

ls -lh "$OUT"
