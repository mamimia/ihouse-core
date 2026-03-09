"""
Phase 143 — Contract Tests: Idempotency Key on Outbound Requests

Tests per group:

  Group A — _build_idempotency_key() unit (helper directly)
  Group B — Airbnb adapter header propagation
  Group C — Booking.com adapter header propagation
  Group D — Expedia / VRBO adapter header propagation
  Group E — iCal Push adapter header propagation

Key invariants tested:
  - Format: {booking_id}:{external_id}:{YYYYMMDD}
  - Day-stable: two calls within the same UTC day share the same key
  - Header present on every real HTTP call
  - Header absent on dry-run calls (no HTTP call at all)
  - Empty booking_id / external_id: key still produced (best-effort), warning logged
"""
from __future__ import annotations

import os
from datetime import date
from typing import List
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_resp(status_code: int) -> MagicMock:
    r = MagicMock()
    r.status_code = status_code
    r.text = f"body-{status_code}"
    return r


def _env_real(monkeypatch, extra: dict | None = None) -> None:
    monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "true")
    monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "true")
    monkeypatch.setenv("IHOUSE_DRY_RUN", "false")
    for k, v in (extra or {}).items():
        monkeypatch.setenv(k, v)


def _captured_headers(mock_httpx_method) -> dict:
    """Extract the headers kwarg from the first call to mock_httpx.post / .put."""
    return mock_httpx_method.call_args[1]["headers"]


# ===========================================================================
# Group A — _build_idempotency_key() unit
# ===========================================================================

class TestBuildIdempotencyKeyUnit:

    def test_format_contains_three_parts(self):
        """Key format: booking_id:external_id:YYYYMMDD."""
        import adapters.outbound as mod
        key = mod._build_idempotency_key("bk-abc", "EXT-123")
        parts = key.split(":")
        assert len(parts) == 3
        assert parts[0] == "bk-abc"
        assert parts[1] == "EXT-123"
        assert len(parts[2]) == 8       # YYYYMMDD
        assert parts[2].isdigit()

    def test_date_matches_today(self):
        """The date segment matches today's date in YYYYMMDD format."""
        import adapters.outbound as mod
        key = mod._build_idempotency_key("bk-1", "ext-1")
        today_str = date.today().strftime("%Y%m%d")
        assert key.endswith(f":{today_str}")

    def test_same_call_within_day_produces_identical_key(self):
        """Two calls with same args on the same day return identical keys."""
        import adapters.outbound as mod
        k1 = mod._build_idempotency_key("bk-1", "ext-1")
        k2 = mod._build_idempotency_key("bk-1", "ext-1")
        assert k1 == k2

    def test_different_booking_ids_produce_different_keys(self):
        import adapters.outbound as mod
        k1 = mod._build_idempotency_key("bk-1", "ext-1")
        k2 = mod._build_idempotency_key("bk-2", "ext-1")
        assert k1 != k2

    def test_different_external_ids_produce_different_keys(self):
        import adapters.outbound as mod
        k1 = mod._build_idempotency_key("bk-1", "ext-1")
        k2 = mod._build_idempotency_key("bk-1", "ext-2")
        assert k1 != k2

    def test_empty_booking_id_still_returns_string(self):
        """Empty booking_id: key is still produced (best-effort)."""
        import adapters.outbound as mod
        key = mod._build_idempotency_key("", "ext-1")
        assert isinstance(key, str)
        assert ":ext-1:" in key

    def test_empty_external_id_still_returns_string(self):
        """Empty external_id: key is still produced (best-effort)."""
        import adapters.outbound as mod
        key = mod._build_idempotency_key("bk-1", "")
        assert isinstance(key, str)
        assert "bk-1::" in key

    def test_empty_inputs_log_warning(self, caplog):
        """Empty inputs trigger a warning log."""
        import adapters.outbound as mod
        import logging
        with caplog.at_level(logging.WARNING):
            mod._build_idempotency_key("", "")
        assert any("empty" in r.message.lower() for r in caplog.records)

    def test_key_day_rollover_produces_different_key(self, monkeypatch):
        """Monkeypatching _date.today simulates day rollover → different key."""
        import adapters.outbound as mod

        # Patch the _date used inside _build_idempotency_key
        fake_date = MagicMock()
        fake_date.today.return_value.strftime.return_value = "20260101"
        monkeypatch.setattr(mod, "_date", fake_date)
        k1 = mod._build_idempotency_key("bk-1", "ext-1")

        fake_date.today.return_value.strftime.return_value = "20260102"
        k2 = mod._build_idempotency_key("bk-1", "ext-1")

        assert k1 != k2
        assert k1.endswith(":20260101")
        assert k2.endswith(":20260102")


# ===========================================================================
# Group B — Airbnb adapter header
# ===========================================================================

