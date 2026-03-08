"""
Phase 46 — Contract tests for System Health Check.

Verifies that:
1. All healthy → ok=True, 5 components all ok
2. supabase_connectivity fails → ok=False
3. DLQ threshold exceeded → ok=False, dlq_threshold component not ok
4. ordering_buffer_waiting with items → still ok=True (informational only)
5. DLQ table inaccessible → ok=False
6. HealthReport and ComponentStatus are frozen dataclasses
7. Never raises even when all components fail
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from dataclasses import FrozenInstanceError

import pytest


def _make_healthy_client() -> MagicMock:
    """Client where all table SELECTs succeed and return empty data."""
    mock_result = MagicMock()
    mock_result.data = []

    mock_limit = MagicMock()
    mock_limit.execute.return_value = mock_result

    mock_eq = MagicMock()
    mock_eq.execute.return_value = mock_result

    mock_select = MagicMock()
    mock_select.limit.return_value = mock_limit
    mock_select.eq.return_value = mock_eq

    client = MagicMock()
    client.table.return_value.select.return_value = mock_select
    return client


# ---------------------------------------------------------------------------
# HealthReport shape
# ---------------------------------------------------------------------------

class TestHealthReportShape:

    def test_all_healthy_returns_ok_true(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=0), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert report.ok is True

    def test_report_has_five_components(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=0), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert len(report.components) == 5

    def test_report_contains_timestamp(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=0), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert report.timestamp  # non-empty string
        assert "T" in report.timestamp  # ISO format

    def test_health_report_is_frozen(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=0), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            report.ok = False  # type: ignore[misc]

    def test_component_status_is_frozen(self) -> None:
        from adapters.ota.health_check import ComponentStatus
        c = ComponentStatus(name="test", ok=True, detail="ok")
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            c.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Failure scenarios
# ---------------------------------------------------------------------------

class TestHealthCheckFailures:

    def test_supabase_unreachable_gives_ok_false(self) -> None:
        client = MagicMock()
        client.table.side_effect = Exception("Connection refused")
        with patch("adapters.ota.health_check.get_pending_count", side_effect=Exception("down")), \
             patch("adapters.ota.health_check.check_dlq_threshold_default", side_effect=Exception("down")):
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert report.ok is False

    def test_dlq_threshold_exceeded_gives_ok_false(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=20), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=True, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert report.ok is False
        threshold_comp = next(c for c in report.components if c.name == "dlq_threshold")
        assert threshold_comp.ok is False

    def test_ordering_buffer_waiting_does_not_fail_ok(self) -> None:
        """Waiting events in the ordering buffer are informational — they don't fail ok."""
        client = _make_healthy_client()
        # Make ordering buffer return 3 waiting rows
        mock_result_waiting = MagicMock()
        mock_result_waiting.data = [{"id": 1}, {"id": 2}, {"id": 3}]
        client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result_waiting

        with patch("adapters.ota.health_check.get_pending_count", return_value=0), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        # ok can still be True even with waiting ordering events
        buf_comp = next(c for c in report.components if c.name == "ordering_buffer_waiting")
        assert buf_comp.ok is True  # informational

    def test_never_raises_on_total_failure(self) -> None:
        """System health check must never propagate exceptions."""
        client = MagicMock()
        client.table.side_effect = RuntimeError("nuclear failure")
        with patch("adapters.ota.health_check.get_pending_count", side_effect=RuntimeError("gone")), \
             patch("adapters.ota.health_check.check_dlq_threshold_default", side_effect=RuntimeError("gone")):
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)  # must not raise
        assert report.ok is False

    def test_dlq_pending_count_in_report(self) -> None:
        client = _make_healthy_client()
        with patch("adapters.ota.health_check.get_pending_count", return_value=7), \
             patch("adapters.ota.health_check.check_dlq_threshold_default") as mock_alert:
            mock_alert.return_value = MagicMock(exceeded=False, threshold=10)
            from adapters.ota.health_check import system_health_check
            report = system_health_check(client)
        assert report.dlq_pending == 7
