#!/usr/bin/env bash
set -euo pipefail

mkdir -p artifacts/supabase

echo "[1/4] Dump public schema (includes functions) -> artifacts/supabase/schema.sql"
supabase db dump --schema public --file artifacts/supabase/schema.sql

echo "[2/4] Dump public data (COPY format) -> artifacts/supabase/data_public.sql"
rm -f artifacts/supabase/data_public.sql
supabase db dump --data-only --schema public --use-copy --file artifacts/supabase/data_public.sql

echo "[3/4] Extract registry tables -> artifacts/supabase/registries.sql"
python3 - <<'PY'
import pathlib, re

src = pathlib.Path("artifacts/supabase/data_public.sql").read_text(encoding="utf-8", errors="replace").splitlines(True)

targets = {"public.event_kind_registry", "public.event_kind_versions"}
out = []
i = 0
while i < len(src):
    line = src[i]
    m = re.match(r"^COPY\s+([^\s]+)\s+\(", line)
    if m:
        table = m.group(1)
        block = [line]
        i += 1
        while i < len(src):
            block.append(src[i])
            if src[i].strip() == r"\.":
                i += 1
                break
            i += 1
        if table in targets:
            out.extend(block)
        continue
    i += 1

pathlib.Path("artifacts/supabase/registries.sql").write_text("".join(out), encoding="utf-8")
PY

echo "[4/4] Write schema hash -> artifacts/supabase/schema.hash.txt"
python3 - <<'PY'
import hashlib, pathlib
p = pathlib.Path("artifacts/supabase/schema.sql")
h = hashlib.sha256(p.read_bytes()).hexdigest()
pathlib.Path("artifacts/supabase/schema.hash.txt").write_text(h + "\n")
print("schema.sha256", h)
PY

echo "Done."
