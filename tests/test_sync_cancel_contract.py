"""
Phase 154 — Contract Tests: API-first Cancellation Push

Tests:
  A — AirbnbAdapter.cancel() dry-run (no API key)
  B — AirbnbAdapter.cancel() real HTTP 200
  C — AirbnbAdapter.cancel() real HTTP 500 → failed
  D — BookingComAdapter.cancel() dry-run (no API key)
  E — BookingComAdapter.cancel() real HTTP 204
  F — BookingComAdapter.cancel() real HTTP 404 → failed
  G — ExpediaVrboAdapter.cancel() dry-run (no API key)
  H — ExpediaVrboAdapter.cancel() 'vrbo' sub-provider dry-run
  I — ExpediaVrboAdapter.cancel() real HTTP 200
  N — _build_idempotency_key suffix distincts keys

Phase 209 — Groups J, K, L, M removed (tested deprecated cancel_sync_trigger.py fast-path,
now deleted). Outbound cancel sync is handled solely via fire_canceled_sync() in
outbound_canceled_sync.py through the guaranteed build_sync_plan -> execute_sync_plan path.
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
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.text = body
    return mock_resp


# ===========================================================================
# Group A — AirbnbAdapter.cancel() dry-run
# ===========================================================================

class TestGroupA_AirbnbCancel_DryRun:

    def test_a1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().cancel("listing-123", "bk-a1")
        assert result.status == "dry_run"

    def test_a2_dry_run_flag_returns_dry_run(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().cancel("listing-123", "bk-a2", dry_run=True)
        assert result.status == "dry_run"

    def test_a3_global_dry_run_env_returns_dry_run(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        from importlib import reload
        import adapters.outbound.airbnb_adapter as m
        reload(m)
        result = m.AirbnbAdapter().cancel("listing-123", "bk-a3")
        assert result.status == "dry_run"
        monkeypatch.delenv("IHOUSE_DRY_RUN")

    def test_a4_dry_run_provider_is_airbnb(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().cancel("listing-abc", "bk-a4")
        assert result.provider == "airbnb"

    def test_a5_dry_run_message_contains_phase(self, monkeypatch):
        monkeypatch.delenv("AIRBNB_API_KEY", raising=False)
        from adapters.outbound.airbnb_adapter import AirbnbAdapter
        result = AirbnbAdapter().cancel("listing-abc", "bk-a5")
        assert "154" in result.message or "dry-run" in result.message


# ===========================================================================
# Group B — AirbnbAdapter.cancel() HTTP 200
# ===========================================================================

class TestGroupB_AirbnbCancel_Http200:

    def test_b1_http_200_returns_ok(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().cancel("listing-123", "bk-b1")
        assert result.status == "ok"
        assert result.http_status == 200

    def test_b2_http_204_returns_ok(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().cancel("listing-123", "bk-b2")
        assert result.status == "ok"

    def test_b3_uses_delete_method(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            AirbnbAdapter().cancel("listing-123", "bk-b3")
        mock_httpx.delete.assert_called_once()


# ===========================================================================
# Group C — AirbnbAdapter.cancel() HTTP 500 → failed
# ===========================================================================

class TestGroupC_AirbnbCancel_HttpError:

    def test_c1_http_500_returns_failed(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(500)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().cancel("listing-123", "bk-c1")
        assert result.status == "failed"

    def test_c2_http_403_returns_failed(self, monkeypatch):
        monkeypatch.setenv("AIRBNB_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(403)
        with patch("adapters.outbound.airbnb_adapter.httpx", mock_httpx):
            from adapters.outbound.airbnb_adapter import AirbnbAdapter
            result = AirbnbAdapter().cancel("listing-123", "bk-c2")
        assert result.status == "failed"
        assert "403" in result.message


# ===========================================================================
# Group D — BookingComAdapter.cancel() dry-run
# ===========================================================================

class TestGroupD_BookingComCancel_DryRun:

    def test_d1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().cancel("hotel-456", "bk-d1")
        assert result.status == "dry_run"

    def test_d2_dry_run_flag_returns_dry_run(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().cancel("hotel-456", "bk-d2", dry_run=True)
        assert result.status == "dry_run"

    def test_d3_dry_run_provider_is_bookingcom(self, monkeypatch):
        monkeypatch.delenv("BOOKINGCOM_API_KEY", raising=False)
        from adapters.outbound.bookingcom_adapter import BookingComAdapter
        result = BookingComAdapter().cancel("hotel-456", "bk-d3")
        assert result.provider == "bookingcom"


# ===========================================================================
# Group E — BookingComAdapter.cancel() HTTP 204
# ===========================================================================

class TestGroupE_BookingComCancel_Http:

    def test_e1_http_204_returns_ok(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            result = BookingComAdapter().cancel("hotel-456", "bk-e1")
        assert result.status == "ok"
        assert result.http_status == 204

    def test_e2_uses_delete_not_post(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(204)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            BookingComAdapter().cancel("hotel-456", "bk-e2")
        mock_httpx.delete.assert_called_once()
        mock_httpx.post.assert_not_called()


# ===========================================================================
# Group F — BookingComAdapter.cancel() HTTP 404 → failed
# ===========================================================================

class TestGroupF_BookingComCancel_HttpError:

    def test_f1_http_404_returns_failed(self, monkeypatch):
        monkeypatch.setenv("BOOKINGCOM_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(404)
        with patch("adapters.outbound.bookingcom_adapter.httpx", mock_httpx):
            from adapters.outbound.bookingcom_adapter import BookingComAdapter
            result = BookingComAdapter().cancel("hotel-456", "bk-f1")
        assert result.status == "failed"
        assert "404" in result.message


# ===========================================================================
# Group G — ExpediaVrboAdapter.cancel() dry-run
# ===========================================================================

class TestGroupG_ExpediaCancel_DryRun:

    def test_g1_no_api_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").cancel("prop-789", "bk-g1")
        assert result.status == "dry_run"

    def test_g2_dry_run_flag_returns_dry_run(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").cancel("prop-789", "bk-g2", dry_run=True)
        assert result.status == "dry_run"

    def test_g3_provider_label_is_expedia(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("expedia").cancel("prop-789", "bk-g3")
        assert result.provider == "expedia"


# ===========================================================================
# Group H — ExpediaVrboAdapter vrbo sub-provider
# ===========================================================================

class TestGroupH_VrboCancel_DryRun:

    def test_h1_vrbo_no_key_returns_dry_run(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("vrbo").cancel("prop-vrbo", "bk-h1")
        assert result.status == "dry_run"

    def test_h2_vrbo_provider_label(self, monkeypatch):
        monkeypatch.delenv("EXPEDIA_API_KEY", raising=False)
        from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
        result = ExpediaVrboAdapter("vrbo").cancel("prop-vrbo", "bk-h2")
        assert result.provider == "vrbo"


# ===========================================================================
# Group I — ExpediaVrboAdapter.cancel() HTTP 200
# ===========================================================================

class TestGroupI_ExpediaCancel_Http:

    def test_i1_http_200_returns_ok(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
            result = ExpediaVrboAdapter("expedia").cancel("prop-789", "bk-i1")
        assert result.status == "ok"

    def test_i2_uses_delete_method(self, monkeypatch):
        monkeypatch.setenv("EXPEDIA_API_KEY", "key123")
        mock_httpx = MagicMock()
        mock_httpx.delete.return_value = _mock_httpx_resp(200)
        with patch("adapters.outbound.expedia_vrbo_adapter.httpx", mock_httpx):
            from adapters.outbound.expedia_vrbo_adapter import ExpediaVrboAdapter
            ExpediaVrboAdapter("expedia").cancel("prop-789", "bk-i2")
        mock_httpx.delete.assert_called_once()


# ===========================================================================
# Groups J, K, L, M — REMOVED in Phase 209
# Tested deprecated cancel_sync_trigger.py fast-path (Phase 151/154),
# now deleted. Outbound cancel sync uses sole guaranteed path:
# outbound_canceled_sync.fire_canceled_sync() -> build_sync_plan -> execute_sync_plan.
# ===========================================================================





# ===========================================================================
# Group N — _build_idempotency_key suffix
# ===========================================================================

class TestGroupN_IdempotencyKeySuffix:

    def test_n1_no_suffix_returns_standard_key(self):
        from adapters.outbound import _build_idempotency_key
        key = _build_idempotency_key("bk-n1", "ext-n1")
        assert "bk-n1" in key
        assert "ext-n1" in key

    def test_n2_suffix_appended(self):
        from adapters.outbound import _build_idempotency_key
        key = _build_idempotency_key("bk-n2", "ext-n2", suffix="cancel")
        assert key.endswith(":cancel")

    def test_n3_send_and_cancel_keys_differ(self):
        from adapters.outbound import _build_idempotency_key
        send_key   = _build_idempotency_key("bk-n3", "ext-n3")
        cancel_key = _build_idempotency_key("bk-n3", "ext-n3", suffix="cancel")
        assert send_key != cancel_key

    def test_n4_empty_suffix_returns_standard_key(self):
        from adapters.outbound import _build_idempotency_key
        key_no_sfx  = _build_idempotency_key("bk-n4", "ext-n4")
        key_empty   = _build_idempotency_key("bk-n4", "ext-n4", suffix="")
        assert key_no_sfx == key_empty
