"""
Phase 41 — Contract tests for DLQ Alerting Threshold.

Verifies that:
1. threshold not exceeded → exceeded=False, no stderr warning
2. threshold exceeded → exceeded=True, WARNING emitted to stderr
3. boundary case (pending == threshold) → exceeded=True
4. zero pending → never exceeded
5. default threshold reads from DLQ_ALERT_THRESHOLD env var
6. invalid env var falls back to default (10)
7. DLQAlertResult fields are correct in all cases
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_inspector_with_count(count: int) -> MagicMock:
    """Return a mock that patches get_pending_count to return `count`."""
    return count


# ---------------------------------------------------------------------------
# check_dlq_threshold
# ---------------------------------------------------------------------------

class TestCheckDlqThreshold:

    def _run(self, pending: int, threshold: int, capsys=None):
        from adapters.ota.dlq_alerting import check_dlq_threshold
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=pending):
            result = check_dlq_threshold(threshold=threshold)
        return result, (capsys.readouterr() if capsys else None)

    def test_not_exceeded_returns_ok(self) -> None:
        result, _ = self._run(pending=3, threshold=10)
        assert result.exceeded is False
        assert result.pending_count == 3
        assert result.threshold == 10
        assert "[DLQ OK]" in result.message

    def test_exceeded_returns_exceeded(self) -> None:
        result, _ = self._run(pending=15, threshold=10)
        assert result.exceeded is True
        assert result.pending_count == 15
        assert result.threshold == 10
        assert "[DLQ ALERT]" in result.message

    def test_boundary_equal_to_threshold_is_exceeded(self) -> None:
        """pending == threshold must be treated as exceeded."""
        result, _ = self._run(pending=10, threshold=10)
        assert result.exceeded is True

    def test_zero_pending_never_exceeded(self) -> None:
        result, _ = self._run(pending=0, threshold=1)
        assert result.exceeded is False

    def test_exceeded_emits_warning_to_stderr(self, capsys) -> None:
        result, captured = self._run(pending=11, threshold=5, capsys=capsys)
        assert result.exceeded is True
        assert "[DLQ ALERT]" in captured.err
        assert "pending=11" in captured.err

    def test_not_exceeded_does_not_emit_to_stderr(self, capsys) -> None:
        result, captured = self._run(pending=4, threshold=10, capsys=capsys)
        assert result.exceeded is False
        assert "[DLQ ALERT]" not in captured.err

    def test_message_contains_pending_and_threshold(self) -> None:
        result, _ = self._run(pending=7, threshold=10)
        assert "pending=7" in result.message or "7" in result.message
        assert "threshold=10" in result.message or "10" in result.message

    def test_result_is_frozen_dataclass(self) -> None:
        """DLQAlertResult must be immutable."""
        from adapters.ota.dlq_alerting import DLQAlertResult
        r = DLQAlertResult(pending_count=5, threshold=10, exceeded=False, message="ok")
        with pytest.raises((AttributeError, TypeError)):
            r.exceeded = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# check_dlq_threshold_default — env var
# ---------------------------------------------------------------------------

class TestCheckDlqThresholdDefault:

    def test_reads_threshold_from_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("DLQ_ALERT_THRESHOLD", "5")
        from adapters.ota.dlq_alerting import check_dlq_threshold_default
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=3):
            result = check_dlq_threshold_default()
        assert result.threshold == 5

    def test_defaults_to_10_when_env_var_missing(self, monkeypatch) -> None:
        monkeypatch.delenv("DLQ_ALERT_THRESHOLD", raising=False)
        from adapters.ota.dlq_alerting import check_dlq_threshold_default
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=0):
            result = check_dlq_threshold_default()
        assert result.threshold == 10

    def test_defaults_to_10_when_env_var_invalid(self, monkeypatch) -> None:
        monkeypatch.setenv("DLQ_ALERT_THRESHOLD", "not_a_number")
        from adapters.ota.dlq_alerting import check_dlq_threshold_default
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=0):
            result = check_dlq_threshold_default()
        assert result.threshold == 10

    def test_defaults_to_10_when_env_var_empty(self, monkeypatch) -> None:
        monkeypatch.setenv("DLQ_ALERT_THRESHOLD", "")
        from adapters.ota.dlq_alerting import check_dlq_threshold_default
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=0):
            result = check_dlq_threshold_default()
        assert result.threshold == 10

    def test_exceeded_when_pending_above_env_threshold(self, monkeypatch) -> None:
        monkeypatch.setenv("DLQ_ALERT_THRESHOLD", "3")
        from adapters.ota.dlq_alerting import check_dlq_threshold_default
        with patch("adapters.ota.dlq_alerting.get_pending_count", return_value=5):
            result = check_dlq_threshold_default()
        assert result.exceeded is True
        assert result.threshold == 3