class TestAirbnbIdempotencyKey:

    def test_header_present_on_real_call(self, monkeypatch):
        """X-Idempotency-Key header is attached to real httpx.post call."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            AirbnbAdapter().send("EXT-1", "bk-1")

        headers = _captured_headers(mock_httpx.post)
        assert "X-Idempotency-Key" in headers

    def test_header_format(self, monkeypatch):
        """X-Idempotency-Key has correct format bk-1:EXT-1:YYYYMMDD."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            AirbnbAdapter().send("EXT-1", "bk-1")

        key = _captured_headers(mock_httpx.post)["X-Idempotency-Key"]
        parts = key.split(":")
        assert parts[0] == "bk-1"
        assert parts[1] == "EXT-1"
        assert len(parts[2]) == 8 and parts[2].isdigit()

    def test_header_stable_on_retry(self, monkeypatch):
        """Same idempotency key is used across retry attempts (same day)."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch, {"AIRBNB_API_KEY": "k", "AIRBNB_API_BASE": "http://x"})
        monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "false")  # enable retry
        import adapters.outbound as base_mod
        monkeypatch.setattr(base_mod.time, "sleep", lambda _: None)

        mock_httpx = MagicMock()
        mock_httpx.post.side_effect = [_mock_resp(500), _mock_resp(500), _mock_resp(500), _mock_resp(200)]
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "ok"
        keys = [c[1]["headers"]["X-Idempotency-Key"] for c in mock_httpx.post.call_args_list]
        assert len(set(keys)) == 1   # all 4 calls used the same key

    def test_no_http_call_on_dry_run(self, monkeypatch):
        """Dry-run: no httpx.post call → no header to check."""
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        _env_real(monkeypatch)   # no AIRBNB_API_KEY → dry run

        mock_httpx = MagicMock()
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            r = AirbnbAdapter().send("EXT-1", "bk-1")

        assert r.status == "dry_run"
        mock_httpx.post.assert_not_called()


# ===========================================================================
# Group C — Booking.com adapter header
# ===========================================================================

class TestBookingComIdempotencyKey:

    def test_header_present(self, monkeypatch):
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch, {"BOOKINGCOM_API_KEY": "bk", "BOOKINGCOM_API_BASE": "http://b"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            BookingComAdapter().send("HOTEL-1", "bk-2")

        headers = _captured_headers(mock_httpx.post)
        assert "X-Idempotency-Key" in headers

    def test_header_format(self, monkeypatch):
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch, {"BOOKINGCOM_API_KEY": "bk", "BOOKINGCOM_API_BASE": "http://b"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            BookingComAdapter().send("HOTEL-1", "bk-2")

        key = _captured_headers(mock_httpx.post)["X-Idempotency-Key"]
        parts = key.split(":")
        assert parts[0] == "bk-2"
        assert parts[1] == "HOTEL-1"

    def test_dry_run_no_http(self, monkeypatch):
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        _env_real(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            r = BookingComAdapter().send("HOTEL-1", "bk-2")

        assert r.status == "dry_run"
        mock_httpx.post.assert_not_called()


# ===========================================================================
# Group D — Expedia / VRBO adapter header
# ===========================================================================

class TestExpediaVrboIdempotencyKey:

    def test_expedia_header_present(self, monkeypatch):
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch, {"EXPEDIA_API_KEY": "ek", "EXPEDIA_API_BASE": "http://e"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            ExpediaVrboAdapter("expedia").send("PROP-1", "bk-3")

        assert "X-Idempotency-Key" in _captured_headers(mock_httpx.post)

    def test_vrbo_header_present(self, monkeypatch):
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch, {"EXPEDIA_API_KEY": "vk", "EXPEDIA_API_BASE": "http://v"})

        mock_httpx = MagicMock()
        mock_httpx.post.return_value = _mock_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            ExpediaVrboAdapter("vrbo").send("PROP-2", "bk-4")

        assert "X-Idempotency-Key" in _captured_headers(mock_httpx.post)

    def test_dry_run_no_http(self, monkeypatch):
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        _env_real(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            r = ExpediaVrboAdapter("expedia").send("PROP-1", "bk-3")

        assert r.status == "dry_run"
        mock_httpx.post.assert_not_called()


# ===========================================================================
# Group E — iCal adapter header
# ===========================================================================

class TestICalIdempotencyKey:

    def test_header_present(self, monkeypatch):
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"HOTELBEDS_ICAL_URL": "http://hb"})

        mock_httpx = MagicMock()
        mock_httpx.put.return_value = _mock_resp(200)
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert "X-Idempotency-Key" in _captured_headers(mock_httpx.put)

    def test_header_format(self, monkeypatch):
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {"HOTELBEDS_ICAL_URL": "http://hb"})

        mock_httpx = MagicMock()
        mock_httpx.put.return_value = _mock_resp(200)
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        key = _captured_headers(mock_httpx.put)["X-Idempotency-Key"]
        parts = key.split(":")
        assert parts[0] == "bk-5"
        assert parts[1] == "EXT-HB"
        assert len(parts[2]) == 8

    def test_header_present_alongside_auth(self, monkeypatch):
        """When api_key is also set, both Authorization and X-Idempotency-Key are present."""
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch, {
            "HOTELBEDS_ICAL_URL": "http://hb",
            "HOTELBEDS_API_KEY":  "secret",
        })

        mock_httpx = MagicMock()
        mock_httpx.put.return_value = _mock_resp(204)
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        hdrs = _captured_headers(mock_httpx.put)
        assert "X-Idempotency-Key" in hdrs
        assert "Authorization" in hdrs

    def test_dry_run_no_http(self, monkeypatch):
        from adapters.outbound.ical_push_adapter import ICalPushAdapter
        _env_real(monkeypatch)

        mock_httpx = MagicMock()
        with patch("adapters.outbound.ical_push_adapter.httpx", mock_httpx):
            r = ICalPushAdapter("hotelbeds").push("EXT-HB", "bk-5")

        assert r.status == "dry_run"
        mock_httpx.put.assert_not_called()
