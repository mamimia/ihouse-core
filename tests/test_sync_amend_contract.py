"""
Phase 155 — Contract Tests: API-first Amendment Push

Tests:
  A — AirbnbAdapter.amend() dry-run (no API key)
  B — AirbnbAdapter.amend() real HTTP 200 via PATCH
  C — AirbnbAdapter.amend() HTTP 500 → failed
  D — BookingComAdapter.amend() dry-run (no API key)
  E — BookingComAdapter.amend() real HTTP 204
  F — BookingComAdapter.amend() HTTP 404 → failed
  G — ExpediaVrboAdapter.amend() dry-run (no API key)
  H — ExpediaVrboAdapter.amend() vrbo sub-provider
  I — ExpediaVrboAdapter.amend() HTTP 200
  J — amend_sync_trigger: api_first provider amend path
  K — amend_sync_trigger: ical_fallback provider still works
  L — amend_sync_trigger: unknown provider → skipped
  M — amend_sync_trigger: mixed api + ical channels
  N — _to_iso() date format helper
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("IHOUSE_THROTTLE_DISABLED", "true")
os.environ.setdefault("IHOUSE_RETRY_DISABLED", "true")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_httpx_resp(status: int, body: str = '{"ok": true}'):
    resp = MagicMock()
    resp.status_code = status
    resp.text = body
    return resp


# ===========================================================================
# Group A — AirbnbAdapter.amend() dry-run
# ===========================================================================

class TestGroupA_AirbnbAmend_DryRun:

    def test_a1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().amend("listing-123", "bk-a1",
                                       check_in="2025-06-01", check_out="2025-06-05")
        assert result.status == "dry_run"

    def test_a2_dry_run_flag_returns_dry_run(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().amend("listing-123", "bk-a2", dry_run=True)
        assert result.status == "dry_run"

    def test_a3_global_dry_run_env(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        from importlib import reload
        import adapters.outbound.airbnb_adapter as m
        reload(m)
        result = m.AirbnbAdapter().amend("listing-123", "bk-a3")
        assert result.status == "dry_run"
        monkeypatch.delenv("IHOUSE_DRY_RUN")

    def test_a4_dry_run_provider_is_airbnb(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().amend("listing-abc", "bk-a4")
        assert result.provider == "airbnb"

    def test_a5_message_contains_phase(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().amend("listing-abc", "bk-a5")
        assert "155" in result.message or "dry-run" in result.message


# ===========================================================================
# Group B — AirbnbAdapter.amend() HTTP 200 via PATCH
# ===========================================================================

class TestGroupB_AirbnbAmend_Http200:

    def test_b1_http_200_returns_ok(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().amend("listing-123", "bk-b1",
                                           check_in="2025-06-01", check_out="2025-06-05")
        assert result.status == "ok"
        assert result.http_status == 200

    def test_b2_http_204_returns_ok(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().amend("listing-123", "bk-b2")
        assert result.status == "ok"

    def test_b3_uses_patch_method(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            AirbnbAdapter().amend("listing-123", "bk-b3")
        mock_httpx.patch.assert_called_once()
        mock_httpx.post.assert_not_called()
        mock_httpx.delete.assert_not_called()


# ===========================================================================
# Group C — AirbnbAdapter.amend() HTTP error → failed
# ===========================================================================

class TestGroupC_AirbnbAmend_HttpError:

    def test_c1_http_500_returns_failed(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(500)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().amend("listing-123", "bk-c1")
        assert result.status == "failed"

    def test_c2_http_422_returns_failed(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(422)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().amend("listing-123", "bk-c2")
        assert result.status == "failed"
        assert "422" in result.message


# ===========================================================================
# Group D — BookingComAdapter.amend() dry-run
# ===========================================================================

class TestGroupD_BookingComAmend_DryRun:

    def test_d1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().amend("hotel-456", "bk-d1",
                                           check_in="2025-07-01", check_out="2025-07-05")
        assert result.status == "dry_run"

    def test_d2_dry_run_flag(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().amend("hotel-456", "bk-d2", dry_run=True)
        assert result.status == "dry_run"

    def test_d3_provider_is_bookingcom(self, monkeypatch):
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().amend("hotel-456", "bk-d3")
        assert result.provider == "bookingcom"


# ===========================================================================
# Group E — BookingComAdapter.amend() HTTP 204
# ===========================================================================

class TestGroupE_BookingComAmend_Http:

    def test_e1_http_204_returns_ok(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            result = BookingComAdapter().amend("hotel-456", "bk-e1",
                                              check_in="2025-07-01", check_out="2025-07-05")
        assert result.status == "ok"
        assert result.http_status == 204

    def test_e2_uses_patch_not_post(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            BookingComAdapter().amend("hotel-456", "bk-e2")
        mock_httpx.patch.assert_called_once()
        mock_httpx.post.assert_not_called()


# ===========================================================================
# Group F — BookingComAdapter.amend() HTTP error → failed
# ===========================================================================

class TestGroupF_BookingComAmend_HttpError:

    def test_f1_http_404_returns_failed(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(404)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            result = BookingComAdapter().amend("hotel-456", "bk-f1")
        assert result.status == "failed"
        assert "404" in result.message


# ===========================================================================
# Group G — ExpediaVrboAdapter.amend() dry-run
# ===========================================================================

class TestGroupG_ExpediaAmend_DryRun:

    def test_g1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").amend("prop-789", "bk-g1",
                                                      check_in="2025-08-01",
                                                      check_out="2025-08-05")
        assert result.status == "dry_run"

    def test_g2_dry_run_flag(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").amend("prop-789", "bk-g2", dry_run=True)
        assert result.status == "dry_run"

    def test_g3_provider_label_is_expedia(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").amend("prop-789", "bk-g3")
        assert result.provider == "expedia"


# ===========================================================================
# Group H — ExpediaVrboAdapter vrbo sub-provider
# ===========================================================================

class TestGroupH_VrboAmend_DryRun:

    def test_h1_vrbo_no_key_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("vrbo").amend("prop-vrbo", "bk-h1")
        assert result.status == "dry_run"

    def test_h2_vrbo_provider_label(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("vrbo").amend("prop-vrbo", "bk-h2")
        assert result.provider == "vrbo"


# ===========================================================================
# Group I — ExpediaVrboAdapter.amend() HTTP 200
# ===========================================================================

class TestGroupI_ExpediaAmend_Http:

    def test_i1_http_200_returns_ok(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
            result = ExpediaVrboAdapter("expedia").amend("prop-789", "bk-i1",
                                                         check_in="2025-08-01",
                                                         check_out="2025-08-05")
        assert result.status == "ok"

    def test_i2_uses_patch_method(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.patch.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
            ExpediaVrboAdapter("expedia").amend("prop-789", "bk-i2")
        mock_httpx.patch.assert_called_once()


# ===========================================================================
# Group J — amend_sync_trigger: api_first path
# ===========================================================================

class TestGroupJ_TriggerApiPath:

    def test_j1_airbnb_channel_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-j1",
            property_id="prop-1",
            tenant_id="t-j",
            check_in="2025-09-01",
            check_out="2025-09-05",
            channels=[{"provider": "airbnb", "external_id": "listing-j1", "sync_strategy": "api_first"}],
        )
        assert len(results) == 1
        assert results[0].status == "dry_run"
        assert results[0].provider == "airbnb"

    def test_j2_bookingcom_channel_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-j2",
            property_id="prop-1",
            tenant_id="t-j",
            channels=[{"provider": "bookingcom", "external_id": "hotel-j2", "sync_strategy": "api_first"}],
        )
        assert results[0].status == "dry_run"
        assert results[0].provider == "bookingcom"

    def test_j3_expedia_channel_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-j3",
            property_id="prop-1",
            tenant_id="t-j",
            channels=[{"provider": "expedia", "external_id": "prop-j3", "sync_strategy": "api_first"}],
        )
        assert results[0].provider == "expedia"
        assert results[0].status == "dry_run"

    def test_j4_vrbo_channel_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-j4",
            property_id="prop-1",
            tenant_id="t-j",
            channels=[{"provider": "vrbo", "external_id": "prop-j4", "sync_strategy": "api_first"}],
        )
        assert results[0].provider == "vrbo"
        assert results[0].status == "dry_run"


# ===========================================================================
# Group K — amend_sync_trigger: ical_fallback path still works
# ===========================================================================

class TestGroupK_TriggerIcalPath:

    def test_k1_hotelbeds_ical_uses_ical_adapter(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-k1",
            property_id="prop-1",
            tenant_id="t-k",
            check_in="2025-10-01",
            check_out="2025-10-05",
            channels=[{
                "provider": "hotelbeds",
                "external_id": "ext-k1",
                "sync_strategy": "ical_fallback",
                "timezone": "Asia/Bangkok",
            }],
        )
        assert results[0].provider == "hotelbeds"
        assert results[0].status in ("dry_run", "ok", "failed")
        monkeypatch.delenv("IHOUSE_DRY_RUN")


# ===========================================================================
# Group L — amend_sync_trigger: unknown provider → skipped
# ===========================================================================

class TestGroupL_TriggerUnknown:

    def test_l1_unknown_provider_skipped(self):
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-l1",
            property_id="prop-1",
            tenant_id="t-l",
            channels=[{"provider": "UNKNOWN_OTA", "external_id": "ext-l1", "sync_strategy": "api_first"}],
        )
        assert results[0].status == "skipped"
        assert results[0].provider == "UNKNOWN_OTA"

    def test_l2_missing_provider_skipped(self):
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-l2",
            property_id="prop-1",
            tenant_id="t-l",
            channels=[{"provider": "", "external_id": "ext-l2", "sync_strategy": "api_first"}],
        )
        assert results[0].status == "skipped"

    def test_l3_empty_channels_empty_result(self):
        from services.amend_sync_trigger import fire_amend_sync
        results = fire_amend_sync(
            booking_id="bk-l3",
            property_id="prop-1",
            tenant_id="t-l",
            channels=[],
        )
        assert results == []


# ===========================================================================
# Group M — amend_sync_trigger: mixed channels
# ===========================================================================

class TestGroupM_TriggerMixed:

    def test_m1_two_channels_two_results(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        from services.amend_sync_trigger import fire_amend_sync
        channels = [
            {"provider": "airbnb",    "external_id": "listing-m1", "sync_strategy": "api_first"},
            {"provider": "hotelbeds", "external_id": "ext-m1",     "sync_strategy": "ical_fallback"},
        ]
        results = fire_amend_sync(
            booking_id="bk-m1",
            property_id="prop-1",
            tenant_id="t-m",
            channels=channels,
        )
        assert len(results) == 2
        monkeypatch.delenv("IHOUSE_DRY_RUN")

    def test_m2_all_four_api_providers(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from services.amend_sync_trigger import fire_amend_sync
        channels = [
            {"provider": "airbnb",    "external_id": "a1", "sync_strategy": "api_first"},
            {"provider": "bookingcom","external_id": "b1", "sync_strategy": "api_first"},
            {"provider": "expedia",   "external_id": "e1", "sync_strategy": "api_first"},
            {"provider": "vrbo",      "external_id": "v1", "sync_strategy": "api_first"},
        ]
        results = fire_amend_sync(
            booking_id="bk-m2",
            property_id="prop-1",
            tenant_id="t-m",
            channels=channels,
        )
        providers = {r.provider for r in results}
        assert {"airbnb", "bookingcom", "expedia", "vrbo"} == providers


# ===========================================================================
# Group N — _to_iso() date helper
# ===========================================================================

class TestGroupN_ToIso:

    def test_n1_iso_passthrough(self):
        from services.amend_sync_trigger import _to_iso
        assert _to_iso("2025-06-01") == "2025-06-01"

    def test_n2_compact_to_iso(self):
        from services.amend_sync_trigger import _to_iso
        assert _to_iso("20250601") == "2025-06-01"

    def test_n3_none_returns_none(self):
        from services.amend_sync_trigger import _to_iso
        assert _to_iso(None) is None

    def test_n4_empty_string_returns_none(self):
        from services.amend_sync_trigger import _to_iso
        assert _to_iso("") is None
