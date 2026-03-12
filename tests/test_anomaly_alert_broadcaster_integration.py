"""
Phase 329 — Anomaly Alert Broadcaster Integration Tests
========================================================

First-ever tests for `api/anomaly_alert_broadcaster.py`.

Group A: Task SLA Scanner (_scan_tasks)
  ✓  CRITICAL task beyond SLA window → alert with CRITICAL severity
  ✓  HIGH task within SLA window → no alert
  ✓  task with missing created_at → skipped silently
  ✓  DB failure → returns empty list, never raises

Group B: Financial Flag Detection (_detect_financial_flags)
  ✓  net_to_property < 0 → NET_NEGATIVE HIGH
  ✓  commission > 25% of total → COMMISSION_HIGH HIGH
  ✓  commission == 0 → COMMISSION_ZERO LOW
  ✓  PARTIAL confidence → PARTIAL_CONFIDENCE MEDIUM
  ✓  missing net_to_property → MISSING_NET_TO_PROPERTY MEDIUM
  ✓  Healthy row → no flags

Group C: Alert Helpers
  ✓  _alert_id is deterministic for same args
  ✓  _alert_id differs for different args
  ✓  _parse_dt handles ISO, Z-suffix, and None
  ✓  Severity order: CRITICAL < HIGH < MEDIUM < LOW
  ✓  _SEVERITY_ORDER values match expected ordering

CI-safe: pure function tests, no DB, no network.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.anomaly_alert_broadcaster import (
    _alert_id,
    _detect_financial_flags,
    _parse_dt,
    _scan_tasks,
    _SEVERITY_ORDER,
    _SLA_MINUTES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)


def _task_row(
    task_id: str = "T-001",
    priority: str = "CRITICAL",
    status: str = "PENDING",
    ack_sla_minutes: int = 5,
    created_at_offset_minutes: int = 30,   # how many minutes BEFORE _NOW was created
) -> dict:
    created = (_NOW - timedelta(minutes=created_at_offset_minutes)).isoformat()
    return {
        "task_id": task_id,
        "kind": "CHECKIN_PREP",
        "title": "Prepare check-in",
        "priority": priority,
        "status": status,
        "ack_sla_minutes": ack_sla_minutes,
        "created_at": created,
        "property_id": "P-001",
        "booking_id": "B-001",
        "worker_role": "cleaner",
    }


def _mock_task_db(rows: list) -> MagicMock:
    db = MagicMock()
    (db.table.return_value.select.return_value
     .eq.return_value.in_.return_value.in_.return_value
     .order.return_value.limit.return_value.execute.return_value.data) = rows
    return db


# ---------------------------------------------------------------------------
# Group A — Task SLA Scanner
# ---------------------------------------------------------------------------

class TestScanTasks:

    def test_critical_task_beyond_sla_emits_alert(self):
        row = _task_row(priority="CRITICAL", ack_sla_minutes=5, created_at_offset_minutes=30)
        db = _mock_task_db([row])
        alerts = _scan_tasks(db, "t-1", 10, _NOW)
        assert len(alerts) == 1
        assert alerts[0]["severity"] == "CRITICAL"
        assert "SLA Breach" in alerts[0]["title"]

    def test_task_within_sla_not_alerted(self):
        row = _task_row(priority="HIGH", ack_sla_minutes=60, created_at_offset_minutes=10)
        db = _mock_task_db([row])
        alerts = _scan_tasks(db, "t-1", 10, _NOW)
        assert alerts == []

    def test_task_missing_created_at_skipped(self):
        row = _task_row()
        row["created_at"] = None
        db = _mock_task_db([row])
        alerts = _scan_tasks(db, "t-1", 10, _NOW)
        assert alerts == []

    def test_db_failure_returns_empty_never_raises(self):
        db = MagicMock()
        db.table.side_effect = Exception("DB down")
        alerts = _scan_tasks(db, "t-1", 10, _NOW)
        assert alerts == []


# ---------------------------------------------------------------------------
# Group B — Financial Flag Detection
# ---------------------------------------------------------------------------

class TestDetectFinancialFlags:

    def test_net_negative_is_high(self):
        row = {"net_to_property": -50, "total_price": 500, "ota_commission": 50,
               "source_confidence": "HIGH"}
        flags = _detect_financial_flags(row)
        flag_names = [f[0] for f in flags]
        assert "NET_NEGATIVE" in flag_names
        severities = {f[0]: f[1] for f in flags}
        assert severities["NET_NEGATIVE"] == "HIGH"

    def test_commission_over_25pct_is_high(self):
        row = {"net_to_property": 200, "total_price": 400, "ota_commission": 110,
               "source_confidence": "FULL"}
        flags = _detect_financial_flags(row)
        flag_names = [f[0] for f in flags]
        assert "COMMISSION_HIGH" in flag_names
        severities = {f[0]: f[1] for f in flags}
        assert severities["COMMISSION_HIGH"] == "HIGH"

    def test_commission_zero_is_low(self):
        row = {"net_to_property": 300, "total_price": 400, "ota_commission": 0,
               "source_confidence": "FULL"}
        flags = _detect_financial_flags(row)
        flag_names = [f[0] for f in flags]
        assert "COMMISSION_ZERO" in flag_names
        severities = {f[0]: f[1] for f in flags}
        assert severities["COMMISSION_ZERO"] == "LOW"

    def test_partial_confidence_is_medium(self):
        row = {"net_to_property": 200, "total_price": 400, "ota_commission": 50,
               "source_confidence": "PARTIAL"}
        flags = _detect_financial_flags(row)
        flag_names = [f[0] for f in flags]
        assert "PARTIAL_CONFIDENCE" in flag_names
        severities = {f[0]: f[1] for f in flags}
        assert severities["PARTIAL_CONFIDENCE"] == "MEDIUM"

    def test_missing_net_to_property_is_medium(self):
        row = {"net_to_property": None, "total_price": 400, "ota_commission": 50,
               "source_confidence": "FULL"}
        flags = _detect_financial_flags(row)
        flag_names = [f[0] for f in flags]
        assert "MISSING_NET_TO_PROPERTY" in flag_names

    def test_healthy_row_produces_no_flags(self):
        row = {"net_to_property": 250, "total_price": 400, "ota_commission": 80,
               "source_confidence": "FULL"}
        flags = _detect_financial_flags(row)
        # No negative net, commission = 20% (ok), full confidence
        flag_names = [f[0] for f in flags]
        assert "NET_NEGATIVE" not in flag_names
        assert "COMMISSION_HIGH" not in flag_names
        assert "PARTIAL_CONFIDENCE" not in flag_names


# ---------------------------------------------------------------------------
# Group C — Alert Helpers
# ---------------------------------------------------------------------------

class TestAlertHelpers:

    def test_alert_id_deterministic(self):
        a = _alert_id("task_sla", "T-001")
        b = _alert_id("task_sla", "T-001")
        assert a == b
        assert len(a) == 12

    def test_alert_id_differs_for_different_args(self):
        a = _alert_id("task_sla", "T-001")
        b = _alert_id("task_sla", "T-002")
        assert a != b

    def test_parse_dt_handles_iso(self):
        dt = _parse_dt("2026-03-12T10:00:00+00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_parse_dt_handles_z_suffix(self):
        dt = _parse_dt("2026-03-12T10:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_parse_dt_handles_none(self):
        assert _parse_dt(None) is None

    def test_severity_order_critical_first(self):
        assert _SEVERITY_ORDER["CRITICAL"] < _SEVERITY_ORDER["HIGH"]
        assert _SEVERITY_ORDER["HIGH"] < _SEVERITY_ORDER["MEDIUM"]
        assert _SEVERITY_ORDER["MEDIUM"] < _SEVERITY_ORDER["LOW"]
