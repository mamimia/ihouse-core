"""
Phase 151 — Contract Tests: iCal Cancellation Push

Groups:
  A — ICalPushAdapter.cancel() dry-run (no URL configured)
  B — cancel() body contains STATUS:CANCELLED
  C — cancel() body: METHOD:CANCEL in VCALENDAR header
  D — cancel() body: SEQUENCE:1 (one step ahead of push SEQUENCE:0)
  E — cancel() body: RFC 5545 required fields (VERSION, PRODID, UID, DTSTAMP)
  F — cancel() body: CRLF line endings throughout
  G — cancel() HTTP OK → status='ok'
  H — cancel() HTTP error → status='failed'
  I — fire_cancel_sync(): routes api_first to API adapters (Phase 154), unknown providers skipped
  J — fire_cancel_sync(): returns CancelSyncResult list correctly
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound.ical_push_adapter import ICalPushAdapter
from services.cancel_sync_trigger import CancelSyncResult, fire_cancel_sync


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_httpx_ok(status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = ""
    return resp


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for var in (
        "HOTELBEDS_ICAL_URL", "HOTELBEDS_API_KEY",
        "TRIPADVISOR_ICAL_URL", "TRIPADVISOR_API_KEY",
        "DESPEGAR_ICAL_URL", "DESPEGAR_API_KEY",
        "IHOUSE_DRY_RUN",
        "IHOUSE_THROTTLE_DISABLED", "IHOUSE_RETRY_DISABLED",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("IHOUSE_THROTTLE_DISABLED", "true")
    monkeypatch.setenv("IHOUSE_RETRY_DISABLED", "true")


# ===========================================================================
# Group A — cancel() dry-run (no URL configured)
# ===========================================================================

class TestGroupA_CancelDryRun:

    def test_a1_dry_run_when_no_url(self):
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.cancel(external_id="HB-001", booking_id="bk-cancel-001")
        assert result.status == "dry_run"

    def test_a2_dry_run_explicit_param(self):
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.cancel(external_id="HB-001", booking_id="bk-cancel-001", dry_run=True)
        assert result.status == "dry_run"

    def test_a3_dry_run_ihouse_env(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.cancel(external_id="HB-001", booking_id="bk-cancel-001")
        assert result.status == "dry_run"

    def test_a4_provider_in_dry_run_result(self):
        adapter = ICalPushAdapter("tripadvisor")
        result = adapter.cancel(external_id="TA-001", booking_id="bk-001")
        assert result.provider == "tripadvisor"

    def test_a5_strategy_in_dry_run_result(self):
        adapter = ICalPushAdapter("hotelbeds")
        result = adapter.cancel(external_id="HB-001", booking_id="bk-001")
        assert result.strategy == "ical_fallback"


# ===========================================================================
# Group B — cancel() body: STATUS:CANCELLED
# ===========================================================================

class TestGroupB_StatusCancelled:

    def _capture(self, monkeypatch, provider="hotelbeds", env_prefix="HOTELBEDS") -> bytes:
        monkeypatch.setenv(f"{env_prefix}_ICAL_URL", f"https://{provider}.test/ical")
        adapter = ICalPushAdapter(provider)
        captured: list[bytes] = []

        def _fake_put(url, content, headers, timeout):
            captured.append(content)
            return _mock_httpx_ok(204)

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = _fake_put
            adapter.cancel(external_id="EXT-CANCEL", booking_id="bk-c001")

        return captured[0] if captured else b""

    def test_b1_status_cancelled_in_body(self, monkeypatch):
        body = self._capture(monkeypatch).decode()
        assert "STATUS:CANCELLED" in body

    def test_b2_summary_cancelled(self, monkeypatch):
        body = self._capture(monkeypatch).decode()
        assert "CANCELLED" in body

    def test_b3_uid_matches_booking_id(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        def _fake_put(url, content, headers, timeout):
            captured.append(content)
            return _mock_httpx_ok(200)

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = _fake_put
            adapter.cancel(external_id="EXT-C", booking_id="bk-uid-test")

        body = captured[0].decode()
        assert "UID:bk-uid-test@ihouse.core" in body

    def test_b4_description_contains_ids(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        def _fake_put(url, content, headers, timeout):
            captured.append(content)
            return _mock_httpx_ok(200)

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = _fake_put
            adapter.cancel(external_id="EXT-DESC", booking_id="bk-desc-test")

        body = captured[0].decode()
        assert "booking_id=bk-desc-test" in body
        assert "external_id=EXT-DESC" in body


# ===========================================================================
# Group C — cancel() body: METHOD:CANCEL in VCALENDAR header
# ===========================================================================

class TestGroupC_MethodCancel:

    def test_c1_method_cancel_present(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        body = captured[0].decode()
        assert "METHOD:CANCEL" in body

    def test_c2_method_cancel_before_vevent(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        body = captured[0].decode()
        assert body.index("METHOD:CANCEL") < body.index("BEGIN:VEVENT")

    def test_c3_not_method_publish(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        # cancel payload should NOT use METHOD:PUBLISH
        body = captured[0].decode()
        assert "METHOD:PUBLISH" not in body


# ===========================================================================
# Group D — cancel() body: SEQUENCE:1
# ===========================================================================

class TestGroupD_SequenceOne:

    def _get_body(self, monkeypatch) -> str:
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        return captured[0].decode()

    def test_d1_sequence_is_one(self, monkeypatch):
        body = self._get_body(monkeypatch)
        assert "SEQUENCE:1" in body

    def test_d2_not_sequence_zero(self, monkeypatch):
        body = self._get_body(monkeypatch)
        assert "SEQUENCE:0" not in body


# ===========================================================================
# Group E — cancel() body: RFC 5545 required fields
# ===========================================================================

class TestGroupE_RequiredFields:

    def _get_body(self, monkeypatch) -> str:
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        return captured[0].decode()

    def test_e1_begin_vcalendar(self, monkeypatch):
        assert "BEGIN:VCALENDAR" in self._get_body(monkeypatch)

    def test_e2_version_2(self, monkeypatch):
        assert "VERSION:2.0" in self._get_body(monkeypatch)

    def test_e3_calscale_gregorian(self, monkeypatch):
        assert "CALSCALE:GREGORIAN" in self._get_body(monkeypatch)

    def test_e4_prodid_present(self, monkeypatch):
        assert "PRODID:" in self._get_body(monkeypatch)

    def test_e5_dtstamp_present(self, monkeypatch):
        import re
        body = self._get_body(monkeypatch)
        assert re.search(r"DTSTAMP:\d{8}T\d{6}Z", body)

    def test_e6_begin_vevent(self, monkeypatch):
        assert "BEGIN:VEVENT" in self._get_body(monkeypatch)

    def test_e7_end_vevent(self, monkeypatch):
        assert "END:VEVENT" in self._get_body(monkeypatch)


# ===========================================================================
# Group F — cancel() body: CRLF line endings
# ===========================================================================

class TestGroupF_CRLF:

    def _get_body(self, monkeypatch) -> str:
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            adapter.cancel(external_id="EXT-1", booking_id="bk-001")

        return captured[0].decode()

    def test_f1_crlf_present(self, monkeypatch):
        assert "\r\n" in self._get_body(monkeypatch)

    def test_f2_no_bare_lf(self, monkeypatch):
        body = self._get_body(monkeypatch)
        for i, ch in enumerate(body):
            if ch == "\n":
                assert i > 0 and body[i - 1] == "\r", f"Bare LF at pos {i}"


# ===========================================================================
# Group G — cancel() HTTP OK → status='ok'
# ===========================================================================

class TestGroupG_HTTPOk:

    @pytest.mark.parametrize("status_code", [200, 201, 204])
    def test_g_http_ok_returns_ok(self, monkeypatch, status_code):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.return_value = _mock_httpx_ok(status_code)
            result = adapter.cancel(external_id="HB-G", booking_id="bk-g001")

        assert result.status == "ok"
        assert result.provider == "hotelbeds"


# ===========================================================================
# Group H — cancel() HTTP error → status='failed'
# ===========================================================================

class TestGroupH_HTTPError:

    @pytest.mark.parametrize("status_code", [400, 404, 500, 503])
    def test_h_http_error_returns_failed(self, monkeypatch, status_code):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        adapter = ICalPushAdapter("hotelbeds")

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.return_value = _mock_httpx_ok(status_code)
            result = adapter.cancel(external_id="HB-H", booking_id="bk-h001")

        assert result.status == "failed"


# ===========================================================================
# Group I — fire_cancel_sync(): routes known providers, skips unknown
# ===========================================================================

class TestGroupI_SkipsNonIcal:

    def test_i1_skips_api_first_provider(self):
        channels = [
            {"provider": "airbnb", "external_id": "AB-001", "sync_strategy": "api_first"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-i001",
            property_id="prop-i",
            tenant_id="t-i",
            channels=channels,
        )
        assert len(results) == 1
        # Phase 154: airbnb is now routed to AirbnbAdapter.cancel().
        # With no API key configured, adapter returns dry_run (not skipped).
        assert results[0].status in ("dry_run", "ok", "failed")

    def test_i2_skips_unknown_provider(self):
        channels = [
            {"provider": "unknown_ota", "external_id": "UNK-1", "sync_strategy": "ical_fallback"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-i002",
            property_id="prop-i",
            tenant_id="t-i",
            channels=channels,
        )
        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_i3_skips_empty_external_id(self):
        channels = [
            {"provider": "hotelbeds", "external_id": "", "sync_strategy": "ical_fallback"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-i003",
            property_id="prop-i",
            tenant_id="t-i",
            channels=channels,
        )
        assert len(results) == 1
        assert results[0].status == "skipped"

    def test_i4_empty_channels_returns_empty(self):
        results = fire_cancel_sync(
            booking_id="bk-i004",
            property_id="prop-i",
            tenant_id="t-i",
            channels=[],
        )
        assert results == []


# ===========================================================================
# Group J — fire_cancel_sync(): returns CancelSyncResult list
# ===========================================================================

class TestGroupJ_FireCancelSyncResults:

    def test_j1_dry_run_channel_returns_dry_run(self):
        # No env URL set → adapter returns dry_run
        channels = [
            {"provider": "hotelbeds", "external_id": "HB-J1", "sync_strategy": "ical_fallback"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-j001",
            property_id="prop-j",
            tenant_id="t-j",
            channels=channels,
        )
        assert len(results) == 1
        assert results[0].provider == "hotelbeds"
        assert results[0].external_id == "HB-J1"
        assert results[0].status == "dry_run"

    def test_j2_multiple_channels_all_returned(self):
        channels = [
            {"provider": "hotelbeds",   "external_id": "HB-J2a", "sync_strategy": "ical_fallback"},
            {"provider": "tripadvisor", "external_id": "TA-J2b", "sync_strategy": "ical_fallback"},
            {"provider": "despegar",    "external_id": "DS-J2c", "sync_strategy": "ical_fallback"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-j002",
            property_id="prop-j",
            tenant_id="t-j",
            channels=channels,
        )
        assert len(results) == 3
        providers = {r.provider for r in results}
        assert providers == {"hotelbeds", "tripadvisor", "despegar"}

    def test_j3_result_is_cancel_sync_result_type(self):
        channels = [
            {"provider": "hotelbeds", "external_id": "HB-J3", "sync_strategy": "ical_fallback"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-j003",
            property_id="prop-j",
            tenant_id="t-j",
            channels=channels,
        )
        assert all(isinstance(r, CancelSyncResult) for r in results)

    def test_j4_mixed_channels_filters_correctly(self):
        channels = [
            {"provider": "hotelbeds", "external_id": "HB-J4", "sync_strategy": "ical_fallback"},
            {"provider": "airbnb",    "external_id": "AB-J4", "sync_strategy": "api_first"},
        ]
        results = fire_cancel_sync(
            booking_id="bk-j004",
            property_id="prop-j",
            tenant_id="t-j",
            channels=channels,
        )
        assert len(results) == 2
        hb = next(r for r in results if r.provider == "hotelbeds")
        ab = next(r for r in results if r.provider == "airbnb")
        assert hb.status == "dry_run"
        # Phase 154: airbnb is now an API adapter, returns dry_run (no key configured)
        assert ab.status in ("dry_run", "ok", "failed")
