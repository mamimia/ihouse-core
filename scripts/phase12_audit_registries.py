#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[1]
KIND_PATH = REPO / "src/core/kind_registry.core.json"
EXEC_PATH = REPO / "src/core/skill_exec_registry.core.json"


def _load_json(p: Path) -> Dict[str, str]:
    raw = p.read_text(encoding="utf-8")
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise SystemExit(f"AUDIT_FAIL {p.name} not an object")
    out: Dict[str, str] = {}
    for k, v in obj.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise SystemExit(f"AUDIT_FAIL {p.name} keys/values must be strings")
        out[k] = v
    return out


def _module_file_exists(module_path: str) -> bool:
    parts = module_path.split(".")
    p = REPO / "src"
    for part in parts[:-1]:
        p = p / part
    return (p / (parts[-1] + ".py")).exists()


def main() -> int:
    kinds = _load_json(KIND_PATH)
    execs = _load_json(EXEC_PATH)

    routed_skills = sorted(set(kinds.values()))
    exec_skills = sorted(execs.keys())

    missing_exec: List[str] = sorted([s for s in routed_skills if s not in execs])
    extra_exec: List[str] = sorted([s for s in exec_skills if s not in set(routed_skills)])
    missing_modules: List[str] = sorted(
        [k for k, v in execs.items() if not _module_file_exists(v)]
    )

    # NEW: ensure every core skill module lives under src/core/skills/**/skill.py
    missing_skillpy: List[str] = []
    for skill_name, module_path in execs.items():
        parts = module_path.split(".")
        if len(parts) >= 4 and parts[0] == "core" and parts[1] == "skills":
            skill_dir = REPO / "src" / "core" / "skills" / parts[2]
            skill_py = skill_dir / "skill.py"
            if not skill_py.exists():
                missing_skillpy.append(skill_name)

    missing_skillpy = sorted(missing_skillpy)

    if missing_exec or extra_exec or missing_modules or missing_skillpy:
        print("AUDIT_FAIL")
        print("MISSING_EXEC_FOR_ROUTED_SKILLS", missing_exec)
        print("EXTRA_EXEC_NOT_ROUTED", extra_exec)
        print("MISSING_CORE_MODULES", missing_modules)
        print("MISSING_CORE_SKILLPY", missing_skillpy)
        return 2

    print("AUDIT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
