"""
Phase 330 — Admin Reconciliation Integration Tests
====================================================

First-ever tests for `api/admin_reconciliation_router.py`.

Group A: Severity Calculation (_severity)
  ✓  0 findings → OK
  ✓  1 finding → MEDIUM
  ✓  2 findings → MEDIUM
  ✓  3 findings → HIGH
  ✓  10 findings → HIGH

Group B: Aggregation by Property (_aggregate_by_property)
  ✓  Single finding → one provider group
  ✓  Multiple findings same provider → single group with count
  ✓  Different providers → separate groups
  ✓  Sorted worst-first (most findings first)
  ✓  kinds list is sorted and de-duplicated

Group C: Count by Kind (_count_by_kind)
  ✓  Empty list → empty dict
  ✓  Multiple findings same kind → count > 1
  ✓  Multiple different kinds → separate keys

CI-safe: pure function tests, no DB, no network.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.admin_reconciliation_router import (
    _aggregate_by_property,
    _count_by_kind,
    _severity,
)
from adapters.ota.reconciliation_model import ReconciliationFinding, ReconciliationFindingKind


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding(
    kind: ReconciliationFindingKind = ReconciliationFindingKind.FINANCIAL_FACTS_MISSING,
    booking_id: str = "airbnb_B001",
    provider: str = "airbnb",
) -> ReconciliationFinding:
    return ReconciliationFinding.build(
        kind=kind,
        booking_id=booking_id,
        provider=provider,
        tenant_id="t-1",
        description="Test finding",
        detected_at="2026-03-12T10:00:00Z",
    )


# ---------------------------------------------------------------------------
# Group A — Severity Calculation
# ---------------------------------------------------------------------------

class TestSeverityCalculation:

    def test_zero_findings_is_ok(self):
        assert _severity(0) == "OK"

    def test_one_finding_is_medium(self):
        assert _severity(1) == "MEDIUM"

    def test_two_findings_is_medium(self):
        assert _severity(2) == "MEDIUM"

    def test_three_findings_is_high(self):
        assert _severity(3) == "HIGH"

    def test_ten_findings_is_high(self):
        assert _severity(10) == "HIGH"


# ---------------------------------------------------------------------------
# Group B — Aggregation by Property
# ---------------------------------------------------------------------------

class TestAggregateByProperty:

    def test_single_finding_produces_one_group(self):
        findings = [_finding()]
        result = _aggregate_by_property(findings)
        assert len(result) == 1
        assert result[0]["provider"] == "airbnb"
        assert result[0]["findings_count"] == 1

    def test_multiple_findings_same_provider_grouped(self):
        findings = [
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B001"),
            _finding(kind=ReconciliationFindingKind.STALE_BOOKING, booking_id="B002"),
        ]
        result = _aggregate_by_property(findings)
        assert len(result) == 1
        assert result[0]["findings_count"] == 2

    def test_different_providers_separate_groups(self):
        findings = [
            _finding(provider="airbnb", booking_id="airbnb_B001"),
            _finding(provider="booking_com", booking_id="booking_com_B002"),
        ]
        result = _aggregate_by_property(findings)
        assert len(result) == 2
        providers = {r["provider"] for r in result}
        assert providers == {"airbnb", "booking_com"}

    def test_sorted_worst_first(self):
        findings = [
            _finding(provider="low", booking_id="low_B001"),                        # 1 finding
            _finding(provider="high", booking_id="high_B001"),                      # 3 findings
            _finding(provider="high", booking_id="high_B001", kind=ReconciliationFindingKind.STALE_BOOKING),
            _finding(provider="high", booking_id="high_B002", kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING),
        ]
        result = _aggregate_by_property(findings)
        assert result[0]["provider"] == "high"
        assert result[0]["findings_count"] == 3
        assert result[-1]["provider"] == "low"

    def test_kinds_deduplicated_and_sorted(self):
        findings = [
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B001"),
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B002"),  # same kind
            _finding(kind=ReconciliationFindingKind.STALE_BOOKING, booking_id="B003"),
        ]
        result = _aggregate_by_property(findings)
        kinds = result[0]["kinds"]
        assert len(kinds) == len(set(kinds))  # no duplicates
        assert kinds == sorted(kinds)  # sorted


# ---------------------------------------------------------------------------
# Group C — Count by Kind
# ---------------------------------------------------------------------------

class TestCountByKind:

    def test_empty_list_returns_empty_dict(self):
        assert _count_by_kind([]) == {}

    def test_multiple_same_kind_counted(self):
        findings = [
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B001"),
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B002"),
        ]
        result = _count_by_kind(findings)
        assert result[ReconciliationFindingKind.FINANCIAL_FACTS_MISSING.value] == 2

    def test_different_kinds_separate_keys(self):
        findings = [
            _finding(kind=ReconciliationFindingKind.FINANCIAL_FACTS_MISSING, booking_id="B001"),
            _finding(kind=ReconciliationFindingKind.STALE_BOOKING, booking_id="B002"),
        ]
        result = _count_by_kind(findings)
        assert len(result) == 2
        assert all(v == 1 for v in result.values())
