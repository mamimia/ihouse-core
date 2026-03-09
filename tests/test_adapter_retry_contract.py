"""
Phase 142 — Contract Tests: Retry + Exponential Backoff in Outbound Adapters

Tests per group:

  Group A — _retry_with_backoff() unit (helper directly)
  Group B — Airbnb adapter retry
  Group C — Booking.com adapter retry
  Group D — Expedia / VRBO adapter retry
  Group E — iCal push adapter retry

Environment controls:
  IHOUSE_THROTTLE_DISABLED=true  — used throughout (no real sleep from Phase 141)
  IHOUSE_RETRY_DISABLED          — toggled per-test to exercise enable / disable

Mock pattern:
  _mock_httpx_seq(status_codes) → MagicMock httpx module where successive
  calls return responses with those HTTP status codes in order.
"""
from __future__ import annotations

import sys
import os
import importlib
from typing import List
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _mock_resp(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.text = f"body-{status_code}"
    return r


def _mock_httpx_seq(status_codes: List[int]) -> MagicMock:
    """Return a fake httpx module where post/put return successive HTTP statuses."""
    responses = [_mock_resp(sc) for sc in status_codes]
    m = MagicMock()
    m.post.side_effect = responses
    m.put.side_effect  = responses
    return m


def _capture_sleep(monkeypatch) -> List[float]:
    """Monkeypatch time.sleep in the outbound base module and return the capture list."""
    import adapters.outbound as base_mod
    sleeps: List[float] = []
    monkeypatch.setattr(base_mod.time, "sleep", sleeps.append)
    return sleeps


def _env_real(monkeypatch, extra: dict | None = None) -> None:
    """Set env to 'production-like' (retry enabled, throttle disabled)."""
    monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "true")
    monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
    monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
    for k, v in (extra or {}).items():
        monkeypatch.setenv(k, v)


# ===========================================================================
# Group A — _retry_with_backoff() unit tests
# ===========================================================================

