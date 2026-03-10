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

Phase 209 — Groups J, K, L, M, N removed (tested deprecated amend_sync_trigger.py fast-path,
now deleted). Outbound amend sync is handled solely via fire_amended_sync() in
outbound_amended_sync.py through the guaranteed build_sync_plan -> execute_sync_plan path.
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
# Groups J, K, L, M, N — REMOVED in Phase 209
# Tested deprecated amend_sync_trigger.py fast-path (Phase 152/155),
# now deleted. Outbound amend sync uses sole guaranteed path:
# outbound_amended_sync.fire_amended_sync() -> build_sync_plan -> execute_sync_plan.
# ===========================================================================
