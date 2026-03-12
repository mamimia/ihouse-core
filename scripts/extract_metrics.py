#!/usr/bin/env python3
"""
scripts/extract_metrics.py — Phase 353
=======================================

Auto-extracts live system metrics from the codebase and test suite.
Outputs a JSON report that can be compared against current-snapshot.md.

Usage:
    python scripts/extract_metrics.py
    python scripts/extract_metrics.py --output docs/core/metrics-report.json

Metrics extracted:
  - test_file_count     : number of test files
  - src_file_count      : number of source files
  - route_count         : number of registered FastAPI routes
  - adapter_count       : number of OTA adapters in registry
  - outbound_adapter_count : number of outbound adapters in registry
  - phase_spec_count    : number of closed phase specs in docs/archive/phases/
  - current_phase       : last closed phase number (from phase-timeline.md)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
SYS_SRC = ROOT / "src"
sys.path.insert(0, str(SYS_SRC))


def count_test_files(root: Path) -> int:
    tests_dir = root / "tests"
    return len([
        f for f in tests_dir.rglob("test_*.py")
    ])


def count_src_files(root: Path) -> int:
    src_dir = root / "src"
    return len(list(src_dir.rglob("*.py")))


def count_routes(root: Path) -> int:
    os.environ.setdefault("IHOUSE_ENV", "test")
    os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
    os.environ.setdefault("SUPABASE_KEY", "test-key")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    try:
        from main import app
        return len([
            r for r in app.routes if hasattr(r, "methods")
        ])
    except Exception as e:
        return -1


def count_ota_adapters(root: Path) -> int:
    try:
        from adapters.ota.registry import _REGISTRY
        return len(_REGISTRY)
    except Exception:
        try:
            from adapters.ota.registry import get_adapter
            # Count unique entries (not aliases)
            from adapters.ota import registry as reg_mod
            raw = getattr(reg_mod, "_REGISTRY", None) or {}
            return len(raw)
        except Exception:
            return -1


def count_outbound_adapters(root: Path) -> int:
    try:
        from adapters.outbound.registry import build_adapter_registry
        return len(build_adapter_registry())
    except Exception:
        return -1


def count_phase_specs(root: Path) -> int:
    phases_dir = root / "docs" / "archive" / "phases"
    return len(list(phases_dir.glob("phase-*.md")))


def extract_current_phase(root: Path) -> int:
    timeline = root / "docs" / "core" / "phase-timeline.md"
    if not timeline.exists():
        return -1
    content = timeline.read_text(encoding="utf-8")
    import re
    numbers = re.findall(r"Phase (\d+).*?\(Closed\)", content, re.IGNORECASE)
    return max((int(n) for n in numbers), default=-1)


def main():
    parser = argparse.ArgumentParser(description="Extract iHouse Core metrics")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    args = parser.parse_args()

    root = ROOT
    metrics = {
        "test_file_count": count_test_files(root),
        "src_file_count": count_src_files(root),
        "route_count": count_routes(root),
        "outbound_adapter_count": count_outbound_adapters(root),
        "phase_spec_count": count_phase_specs(root),
        "current_phase": extract_current_phase(root),
    }

    report = json.dumps(metrics, indent=2)
    print(report)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"\nReport written to {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
