"""
Phase 139 — Real Outbound Adapter Contract Tests

Four adapter test suites:
  1. AirbnbAdapter (.send)
  2. BookingComAdapter (.send)
  3. ExpediaVrboAdapter (.send)
  4. ICalPushAdapter (.push)

Plus registry tests:
  5. adapter_registry — build_adapter_registry() correctness

ADAPTER CONTRACT RULES (applies to all):
  - With no credentials (env vars absent) → status=dry_run
  - With IHOUSE_DRY_RUN=true → status=dry_run regardless of credentials
  - With dry_run=True arg → status=dry_run
  - OK HTTP response (200/201/204) → status=ok
  - Non-2xx HTTP response → status=failed
  - Network exception → status=failed (no raise)
  - AdapterResult has: provider, external_id, strategy, status, http_status, message
  - provider field matches adapter's provider attribute
  - strategy field matches the call type (api_first or ical_fallback)
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from adapters.outbound import AdapterResult
from adapters.outbound.airbnb_adapter import AirbnbAdapter
from adapters.outbound.bookingcom_adapter import BookingComAdapter
from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
from adapters.outbound.ical_push_adapter import ICalPushAdapter
from adapters.outbound.registry import build_adapter_registry, get_adapter

_BOOKING = "bk-phase139-001"
_EXT     = "EXT-139"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_env(*keys: str):
    """Remove adapter keys from environment for isolation."""
    return patch.dict("os.environ", {k: "" for k in keys}, clear=False)


def _mock_httpx(status: int, text: str = "ok") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    mock_httpx = MagicMock()
    mock_httpx.post.return_value = resp
    mock_httpx.put.return_value  = resp
    return mock_httpx


# ===========================================================================
# AirbnbAdapter
# ===========================================================================

class TestAirbnbAdapter:
    def test_dry_run_when_no_credentials(self):
        with _clean_env("AIRBNB_API_KEY"):
            r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "dry_run"
        assert r.strategy == "api_first"
        assert r.provider == "airbnb"

    def test_dry_run_when_global_ihouse_dry_run(self):
        with patch.dict("os.environ", {"IHOUSE_DRY_RUN": "true", "AIRBNB_API_KEY": "key"}):
            r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "dry_run"

    def test_dry_run_when_arg_true(self):
        with patch.dict("os.environ", {"AIRBNB_API_KEY": "key"}):
            r = AirbnbAdapter().send(_EXT, _BOOKING, dry_run=True)
        assert r.status == "dry_run"

    def test_ok_on_200(self):
        with patch.dict("os.environ", {"AIRBNB_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.airbnb_adapter.httpx", _mock_httpx(200)):
                r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "ok"
        assert r.http_status == 200

    def test_ok_on_204(self):
        with patch.dict("os.environ", {"AIRBNB_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.airbnb_adapter.httpx", _mock_httpx(204)):
                r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "ok"
        assert r.http_status == 204

    def test_failed_on_4xx(self):
        with patch.dict("os.environ", {"AIRBNB_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.airbnb_adapter.httpx", _mock_httpx(403, "Forbidden")):
                r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "failed"
        assert r.http_status == 403

    def test_failed_on_network_exception(self):
        mock_httpx = MagicMock()
        mock_httpx.post.side_effect = RuntimeError("connection refused")
        with patch.dict("os.environ", {"AIRBNB_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
                r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert r.status == "failed"
        assert r.http_status is None

    def test_result_fields_present(self):
        with _clean_env("AIRBNB_API_KEY"):
            r = AirbnbAdapter().send(_EXT, _BOOKING)
        assert hasattr(r, "provider")
        assert hasattr(r, "external_id")
        assert hasattr(r, "strategy")
        assert hasattr(r, "status")
        assert hasattr(r, "http_status")
        assert hasattr(r, "message")

    def test_external_id_propagated(self):
        with _clean_env("AIRBNB_API_KEY"):
            r = AirbnbAdapter().send("MYEXT-123", _BOOKING)
        assert r.external_id == "MYEXT-123"


# ===========================================================================
# BookingComAdapter
# ===========================================================================

class TestBookingComAdapter:
    def test_dry_run_no_credentials(self):
        with _clean_env("BOOKINGCOM_API_KEY"):
            r = BookingComAdapter().send(_EXT, _BOOKING)
        assert r.status == "dry_run"
        assert r.provider == "bookingcom"
        assert r.strategy == "api_first"

    def test_dry_run_global_flag(self):
        with patch.dict("os.environ", {"IHOUSE_DRY_RUN": "true", "BOOKINGCOM_API_KEY": "key"}):
            r = BookingComAdapter().send(_EXT, _BOOKING)
        assert r.status == "dry_run"

    def test_ok_on_201(self):
        with patch.dict("os.environ", {"BOOKINGCOM_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.bookingcom_adapter.httpx", _mock_httpx(201)):
                r = BookingComAdapter().send(_EXT, _BOOKING)
        assert r.status == "ok"

    def test_failed_on_500(self):
        with patch.dict("os.environ", {"BOOKINGCOM_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.bookingcom_adapter.httpx", _mock_httpx(500, "Internal error")):
                r = BookingComAdapter().send(_EXT, _BOOKING)
        assert r.status == "failed"

    def test_failed_on_exception(self):
        m = MagicMock(); m.post.side_effect = RuntimeError("timeout")
        with patch.dict("os.environ", {"BOOKINGCOM_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.bookingcom_adapter.httpx", m):
                r = BookingComAdapter().send(_EXT, _BOOKING)
        assert r.status == "failed"


# ===========================================================================
# ExpediaVrboAdapter
# ===========================================================================

class TestExpediaVrboAdapter:
    def test_expedia_dry_run_no_credentials(self):
        with _clean_env("EXPEDIA_API_KEY"):
            r = ExpediaVrboAdapter(provider="expedia").send(_EXT, _BOOKING)
        assert r.status == "dry_run"
        assert r.provider == "expedia"

    def test_vrbo_dry_run_no_credentials(self):
        with _clean_env("EXPEDIA_API_KEY"):
            r = ExpediaVrboAdapter(provider="vrbo").send(_EXT, _BOOKING)
        assert r.status == "dry_run"
        assert r.provider == "vrbo"

    def test_expedia_ok_on_200(self):
        with patch.dict("os.environ", {"EXPEDIA_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.expedia_vrbo_adapter.httpx", _mock_httpx(200)):
                r = ExpediaVrboAdapter(provider="expedia").send(_EXT, _BOOKING)
        assert r.status == "ok"

    def test_expedia_failed_on_401(self):
        with patch.dict("os.environ", {"EXPEDIA_API_KEY": "key", "IHOUSE_DRY_RUN": "false"}):
            with patch("adapters.outbound.expedia_vrbo_adapter.httpx", _mock_httpx(401, "Unauthorized")):
                r = ExpediaVrboAdapter(provider="expedia").send(_EXT, _BOOKING)
        assert r.status == "failed"
        assert r.http_status == 401

    def test_global_dry_run_overrides(self):
        with patch.dict("os.environ", {"IHOUSE_DRY_RUN": "true", "EXPEDIA_API_KEY": "key"}):
            r = ExpediaVrboAdapter(provider="vrbo").send(_EXT, _BOOKING)
        assert r.status == "dry_run"


# ===========================================================================
# ICalPushAdapter
# ===========================================================================

class TestICalPushAdapter:
    def test_hotelbeds_dry_run_no_url(self):
        with _clean_env("HOTELBEDS_ICAL_URL"):
            r = ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING)
        assert r.status == "dry_run"
        assert r.provider == "hotelbeds"
        assert r.strategy == "ical_fallback"

    def test_tripadvisor_dry_run(self):
        with _clean_env("TRIPADVISOR_ICAL_URL"):
            r = ICalPushAdapter(provider="tripadvisor").push(_EXT, _BOOKING)
        assert r.status == "dry_run"

    def test_despegar_dry_run(self):
        with _clean_env("DESPEGAR_ICAL_URL"):
            r = ICalPushAdapter(provider="despegar").push(_EXT, _BOOKING)
        assert r.status == "dry_run"

    def test_ok_on_200_put(self):
        with patch.dict("os.environ", {
            "HOTELBEDS_ICAL_URL": "https://ical.hotelbeds.com",
            "IHOUSE_DRY_RUN": "false",
        }):
            with patch("adapters.outbound.ical_push_adapter.httpx", _mock_httpx(200)):
                r = ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING)
        assert r.status == "ok"
        assert r.http_status == 200

    def test_ok_on_204(self):
        with patch.dict("os.environ", {
            "TRIPADVISOR_ICAL_URL": "https://ical.tripadvisor.com",
            "IHOUSE_DRY_RUN": "false",
        }):
            with patch("adapters.outbound.ical_push_adapter.httpx", _mock_httpx(204)):
                r = ICalPushAdapter(provider="tripadvisor").push(_EXT, _BOOKING)
        assert r.status == "ok"

    def test_failed_on_403(self):
        with patch.dict("os.environ", {
            "DESPEGAR_ICAL_URL": "https://ical.despegar.com",
            "IHOUSE_DRY_RUN": "false",
        }):
            with patch("adapters.outbound.ical_push_adapter.httpx", _mock_httpx(403)):
                r = ICalPushAdapter(provider="despegar").push(_EXT, _BOOKING)
        assert r.status == "failed"

    def test_global_dry_run_overrides(self):
        with patch.dict("os.environ", {
            "IHOUSE_DRY_RUN": "true",
            "HOTELBEDS_ICAL_URL": "https://ical.hotelbeds.com",
        }):
            r = ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING)
        assert r.status == "dry_run"

    def test_failed_on_exception(self):
        m = MagicMock(); m.put.side_effect = RuntimeError("DNS error")
        with patch.dict("os.environ", {
            "HOTELBEDS_ICAL_URL": "https://ical.hotelbeds.com",
            "IHOUSE_DRY_RUN": "false",
        }):
            with patch("adapters.outbound.ical_push_adapter.httpx", m):
                r = ICalPushAdapter(provider="hotelbeds").push(_EXT, _BOOKING)
        assert r.status == "failed"
        assert r.http_status is None

    def test_external_id_in_result(self):
        with _clean_env("HOTELBEDS_ICAL_URL"):
            r = ICalPushAdapter(provider="hotelbeds").push("HOTEL-999", _BOOKING)
        assert r.external_id == "HOTEL-999"


# ===========================================================================
# Adapter Registry
# ===========================================================================

class TestAdapterRegistry:
    def test_registry_has_airbnb(self):
        reg = build_adapter_registry()
        assert "airbnb" in reg

    def test_registry_has_bookingcom(self):
        reg = build_adapter_registry()
        assert "bookingcom" in reg

    def test_registry_has_expedia(self):
        reg = build_adapter_registry()
        assert "expedia" in reg

    def test_registry_has_vrbo(self):
        reg = build_adapter_registry()
        assert "vrbo" in reg

    def test_registry_has_hotelbeds(self):
        reg = build_adapter_registry()
        assert "hotelbeds" in reg

    def test_registry_has_tripadvisor(self):
        reg = build_adapter_registry()
        assert "tripadvisor" in reg

    def test_registry_has_despegar(self):
        reg = build_adapter_registry()
        assert "despegar" in reg

    def test_get_adapter_returns_none_for_unknown(self):
        assert get_adapter("nonexistent-ota") is None

    def test_airbnb_is_airbnb_adapter(self):
        reg = build_adapter_registry()
        assert isinstance(reg["airbnb"], AirbnbAdapter)

    def test_hotelbeds_is_ical_adapter(self):
        reg = build_adapter_registry()
        assert isinstance(reg["hotelbeds"], ICalPushAdapter)

    def test_expedia_adapter_provider_set(self):
        reg = build_adapter_registry()
        assert reg["expedia"].provider == "expedia"

    def test_vrbo_adapter_provider_set(self):
        reg = build_adapter_registry()
        assert reg["vrbo"].provider == "vrbo"
