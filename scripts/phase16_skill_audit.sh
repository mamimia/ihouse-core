#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-src}"
OUTDIR="artifacts/phase16_skill_audit"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$OUTDIR"

echo "Phase16 Skill Audit"
echo "Root: $ROOT"
echo "Out:  $OUTDIR"
echo "UTC:  $TS"
echo

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep (rg) not found. Install it first."
  exit 1
fi

PATTERN='datetime\.now|time\.time|time\.sleep|uuid\.uuid4|random\.|os\.environ|getenv\(|requests\.|httpx\.|supabase|sqlite|connect\(|open\(|subprocess|socket|aiohttp|boto3|redis|pymongo'

rg -n --hidden --glob '!**/.venv/**' --glob "$ROOT/**" -S "$PATTERN" "$ROOT" \
  | tee "$OUTDIR/suspect_calls_${TS}.txt" >/dev/null

rg -n --hidden --glob '!**/.venv/**' --glob "$ROOT/**" -S 'payload\s*\[|payload\.' "$ROOT" \
  | tee "$OUTDIR/payload_access_${TS}.txt" >/dev/null

rg -n --hidden --glob '!**/.venv/**' --glob "$ROOT/**" -S 'state\s*\[|state\.|mutat|update\(|setdefault\(' "$ROOT" \
  | tee "$OUTDIR/state_mutation_${TS}.txt" >/dev/null

rg -n --hidden --glob '!**/.venv/**' --glob "$ROOT/**" -S 'class\s+.*Skill|def\s+.*skill|skills?/' "$ROOT" \
  | tee "$OUTDIR/skill_surfaces_${TS}.txt" >/dev/null

cat > "$OUTDIR/README_${TS}.txt" <<EOF
Phase 16 audit outputs

1) suspect_calls_${TS}.txt
Possible nondeterminism or IO inside core.

2) payload_access_${TS}.txt
Direct payload coupling surfaces.

3) state_mutation_${TS}.txt
Potential mutation or implicit writes.

4) skill_surfaces_${TS}.txt
Entry points and locations to review.

Next step:
We will classify each hit into: Pure, Mostly Pure, Coupled
Then define minimal refactors that remove coupling without adding new execution surfaces.
EOF

echo
echo "Done."
echo "Open: $OUTDIR"
