"""
Phase 141 — Rate-Limit Enforcement Contract Tests

Tests that `_throttle(rate_limit)` is:
  - Called with the correct sleep duration on the REAL HTTP path
  - NOT called on the dry-run path (no credentials, IHOUSE_DRY_RUN=true, dry_run=True arg)
  - A no-op when IHOUSE_THROTTLE_DISABLED=true
  - A no-op when rate_limit <= 0 (best-effort, warning logged instead)

All groups use monkeypatching of `adapters.outbound.time.sleep` so no real
sleep occurs during tests. IHOUSE_THROTTLE_DISABLED is NOT set so tests
exercise the real throttle path.

Groups:
  A — _throttle() unit tests (direct invocation)
  B — AirbnbAdapter throttle wiring
  C — BookingComAdapter throttle wiring
  D — ExpediaVrboAdapter throttle wiring
  E — ICalPushAdapter throttle wiring
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

import adapters.outbound as outbound_module
from adapters.outbound import _throttle
from adapters.outbound.airbnb_adapter import AirbnbAdapter
from adapters.outbound.bookingcom_adapter import BookingComAdapter
from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
from adapters.outbound.ical_push_adapter import ICalPushAdapter

_BOOKING = "bk-phase141-001"
_EXT = "EXT-141"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_httpx(status: int, text: str = "ok") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    mock = MagicMock()
    mock.post.return_value = resp
    mock.put.return_value = resp
    return mock


def _capture_sleep(monkeypatch) -> list[float]:
    """Monkeypatch time.sleep in the outbound base module and return capture list."""
    calls: list[float] = []
    monkeypatch.setattr(outbound_module.time, "sleep", calls.append)
    return calls


def _enable_throttle(monkeypatch) -> None:
    """Ensure IHOUSE_THROTTLE_DISABLED is not set (default on)."""
    monkeypatch.delenv("IHOUSE_THROTTLE_DISABLED", raising=False)


# ===========================================================================
# Group A — _throttle() unit tests
# ===========================================================================

class TestThrottleUnit:
    def test_rate_limit_60_sleeps_one_second(self, monkeypatch):
        _enable_throttle(monkeypatch)
        calls = _capture_sleep(monkeypatch)
        _throttle(60)
        assert len(calls) == 1
        assert abs(calls[0] - 1.0) < 0.001

    def test_rate_limit_120_sleeps_half_second(self, monkeypatch):
        _enable_throttle(monkeypatch)
        calls = _capture_sleep(monkeypatch)
        _throttle(120)
        assert len(calls) == 1
        assert abs(calls[0] - 0.5) < 0.001

    def test_rate_limit_30_sleeps_two_seconds(self, monkeypatch):
        _enable_throttle(monkeypatch)
        calls = _capture_sleep(monkeypatch)
        _throttle(30)
        assert len(calls) == 1
        assert abs(calls[0] - 2.0) < 0.001

    def test_rate_limit_zero_no_sleep(self, monkeypatch):
        _enable_throttle(monkeypatch)
        calls = _capture_sleep(monkeypatch)
        _throttle(0)
        assert calls == []

    def test_rate_limit_negative_no_sleep(self, monkeypatch):
        _enable_throttle(monkeypatch)
        calls = _capture_sleep(monkeypatch)
        _throttle(-10)
        assert calls == []

    def test_rate_limit_zero_logs_warning(self, monkeypatch, caplog):
        _enable_throttle(monkeypatch)
        _capture_sleep(monkeypatch)
        with caplog.at_level(logging.WARNING, logger="adapters.outbound"):
            _throttle(0)
        assert any("non-positive" in r.message for r in caplog.records)

    def test_throttle_disabled_env_no_sleep(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "true")
        calls = _capture_sleep(monkeypatch)
        _throttle(60)
        assert calls == []

    def test_throttle_disabled_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "TRUE")
        calls = _capture_sleep(monkeypatch)
        _throttle(60)
        assert calls == []


# ===========================================================================
# Group B — AirbnbAdapter throttle wiring
# ===========================================================================

class TestAirbnbThrottle:
    def test_throttle_called_on_real_call(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("AIRBNB_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.airbnb_adapter.httpx", _mock_httpx(200)):
            AirbnbAdapter().send(_EXT, _BOOKING, rate_limit=60)
        assert len(calls) == 1
        assert abs(calls[0] - 1.0) < 0.001

    def test_throttle_respects_rate_limit_arg(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("AIRBNB_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.airbnb_adapter.httpx", _mock_httpx(200)):
            AirbnbAdapter().send(_EXT, _BOOKING, rate_limit=120)
        assert len(calls) == 1
        assert abs(calls[0] - 0.5) < 0.001

    def test_no_throttle_in_dry_run_no_credentials(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("AIRBNB_API_KEY", "")              # triggers dry_run
        calls = _capture_sleep(monkeypatch)
        AirbnbAdapter().send(_EXT, _BOOKING, rate_limit=60)
        assert calls == []

    def test_no_throttle_when_global_dry_run(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("AIRBNB_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        calls = _capture_sleep(monkeypatch)
        AirbnbAdapter().send(_EXT, _BOOKING, rate_limit=60)
        assert calls == []

    def test_no_throttle_when_dry_run_arg_true(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("AIRBNB_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        AirbnbAdapter().send(_EXT, _BOOKING, rate_limit=60, dry_run=True)
        assert calls == []


# ===========================================================================
# Group C — BookingComAdapter throttle wiring
# ===========================================================================

class TestBookingComThrottle:
    def test_throttle_called_on_real_call(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.bookingcom_adapter.httpx", _mock_httpx(200)):
            BookingComAdapter().send(_EXT, _BOOKING, rate_limit=60)
        assert len(calls) == 1
        assert abs(calls[0] - 1.0) < 0.001

    def test_no_throttle_in_dry_run(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "")
        calls = _capture_sleep(monkeypatch)
        BookingComAdapter().send(_EXT, _BOOKING, rate_limit=60)
        assert calls == []


# ===========================================================================
# Group D — ExpediaVrboAdapter throttle wiring
# ===========================================================================

class TestExpediaVrboThrottle:
    def test_throttle_called_on_real_expedia_call(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("EXPEDIA_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", _mock_httpx(200)):
            ExpediaVrboAdapter(provider="expedia").send(_EXT, _BOOKING, rate_limit=60)
        assert len(calls) == 1
        assert abs(calls[0] - 1.0) < 0.001

    def test_throttle_called_on_real_vrbo_call(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("EXPEDIA_API_KEY", "key")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", _mock_httpx(200)):
            ExpediaVrboAdapter(provider="vrbo").send(_EXT, _BOOKING, rate_limit=30)
        assert len(calls) == 1
        assert abs(calls[0] - 2.0) < 0.001

    def test_no_throttle_in_dry_run(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("EXPEDIA_API_KEY", "")
        calls = _capture_sleep(monkeypatch)
        ExpediaVrboAdapter(provider="expedia").send(_EXT, _BOOKING, rate_limit=60)
        assert calls == []


# ===========================================================================
# Group E — ICalPushAdapter throttle wiring
# ===========================================================================

class TestICalThrottle:
    def test_throttle_called_on_real_ical_push(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://ical.hotelbeds.com")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.ical_push_adapter.httpx", _mock_httpx(200)):
            ICalPushAdapter(provider="hotelbeds").push(
                _EXT, _BOOKING, rate_limit=10
            )
        assert len(calls) == 1
        assert abs(calls[0] - 6.0) < 0.001   # 60s / 10rpm = 6s

    def test_throttle_works_for_tripadvisor(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("TRIPADVISOR_ICAL_URL", "https://ical.tripadvisor.com")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
        calls = _capture_sleep(monkeypatch)
        with patch("adapters.outbound.ical_push_adapter.httpx", _mock_httpx(200)):
            ICalPushAdapter(provider="tripadvisor").push(
                _EXT, _BOOKING, rate_limit=20
            )
        assert len(calls) == 1
        assert abs(calls[0] - 3.0) < 0.001   # 60s / 20rpm = 3s

    def test_no_throttle_in_dry_run(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "")   # triggers dry_run
        calls = _capture_sleep(monkeypatch)
        ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING, rate_limit=10)
        assert calls == []

    def test_no_throttle_global_dry_run(self, monkeypatch):
        _enable_throttle(monkeypatch)
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://ical.hotelbeds.com")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        calls = _capture_sleep(monkeypatch)
        ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING, rate_limit=10)
        assert calls == []
