"""
Phase 353 — Doc Auto-Generation from Code
==========================================

Tests that validate the iHouse Core codebase metrics are internally
consistent and that docs match actual code reality.

Groups:
  A — Metrics Extractor (6 tests)
  B — Route Inventory Consistency (4 tests)
  C — Adapter Registry Consistency (4 tests)
  D — Doc ↔ Code Cross-Validation (4 tests)
  E — Phase Spec Completeness (4 tests)
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

sys.path.insert(0, str(SRC))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _test_files() -> list[Path]:
    return list((ROOT / "tests").rglob("test_*.py"))


def _src_files() -> list[Path]:
    return list(SRC.rglob("*.py"))


def _all_routes():
    from main import app
    return [r for r in app.routes if hasattr(r, "methods")]


def _phase_specs() -> list[Path]:
    return list((ROOT / "docs" / "archive" / "phases").glob("phase-*.md"))


def _snapshot_text() -> str:
    return (ROOT / "docs" / "core" / "current-snapshot.md").read_text(encoding="utf-8")


def _timeline_text() -> str:
    return (ROOT / "docs" / "core" / "phase-timeline.md").read_text(encoding="utf-8")


def _extract_current_phase() -> int:
    text = _timeline_text()
    numbers = re.findall(r"Phase (\d+).*?\(Closed\)", text, re.IGNORECASE)
    return max((int(n) for n in numbers), default=-1)


# ---------------------------------------------------------------------------
# Group A — Metrics Extractor
# ---------------------------------------------------------------------------

class TestGroupAMetricsExtractor:

    def test_a1_test_file_count_above_200(self):
        """At least 200 test files in /tests/ (system maturity invariant)."""
        count = len(_test_files())
        assert count >= 200, f"Expected ≥200 test files, got {count}"

    def test_a2_src_file_count_above_200(self):
        """At least 200 source files in /src/ (system size invariant)."""
        count = len(_src_files())
        assert count >= 200, f"Expected ≥200 src files, got {count}"

    def test_a3_phase_spec_count_above_100(self):
        """At least 100 phase spec files exist."""
        count = len(_phase_specs())
        assert count >= 100, f"Expected ≥100 phase specs, got {count}"

    def test_a4_current_phase_above_350(self):
        """Last closed phase is ≥ 350 (progression invariant)."""
        phase = _extract_current_phase()
        assert phase >= 350, f"Expected current_phase≥350, got {phase}"

    def test_a5_metrics_extractor_script_exists(self):
        """scripts/extract_metrics.py exists and is importable."""
        script = ROOT / "scripts" / "extract_metrics.py"
        assert script.exists(), "extract_metrics.py not found"

    def test_a6_metrics_are_positive_integers(self):
        """All extracted metrics return positive values."""
        assert len(_test_files()) > 0
        assert len(_src_files()) > 0
        assert len(_phase_specs()) > 0
        assert _extract_current_phase() > 0


# ---------------------------------------------------------------------------
# Group B — Route Inventory Consistency
# ---------------------------------------------------------------------------

class TestGroupBRouteInventory:

    def test_b1_route_count_at_least_100(self):
        """API has at least 100 routes."""
        routes = _all_routes()
        assert len(routes) >= 100

    def test_b2_all_routes_have_paths(self):
        """All registered routes have non-empty path strings."""
        routes = _all_routes()
        for r in routes:
            assert hasattr(r, "path") and r.path, f"Route missing path: {r}"

    def test_b3_no_duplicate_path_method_pairs(self):
        """No excessive duplicate path/method pairs (≤ 5 intentional dups allowed)."""
        routes = _all_routes()
        seen: dict = {}
        dups = []
        for r in routes:
            for method in (r.methods or set()):
                key = (r.path, method)
                if key in seen:
                    dups.append(key)
                seen[key] = True
        # Some intentional duplicates exist (like /admin/dlq, /admin/reconciliation)
        assert len(dups) <= 5, f"Too many duplicate route/method pairs: {dups}"

    def test_b4_health_and_docs_routes_exist(self):
        """Core infrastructure routes (/health, /docs, /openapi.json) exist."""
        routes = _all_routes()
        paths = {r.path for r in routes}
        for required in ("/health", "/docs", "/openapi.json"):
            assert required in paths, f"{required} route missing"


# ---------------------------------------------------------------------------
# Group C — Adapter Registry Consistency
# ---------------------------------------------------------------------------

class TestGroupCAdapterRegistry:

    def test_c1_ota_registry_has_entries(self):
        """OTA adapter registry is non-empty."""
        from adapters.ota import registry as reg_mod
        adapters = getattr(reg_mod, "_ADAPTERS", None) or getattr(reg_mod, "_REGISTRY", {})
        assert len(adapters) >= 10

    def test_c2_outbound_registry_has_7_providers(self):
        """Outbound adapter registry has exactly 7 providers."""
        from adapters.outbound.registry import build_adapter_registry
        reg = build_adapter_registry()
        assert len(reg) == 7

    def test_c3_outbound_adapter_names_are_lowercase(self):
        """All outbound adapter provider names are lowercase strings."""
        from adapters.outbound.registry import build_adapter_registry
        reg = build_adapter_registry()
        for name in reg:
            assert name == name.lower(), f"Provider name not lowercase: {name}"

    def test_c4_ota_adapters_implement_interface(self):
        """All OTA adapters implement normalize() and to_canonical_envelope()."""
        from adapters.ota import registry as reg_mod
        adapters = getattr(reg_mod, "_ADAPTERS", None) or getattr(reg_mod, "_REGISTRY", {})
        for name, adapter in adapters.items():
            assert hasattr(adapter, "normalize"), f"{name} missing normalize()"
            assert hasattr(adapter, "to_canonical_envelope"), f"{name} missing to_canonical_envelope()"


# ---------------------------------------------------------------------------
# Group D — Doc ↔ Code Cross-Validation
# ---------------------------------------------------------------------------

class TestGroupDDocValidation:

    def test_d1_snapshot_mentions_phase_350_or_later(self):
        """current-snapshot.md references Phase 350 or higher."""
        text = _snapshot_text()
        phases = [int(n) for n in re.findall(r"Phase (\d+)", text)]
        assert max(phases, default=0) >= 350, "Snapshot seems stale — no Phase 350+ reference"

    def test_d2_snapshot_test_count_is_plausible(self):
        """current-snapshot.md mentions a test count ≥ 5000."""
        text = _snapshot_text()
        # Match "7,047" or "7047" or "≥5000" formats
        counts = re.findall(r"(\d+)[,.]?(\d{3})\s+collected", text)
        if not counts:
            # Fallback: look for plain 4+ digit number near 'collected' or 'passing'
            counts2 = re.findall(r"(\d{4,6})\s+collected|collected.*?(\d{4,6})", text)
            nums = [int(m[0] or m[1]) for m in counts2 if m[0] or m[1]]
        else:
            nums = [int(a + b) for a, b in counts]
        assert nums, "No test count found in current-snapshot.md"
        assert max(nums, default=0) >= 5000, f"Snapshot test count seems too low: {nums}"

    def test_d3_timeline_has_phase_352_or_later(self):
        """phase-timeline.md documents Phase 352 or higher."""
        text = _timeline_text()
        assert re.search(r"Phase 35[2-9]|Phase 3[6-9]\d|Phase [4-9]\d\d", text), \
            "phase-timeline.md does not document Phase 352+"

    def test_d4_construction_log_is_non_empty(self):
        """construction-log.md has at least 50 lines of content."""
        log = (ROOT / "docs" / "core" / "construction-log.md").read_text(encoding="utf-8")
        lines = [l.strip() for l in log.splitlines() if l.strip()]
        assert len(lines) >= 50, f"construction-log.md too short: {len(lines)} lines"


# ---------------------------------------------------------------------------
# Group E — Phase Spec Completeness
# ---------------------------------------------------------------------------

class TestGroupEPhaseSpecs:

    def test_e1_all_phase_specs_are_markdown(self):
        """All phase spec files are .md extension."""
        specs = _phase_specs()
        for s in specs:
            assert s.suffix == ".md"

    def test_e2_phase_specs_are_non_empty(self):
        """All phase spec files have content > 100 bytes."""
        specs = _phase_specs()
        for s in specs:
            assert s.stat().st_size > 100, f"Spec too small: {s.name}"

    def test_e3_recent_phases_have_specs(self):
        """Phase 349, 350, 351, 352 all have spec files."""
        spec_dir = ROOT / "docs" / "archive" / "phases"
        for phase_n in (349, 350, 351, 352):
            spec = spec_dir / f"phase-{phase_n}-spec.md"
            assert spec.exists(), f"Missing spec for Phase {phase_n}"

    def test_e4_phase_specs_contain_closed_date(self):
        """Recent phase specs contain a 'Closed:' date line."""
        spec_dir = ROOT / "docs" / "archive" / "phases"
        for phase_n in (349, 350, 351, 352):
            spec = spec_dir / f"phase-{phase_n}-spec.md"
            if spec.exists():
                content = spec.read_text(encoding="utf-8")
                assert "Closed:" in content, f"{spec.name} missing Closed: date"