class TestRetryWithBackoffUnit:
    """Direct tests of the _retry_with_backoff helper."""

    def test_immediate_ok_no_sleep(self, monkeypatch):
        """A callable returning 200 succeeds on first try — no sleep."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        result = MagicMock()
        result.http_status = 200
        r = mod._retry_with_backoff(lambda: result)
        assert r is result
        assert sleeps == []

    def test_5xx_then_200_retries_once(self, monkeypatch):
        """5xx on attempt 0 → sleep 1s → retry → 200 → ok."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        r500 = MagicMock(); r500.http_status = 500
        r200 = MagicMock(); r200.http_status = 200
        calls = [r500, r200]
        result = mod._retry_with_backoff(lambda: calls.pop(0))
        assert result is r200
        assert sleeps == [1.0]

    def test_5xx_then_5xx_then_200_retries_twice(self, monkeypatch):
        """Two 5xx → sleep 1s, 4s → 200 → ok."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        items = [500, 500, 200]
        idx = [0]
        def fn():
            r = MagicMock(); r.http_status = items[idx[0]]; idx[0] += 1; return r

        result = mod._retry_with_backoff(fn)
        assert result.http_status == 200
        assert sleeps == [1.0, 4.0]

    def test_three_5xx_exhausts_retries(self, monkeypatch):
        """3 retries (4 total attempts) all 5xx → return last 5xx result."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        idx = [0]
        def fn():
            idx[0] += 1
            r = MagicMock(); r.http_status = 503; return r

        result = mod._retry_with_backoff(fn, max_retries=3)
        assert result.http_status == 503
        assert idx[0] == 4   # 1 initial + 3 retries
        assert sleeps == [1.0, 4.0, 16.0]

    def test_exception_retried_then_succeeds(self, monkeypatch):
        """Network exception on attempt 0 → sleep 1s → 200 ok on attempt 1."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        r200 = MagicMock(); r200.http_status = 200
        calls = [ConnectionError("timeout"), r200]

        def fn():
            v = calls.pop(0)
            if isinstance(v, Exception):
                raise v
            return v

        result = mod._retry_with_backoff(fn)
        assert result is r200
        assert sleeps == [1.0]

    def test_three_exceptions_reraises(self, monkeypatch):
        """Three consecutive exceptions → re-raises after exhausting retries."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        def fn():
            raise ConnectionError("no route to host")

        with pytest.raises(ConnectionError, match="no route to host"):
            mod._retry_with_backoff(fn, max_retries=3)
        assert sleeps == [1.0, 4.0, 16.0]

    def test_4xx_not_retried(self, monkeypatch):
        """4xx (client error) is returned immediately — no retry."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        r401 = MagicMock(); r401.http_status = 401
        result = mod._retry_with_backoff(lambda: r401)
        assert result is r401
        assert sleeps == []

    def test_retry_disabled_no_sleep(self, monkeypatch):
        """IHOUSE_RETRY_DISABLED=true → fn() called once, no retry even on 5xx."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "true")
        sleeps = _capture_sleep(monkeypatch)

        r500 = MagicMock(); r500.http_status = 500
        result = mod._retry_with_backoff(lambda: r500)
        assert result is r500
        assert sleeps == []

    def test_backoff_cap_at_30s(self, monkeypatch):
        """With max_retries=5, delays should cap at 30s."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        idx = [0]
        def fn():
            idx[0] += 1
            r = MagicMock(); r.http_status = 503; return r

        mod._retry_with_backoff(fn, max_retries=5)
        assert idx[0] == 6   # 1 initial + 5 retries
        # pre-sleep before attempts 1-5: 4^0=1, 4^1=4, 4^2=16, 4^3=min(64,30)=30, 4^4=min(256,30)=30
        assert sleeps == [1.0, 4.0, 16.0, 30.0, 30.0]

    def test_none_http_status_not_retried(self, monkeypatch):
        """None http_status (dry_run / no request) → no retry."""
        import adapters.outbound as mod
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")
        sleeps = _capture_sleep(monkeypatch)

        r = MagicMock(); r.http_status = None
        result = mod._retry_with_backoff(lambda: r)
        assert result is r
        assert sleeps == []


# ===========================================================================
# Group B — Airbnb adapter retry
# ===========================================================================

class TestAirbnbRetry:
    """Retry wiring in AirbnbAdapter.send()."""

    def test_5xx_then_200_retries_and_returns_ok(self, monkeypatch):
        """2×500 then 200 → ok; 2 backoff sleeps (1s, 4s)."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 500, 200])
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "ok"
        assert r.http_status == 200
        assert sleeps == [1.0, 4.0]
        assert mock_httpx.post.call_count == 3

    def test_three_5xx_returns_failed(self, monkeypatch):
        """3 retries (4 total attempts) × 5xx → status=failed; 3 backoff sleeps."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        sleeps = _capture_sleep(monkeypatch)

        # 4 attempts: attempt 0,1,2,3 all 5xx → exhausted → return last 5xx
        mock_httpx = _mock_httpx_seq([500, 502, 503, 503])
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "failed"
        assert r.http_status == 503
        assert sleeps == [1.0, 4.0, 16.0]

    def test_4xx_not_retried(self, monkeypatch):
        """401 on first call → returned immediately, no sleep."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([401])
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "failed"
        assert sleeps == []
        assert mock_httpx.post.call_count == 1

    def test_immediate_200_no_retry(self, monkeypatch):
        """Immediate 200 — no retry, no sleep."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([200])
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "ok"
        assert sleeps == []

    def test_network_exception_retried(self, monkeypatch):
        """Connection reset → retry → 200 ok."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        mock_httpx.post.side_effect = [ConnectionError("reset"), _mock_resp(200)]
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "ok"
        assert sleeps == [1.0]

    def test_dry_run_no_retry(self, monkeypatch):
        """Dry-run path never reaches _retry_with_backoff at all."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch)  # no AIRBNB_API_KEY → dry-run
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "dry_run"
        assert sleeps == []
        assert mock_httpx.post.call_count == 0


# ===========================================================================
# Group C — Booking.com adapter retry
# ===========================================================================

class TestBookingComRetry:
    """Retry wiring in BookingComAdapter.send()."""

    def test_5xx_then_200_ok(self, monkeypatch):
        """1×500 then 200 → ok; 1 backoff sleep (1s)."""
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch, {"BOOKINGCOM_API_KEY": "bk", "BOOKINGCOM_API_BASE": "http://b"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 200])
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            r = BookingComAdapter().send("HOTEL-1", "bk-2")

        assert r.status == "ok"
        assert sleeps == [1.0]

    def test_three_5xx_failed(self, monkeypatch):
        """4 total attempts × 5xx → failed, sleeps = [1, 4, 16]."""
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch, {"BOOKINGCOM_API_KEY": "bk", "BOOKINGCOM_API_BASE": "http://b"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 502, 503, 503])
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            r = BookingComAdapter().send("HOTEL-1", "bk-2")

        assert r.status == "failed"
        assert sleeps == [1.0, 4.0, 16.0]

    def test_dry_run_no_retry(self, monkeypatch):
        """No credentials → dry_run, no HTTP, no sleep."""
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch)
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            r = BookingComAdapter().send("HOTEL-1", "bk-2")

        assert r.status == "dry_run"
        assert sleeps == []


# ===========================================================================
# Group D — Expedia / VRBO adapter retry
# ===========================================================================

class TestExpediaVrboRetry:
    """Retry wiring in ExpediaVrboAdapter.send()."""

    def test_expedia_5xx_then_200(self, monkeypatch):
        """Expedia: 1×500 then 200 → ok."""
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch, {"EXPEDIA_API_KEY": "ek", "EXPEDIA_API_BASE": "http://e"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 200])
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            r = ExpediaVrboAdapter("expedia").send("PROP-1", "bk-3")

        assert r.status == "ok"
        assert sleeps == [1.0]
        assert r.provider == "expedia"

    def test_vrbo_5xx_then_200(self, monkeypatch):
        """VRBO (same key): 1×500 then 200 → ok."""
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch, {"EXPEDIA_API_KEY": "vk", "EXPEDIA_API_BASE": "http://v"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 200])
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            r = ExpediaVrboAdapter("vrbo").send("PROP-2", "bk-4")

        assert r.status == "ok"
        assert sleeps == [1.0]
        assert r.provider == "vrbo"

    def test_three_5xx_failed(self, monkeypatch):
        """4 total attempts × 5xx → failed, 3 sleeps."""
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch, {"EXPEDIA_API_KEY": "ek", "EXPEDIA_API_BASE": "http://e"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 502, 503, 503])
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            r = ExpediaVrboAdapter("expedia").send("PROP-1", "bk-3")

        assert r.status == "failed"
        assert sleeps == [1.0, 4.0, 16.0]

    def test_dry_run_no_retry(self, monkeypatch):
        """No credentials → dry_run, no HTTP, no sleep."""
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch)
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            r = ExpediaVrboAdapter("expedia").send("PROP-1", "bk-3")

        assert r.status == "dry_run"
        assert sleeps == []


# ===========================================================================
# Group E — iCal Push adapter retry
# ===========================================================================

class TestICalRetry:
    """Retry wiring in ICalPushAdapter.push()."""

    def test_hotelbeds_5xx_then_200(self, monkeypatch):
        """Hotelbeds: 1×500 then 204 → ok."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"HOTELBEDS_ICAL_URL": "http://hb"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 204])
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert r.status == "ok"
        assert sleeps == [1.0]

    def test_tripadvisor_5xx_then_200(self, monkeypatch):
        """TripAdvisor: 1×503 then 200 → ok."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"TRIPADVISOR_ICAL_URL": "http://ta"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([503, 200])
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("tripadvisor").push("EXT-TA", "bk-6")

        assert r.status == "ok"
        assert sleeps == [1.0]

    def test_three_5xx_failed(self, monkeypatch):
        """4 total attempts × 5xx → failed, sleeps = [1, 4, 16]."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"HOTELBEDS_ICAL_URL": "http://hb"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = _mock_httpx_seq([500, 502, 503, 503])
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert r.status == "failed"
        assert sleeps == [1.0, 4.0, 16.0]

    def test_dry_run_no_retry(self, monkeypatch):
        """No ICAL_URL → dry_run, no HTTP, no sleep."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch)
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert r.status == "dry_run"
        assert sleeps == []

    def test_network_exception_retried(self, monkeypatch):
        """Connection error → retry → 200 ok."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"HOTELBEDS_ICAL_URL": "http://hb"})
        sleeps = _capture_sleep(monkeypatch)

        mock_httpx = MagicMock()
        mock_httpx.put.side_effect = [ConnectionError("timeout"), _mock_resp(200)]
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert r.status == "ok"
        assert sleeps == [1.0]
