import json
from pathlib import Path

core = Path("src/core")
kind_p = core / "kind_registry.core.json"
exec_p = core / "skill_exec_registry.core.json"

kind = json.loads(kind_p.read_text(encoding="utf-8"))
exe = json.loads(exec_p.read_text(encoding="utf-8"))

if not isinstance(kind, dict) or not isinstance(exe, dict):
    raise SystemExit("REGISTRY_INVALID_JSON")

kinds = set(kind.values())
missing = sorted([k for k in kinds if k not in exe])

if missing:
    print("REGISTRY_MISMATCH")
    print("Kinds referenced by kind_registry but missing in skill_exec_registry:")
    for k in missing:
        print(k)
    raise SystemExit(1)

print("REGISTRY_OK")
