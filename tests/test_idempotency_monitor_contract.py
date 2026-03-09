"""
test_idempotency_monitor_contract.py -- Phase 79

Contract tests for idempotency_monitor.collect_idempotency_report().

All tests inject a mock client so no live Supabase connection is required.

Groups:
  A -- IdempotencyReport field types and structure
  B -- DLQ row classification (pending vs already_applied)
  C -- idempotency_rejection_count
  D -- ordering_buffer_depth
  E -- empty / missing data safe defaults
  F -- IDEMPOTENCY_REJECTION_CODES coverage
"""

from __future__ import annotations

import pytest

from adapters.ota.idempotency_monitor import (
    IDEMPOTENCY_REJECTION_CODES,
    IdempotencyReport,
    _classify_dlq_rows,
    _count_ordering_buffer_waiting,
    collect_idempotency_report,
)


# ---------------------------------------------------------------------------
# Mock client factory
# ---------------------------------------------------------------------------

class _MockTableQuery:
    """Minimal mock that returns a fixed data list on .execute()."""

    def __init__(self, data: list):
        self._data = data

    def select(self, *args, **kwargs):
        return self

    def execute(self):
        class _Resp:
            pass
        r = _Resp()
        r.data = self._data
        return r


class _MockClient:
    """Returns per-table mock queries."""

    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name: str) -> _MockTableQuery:
        return _MockTableQuery(self._tables.get(name, []))


def _client(dlq_rows=None, buffer_rows=None) -> _MockClient:
    return _MockClient({
        "ota_dead_letter": dlq_rows or [],
        "ota_ordering_buffer": buffer_rows or [],
    })


# ---------------------------------------------------------------------------
# Group A -- IdempotencyReport structure
# ---------------------------------------------------------------------------

class TestIdempotencyReportStructure:

    def test_report_is_dataclass_instance(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report, IdempotencyReport)

    def test_total_dlq_rows_is_int(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.total_dlq_rows, int)

    def test_pending_dlq_rows_is_int(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.pending_dlq_rows, int)

    def test_already_applied_count_is_int(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.already_applied_count, int)

    def test_idempotency_rejection_count_is_int(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.idempotency_rejection_count, int)

    def test_ordering_buffer_depth_is_int(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.ordering_buffer_depth, int)

    def test_checked_at_is_str(self):
        report = collect_idempotency_report(client=_client())
        assert isinstance(report.checked_at, str)

    def test_report_is_frozen(self):
        report = collect_idempotency_report(client=_client())
        with pytest.raises((AttributeError, TypeError)):
            report.total_dlq_rows = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Group B -- DLQ row classification
# ---------------------------------------------------------------------------

class TestDlqClassification:

    def test_empty_dlq_all_zeros(self):
        report = collect_idempotency_report(client=_client(dlq_rows=[]))
        assert report.total_dlq_rows == 0
        assert report.pending_dlq_rows == 0
        assert report.already_applied_count == 0

    def test_null_replay_result_counts_as_pending(self):
        rows = [{"replay_result": None, "rejection_code": None}]
        total, pending, applied, _ = _classify_dlq_rows(rows)
        assert total == 1
        assert pending == 1
        assert applied == 0

    def test_applied_replay_result_counts_as_already_applied(self):
        rows = [{"replay_result": "APPLIED", "rejection_code": None}]
        total, pending, applied, _ = _classify_dlq_rows(rows)
        assert total == 1
        assert pending == 0
        assert applied == 1

    def test_already_applied_status(self):
        rows = [{"replay_result": "ALREADY_APPLIED", "rejection_code": None}]
        _, _, applied, _ = _classify_dlq_rows(rows)
        assert applied == 1

    def test_already_exists_status(self):
        rows = [{"replay_result": "ALREADY_EXISTS", "rejection_code": None}]
        _, _, applied, _ = _classify_dlq_rows(rows)
        assert applied == 1

    def test_already_exists_business_status(self):
        rows = [{"replay_result": "ALREADY_EXISTS_BUSINESS", "rejection_code": None}]
        _, _, applied, _ = _classify_dlq_rows(rows)
        assert applied == 1

    def test_mixed_rows_counted_correctly(self):
        rows = [
            {"replay_result": None, "rejection_code": None},
            {"replay_result": "APPLIED", "rejection_code": None},
            {"replay_result": "ALREADY_APPLIED", "rejection_code": None},
            {"replay_result": None, "rejection_code": None},
        ]
        total, pending, applied, _ = _classify_dlq_rows(rows)
        assert total == 4
        assert pending == 2
        assert applied == 2

    def test_total_equals_pending_plus_applied(self):
        rows = [
            {"replay_result": "APPLIED", "rejection_code": None},
            {"replay_result": None, "rejection_code": None},
            {"replay_result": None, "rejection_code": None},
        ]
        total, pending, applied, _ = _classify_dlq_rows(rows)
        assert total == pending + applied


