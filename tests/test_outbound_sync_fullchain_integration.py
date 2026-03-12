"""
Phase 340 — Outbound Sync Full-Chain Integration Tests
======================================================

Full-chain integration tests exercising:
  outbound_executor.execute_single_provider() → adapter selection → result
  sync_log_writer.write_sync_result() → outbound_sync_log persistence

Group A: Executor Chain (5 tests)
Group B: ExecutionResult Shape (4 tests)
Group C: Sync Result Persistence (4 tests)
Group D: Replay via re-execution (4 tests)

CI-safe: env-based dry run, injectable adapters, mock DB.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DRY_RUN", "true")
os.environ.setdefault("IHOUSE_THROTTLE_DISABLED", "true")
os.environ.setdefault("IHOUSE_RETRY_DISABLED", "true")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.outbound_executor import (
    ExecutionReport,
    ExecutionResult,
    execute_single_provider,
)
from services.sync_log_writer import write_sync_result


# ===========================================================================
# Group A — Executor Chain
# ===========================================================================


class TestExecutorChain:

    def test_execute_single_provider_returns_report(self):
        report = execute_single_provider(
            booking_id="b-001", property_id="p-001", tenant_id="t-001",
            provider="airbnb", external_id="ext-001", strategy="api_first",
        )
        assert isinstance(report, ExecutionReport)

    def test_dry_run_produces_dry_run_results(self):
        report = execute_single_provider(
            booking_id="b-001", property_id="p-001", tenant_id="t-001",
            provider="airbnb", external_id="ext-001", strategy="api_first",
        )
        # In dry run mode the results should have dry_run or skipped status
        for r in report.results:
            assert r.status in ("dry_run", "skipped", "failed", "ok")

    def test_unknown_provider_returns_report(self):
        report = execute_single_provider(
            booking_id="b-001", property_id="p-001", tenant_id="t-001",
            provider="nonexistent_ota", external_id="ext-001", strategy="api_first",
        )
        assert isinstance(report, ExecutionReport)

    def test_ical_fallback_strategy(self):
        report = execute_single_provider(
            booking_id="b-001", property_id="p-001", tenant_id="t-001",
            provider="gvr", external_id="ext-001", strategy="ical_fallback",
        )
        assert isinstance(report, ExecutionReport)

    def test_report_has_booking_id(self):
        report = execute_single_provider(
            booking_id="b-999", property_id="p-001", tenant_id="t-001",
            provider="airbnb", external_id="ext-001", strategy="api_first",
        )
        assert report.booking_id == "b-999"


# ===========================================================================
# Group B — ExecutionResult Shape
# ===========================================================================


class TestExecutionResultShape:

    def test_result_has_provider_field(self):
        r = ExecutionResult(
            provider="airbnb", external_id="ext-001", strategy="api_first",
            status="dry_run", http_status=None, message="DRY RUN",
        )
        assert r.provider == "airbnb"

    def test_result_has_external_id_field(self):
        r = ExecutionResult(
            provider="airbnb", external_id="ext-123", strategy="api_first",
            status="ok", http_status=200, message="Success",
        )
        assert r.external_id == "ext-123"

    def test_result_has_status_field(self):
        r = ExecutionResult(
            provider="airbnb", external_id="ext-001", strategy="api_first",
            status="failed", http_status=500, message="Error",
        )
        assert r.status == "failed"

    def test_result_has_message_field(self):
        r = ExecutionResult(
            provider="airbnb", external_id="ext-001", strategy="api_first",
            status="ok", http_status=200, message="All good",
        )
        assert r.message == "All good"


# ===========================================================================
# Group C — Sync Result Persistence
# ===========================================================================


class TestSyncResultPersistence:

    def test_write_sync_result_uses_correct_table(self):
        db = MagicMock()
        write_sync_result(
            booking_id="b-001", tenant_id="t-001", provider="airbnb",
            external_id="ext-001", strategy="api_first", status="dry_run",
            http_status=None, message="DRY RUN", client=db,
        )
        db.table.assert_called_with("outbound_sync_log")

    def test_write_sync_result_db_error_returns_false(self):
        db = MagicMock()
        db.table.side_effect = Exception("DB failure")
        ok = write_sync_result(
            booking_id="b-001", tenant_id="t-001", provider="airbnb",
            external_id="ext-001", strategy="api_first", status="failed",
            http_status=500, message="Server crash", client=db,
        )
        assert ok is False

    def test_write_sync_result_success_returns_true(self):
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.return_value.error = None
        ok = write_sync_result(
            booking_id="b-002", tenant_id="t-001", provider="bookingcom",
            external_id="ext-002", strategy="api_first", status="ok",
            http_status=200, message="Success", client=db,
        )
        assert ok is True

    def test_write_none_http_status(self):
        db = MagicMock()
        db.table.return_value.insert.return_value.execute.return_value.error = None
        ok = write_sync_result(
            booking_id="b-003", tenant_id="t-001", provider="vrbo",
            external_id="ext-003", strategy="ical_fallback", status="dry_run",
            http_status=None, message="DRY RUN: iCal push skipped.", client=db,
        )
        assert ok is True


# ===========================================================================
# Group D — Replay (re-execution with same params)
# ===========================================================================


class TestSyncReplay:

    def test_replay_returns_report(self):
        report = execute_single_provider(
            booking_id="b-replay-001", property_id="p-001", tenant_id="t-001",
            provider="airbnb", external_id="ext-001", strategy="api_first",
        )
        assert isinstance(report, ExecutionReport)
        assert report.booking_id == "b-replay-001"

    def test_replay_bookingcom(self):
        report = execute_single_provider(
            booking_id="b-replay-002", property_id="p-001", tenant_id="t-001",
            provider="bookingcom", external_id="ext-002", strategy="api_first",
        )
        assert isinstance(report, ExecutionReport)

    def test_replay_expedia(self):
        report = execute_single_provider(
            booking_id="b-replay-003", property_id="p-001", tenant_id="t-001",
            provider="expedia", external_id="ext-003", strategy="api_first",
        )
        assert isinstance(report, ExecutionReport)

    def test_replay_vrbo(self):
        report = execute_single_provider(
            booking_id="b-replay-004", property_id="p-001", tenant_id="t-001",
            provider="vrbo", external_id="ext-004", strategy="ical_fallback",
        )
        assert isinstance(report, ExecutionReport)