# ---------------------------------------------------------------------------
# Group C -- idempotency_rejection_count
# ---------------------------------------------------------------------------

class TestIdempotencyRejectionCount:

    def test_no_rejections_yields_zero(self):
        rows = [{"replay_result": None, "rejection_code": "BOOKING_NOT_FOUND"}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 0

    def test_already_applied_code_counts(self):
        rows = [{"replay_result": "ALREADY_APPLIED", "rejection_code": "ALREADY_APPLIED"}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 1

    def test_already_exists_code_counts(self):
        rows = [{"replay_result": None, "rejection_code": "ALREADY_EXISTS"}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 1

    def test_already_exists_business_code_counts(self):
        rows = [{"replay_result": None, "rejection_code": "ALREADY_EXISTS_BUSINESS"}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 1

    def test_duplicate_code_counts(self):
        rows = [{"replay_result": None, "rejection_code": "DUPLICATE"}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 1

    def test_none_rejection_code_not_counted(self):
        rows = [{"replay_result": None, "rejection_code": None}]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 0

    def test_multiple_rejection_rows_counted(self):
        rows = [
            {"replay_result": None, "rejection_code": "ALREADY_APPLIED"},
            {"replay_result": None, "rejection_code": "DUPLICATE"},
            {"replay_result": None, "rejection_code": "BOOKING_NOT_FOUND"},
        ]
        _, _, _, rej = _classify_dlq_rows(rows)
        assert rej == 2


# ---------------------------------------------------------------------------
# Group D -- ordering_buffer_depth
# ---------------------------------------------------------------------------

class TestOrderingBufferDepth:

    def test_empty_buffer_yields_zero(self):
        report = collect_idempotency_report(client=_client(buffer_rows=[]))
        assert report.ordering_buffer_depth == 0

    def test_waiting_rows_counted(self):
        rows = [
            {"status": "waiting"},
            {"status": "waiting"},
            {"status": "replayed"},
        ]
        assert _count_ordering_buffer_waiting(rows) == 2

    def test_replayed_rows_not_counted(self):
        rows = [{"status": "replayed"}, {"status": "replayed"}]
        assert _count_ordering_buffer_waiting(rows) == 0

    def test_ordering_depth_via_report(self):
        report = collect_idempotency_report(client=_client(
            buffer_rows=[{"status": "waiting"}, {"status": "replayed"}]
        ))
        assert report.ordering_buffer_depth == 1


# ---------------------------------------------------------------------------
# Group E -- empty / safe defaults
# ---------------------------------------------------------------------------

class TestSafeDefaults:

    def test_empty_everything_yields_all_zeros(self):
        report = collect_idempotency_report(client=_client())
        assert report.total_dlq_rows == 0
        assert report.pending_dlq_rows == 0
        assert report.already_applied_count == 0
        assert report.idempotency_rejection_count == 0
        assert report.ordering_buffer_depth == 0

    def test_checked_at_is_not_empty(self):
        report = collect_idempotency_report(client=_client())
        assert report.checked_at != ""

    def test_checked_at_contains_timezone_indicator(self):
        """checked_at must be UTC ISO string — should contain +00:00 or Z."""
        report = collect_idempotency_report(client=_client())
        assert "+" in report.checked_at or report.checked_at.endswith("Z")


# ---------------------------------------------------------------------------
# Group F -- IDEMPOTENCY_REJECTION_CODES coverage
# ---------------------------------------------------------------------------

class TestRejectionCodeConstants:

    def test_already_applied_in_codes(self):
        assert "ALREADY_APPLIED" in IDEMPOTENCY_REJECTION_CODES

    def test_already_exists_in_codes(self):
        assert "ALREADY_EXISTS" in IDEMPOTENCY_REJECTION_CODES

    def test_already_exists_business_in_codes(self):
        assert "ALREADY_EXISTS_BUSINESS" in IDEMPOTENCY_REJECTION_CODES

    def test_duplicate_in_codes(self):
        assert "DUPLICATE" in IDEMPOTENCY_REJECTION_CODES

    def test_codes_is_frozenset(self):
        assert isinstance(IDEMPOTENCY_REJECTION_CODES, frozenset)
