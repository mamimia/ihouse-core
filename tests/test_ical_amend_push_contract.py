"""
Phase 152 — Contract Tests: iCal Sync-on-Amendment Push

Groups:
  A — fire_amend_sync(): dry-run when no URL configured
  B — fire_amend_sync(): skips non-ical / unknown providers
  C — fire_amend_sync(): returns AmendSyncResult list
  D — fire_amend_sync(): updated dates appear in pushed iCal body
  E — fire_amend_sync(): timezone forwarded from channel map row
  F — fire_amend_sync(): None dates fall back to adapter defaults
  G — fire_amend_sync(): multiple channels all attempted
  H — _to_ical() helper: date normalisation
  I — fire_amend_sync(): HTTP OK → status='ok'
  J — fire_amend_sync(): HTTP error → status='failed' (absorbed, not raised)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.amend_sync_trigger import AmendSyncResult, _to_ical, fire_amend_sync


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
# Group A — dry-run when no URL configured
# ===========================================================================

class TestGroupA_DryRun:

    def test_a1_dry_run_when_no_url(self):
        channels = [{"provider": "hotelbeds", "external_id": "HB-001", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-a001", property_id="p-a", tenant_id="t-a",
            check_in="20260501", check_out="20260510", channels=channels,
        )
        assert results[0].status == "dry_run"

    def test_a2_dry_run_with_tripadvisor(self):
        channels = [{"provider": "tripadvisor", "external_id": "TA-001", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-a002", property_id="p-a", tenant_id="t-a",
            channels=channels,
        )
        assert results[0].status == "dry_run"

    def test_a3_ihouse_dry_run_env(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_DRY_RUN", "true")
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{"provider": "hotelbeds", "external_id": "HB-001", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-a003", property_id="p-a", tenant_id="t-a",
            check_in="20260601", check_out="20260610", channels=channels,
        )
        assert results[0].status == "dry_run"

    def test_a4_dry_run_result_has_correct_provider(self):
        channels = [{"provider": "despegar", "external_id": "DS-001", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-a004", property_id="p-a", tenant_id="t-a",
            channels=channels,
        )
        assert results[0].provider == "despegar"

    def test_a5_strategy_is_ical_fallback(self):
        channels = [{"provider": "hotelbeds", "external_id": "HB-a5", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-a005", property_id="p-a", tenant_id="t-a",
            channels=channels,
        )
        assert results[0].status in ("dry_run", "ok", "failed")  # valid statuses


# ===========================================================================
# Group B — skips non-ical / unknown providers
# ===========================================================================

class TestGroupB_SkipsNonIcal:

    def test_b1_skips_airbnb(self):
        channels = [{"provider": "airbnb", "external_id": "AB-001", "sync_strategy": "api_first"}]
        results = fire_amend_sync(
            booking_id="bk-b001", property_id="p-b", tenant_id="t-b", channels=channels,
        )
        assert results[0].status == "skipped"

    def test_b2_skips_unknown_provider(self):
        channels = [{"provider": "some_unknown_ota", "external_id": "UNK-1", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-b002", property_id="p-b", tenant_id="t-b", channels=channels,
        )
        assert results[0].status == "skipped"

    def test_b3_skips_empty_external_id(self):
        channels = [{"provider": "hotelbeds", "external_id": "", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-b003", property_id="p-b", tenant_id="t-b", channels=channels,
        )
        assert results[0].status == "skipped"

    def test_b4_empty_channels_returns_empty(self):
        assert fire_amend_sync(
            booking_id="bk-b004", property_id="p-b", tenant_id="t-b", channels=[],
        ) == []

    def test_b5_mixed_skips_correctly(self):
        channels = [
            {"provider": "hotelbeds", "external_id": "HB-B5", "sync_strategy": "ical_fallback"},
            {"provider": "airbnb",    "external_id": "AB-B5", "sync_strategy": "api_first"},
        ]
        results = fire_amend_sync(
            booking_id="bk-b005", property_id="p-b", tenant_id="t-b", channels=channels,
        )
        assert len(results) == 2
        hb = next(r for r in results if r.provider == "hotelbeds")
        ab = next(r for r in results if r.provider == "airbnb")
        assert hb.status == "dry_run"
        assert ab.status == "skipped"


# ===========================================================================
# Group C — returns AmendSyncResult list
# ===========================================================================

class TestGroupC_ResultType:

    def test_c1_result_is_amend_sync_result(self):
        channels = [{"provider": "hotelbeds", "external_id": "HB-C1", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-c001", property_id="p-c", tenant_id="t-c", channels=channels,
        )
        assert all(isinstance(r, AmendSyncResult) for r in results)

    def test_c2_result_has_external_id(self):
        channels = [{"provider": "hotelbeds", "external_id": "HB-C2", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-c002", property_id="p-c", tenant_id="t-c", channels=channels,
        )
        assert results[0].external_id == "HB-C2"

    def test_c3_result_has_message(self):
        channels = [{"provider": "hotelbeds", "external_id": "HB-C3", "sync_strategy": "ical_fallback"}]
        results = fire_amend_sync(
            booking_id="bk-c003", property_id="p-c", tenant_id="t-c", channels=channels,
        )
        assert isinstance(results[0].message, str)


# ===========================================================================
# Group D — updated dates appear in pushed iCal body
# ===========================================================================

class TestGroupD_UpdatedDates:

    def _push_and_capture(self, monkeypatch, check_in, check_out) -> str:
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{"provider": "hotelbeds", "external_id": "HB-D", "sync_strategy": "ical_fallback"}]
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            fire_amend_sync(
                booking_id="bk-d001", property_id="p-d", tenant_id="t-d",
                check_in=check_in, check_out=check_out, channels=channels,
            )
        return captured[0].decode() if captured else ""

    def test_d1_new_checkin_in_body(self, monkeypatch):
        body = self._push_and_capture(monkeypatch, "20260901", "20260910")
        assert "20260901" in body

    def test_d2_new_checkout_in_body(self, monkeypatch):
        body = self._push_and_capture(monkeypatch, "20260901", "20260910")
        assert "20260910" in body

    def test_d3_iso_date_converted(self, monkeypatch):
        body = self._push_and_capture(monkeypatch, "2026-09-01", "2026-09-10")
        assert "20260901" in body
        assert "20260910" in body

    def test_d4_dtstart_has_new_date(self, monkeypatch):
        body = self._push_and_capture(monkeypatch, "20261201", "20261208")
        assert "DTSTART:20261201" in body


# ===========================================================================
# Group E — timezone forwarded from channel map row
# ===========================================================================

class TestGroupE_TimezoneForwarded:

    def test_e1_timezone_in_vtimezone_block(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{
            "provider": "hotelbeds", "external_id": "HB-E1",
            "sync_strategy": "ical_fallback", "timezone": "Asia/Bangkok",
        }]
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            fire_amend_sync(
                booking_id="bk-e001", property_id="p-e", tenant_id="t-e",
                check_in="20260601", check_out="20260610", channels=channels,
            )
        body = captured[0].decode() if captured else ""
        assert "VTIMEZONE" in body
        assert "Asia/Bangkok" in body

    def test_e2_none_timezone_falls_back_to_utc(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{
            "provider": "hotelbeds", "external_id": "HB-E2",
            "sync_strategy": "ical_fallback", "timezone": None,
        }]
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            fire_amend_sync(
                booking_id="bk-e002", property_id="p-e", tenant_id="t-e",
                check_in="20260601", check_out="20260610", channels=channels,
            )
        body = captured[0].decode() if captured else ""
        # UTC path: DTSTART without TZID
        assert "DTSTART:20260601" in body


# ===========================================================================
# Group F — None dates fall back to adapter defaults
# ===========================================================================

class TestGroupF_NoneDatesFallback:

    def test_f1_none_checkin_uses_fallback(self, monkeypatch):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{"provider": "hotelbeds", "external_id": "HB-F1", "sync_strategy": "ical_fallback"}]
        captured: list[bytes] = []

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.side_effect = lambda url, content, headers, timeout: (
                captured.append(content) or _mock_httpx_ok(200)
            )
            fire_amend_sync(
                booking_id="bk-f001", property_id="p-f", tenant_id="t-f",
                check_in=None, check_out=None, channels=channels,
            )
        body = captured[0].decode() if captured else ""
        # Adapter falls back to _FALLBACK_DTSTART / _FALLBACK_DTEND
        assert "DTSTART:20260101" in body
        assert "DTEND:20260102" in body


# ===========================================================================
# Group G — multiple channels all attempted
# ===========================================================================

class TestGroupG_MultipleChannels:

    def test_g1_all_channels_returned(self):
        channels = [
            {"provider": "hotelbeds",   "external_id": "HB-G", "sync_strategy": "ical_fallback"},
            {"provider": "tripadvisor", "external_id": "TA-G", "sync_strategy": "ical_fallback"},
            {"provider": "despegar",    "external_id": "DS-G", "sync_strategy": "ical_fallback"},
        ]
        results = fire_amend_sync(
            booking_id="bk-g001", property_id="p-g", tenant_id="t-g", channels=channels,
        )
        assert len(results) == 3

    def test_g2_all_providers_present(self):
        channels = [
            {"provider": "hotelbeds",   "external_id": "HB-G2", "sync_strategy": "ical_fallback"},
            {"provider": "tripadvisor", "external_id": "TA-G2", "sync_strategy": "ical_fallback"},
        ]
        results = fire_amend_sync(
            booking_id="bk-g002", property_id="p-g", tenant_id="t-g", channels=channels,
        )
        providers = {r.provider for r in results}
        assert "hotelbeds" in providers
        assert "tripadvisor" in providers


# ===========================================================================
# Group H — _to_ical() helper
# ===========================================================================

class TestGroupH_ToIcal:

    def test_h1_iso_to_compact(self):
        assert _to_ical("2026-09-01") == "20260901"

    def test_h2_compact_unchanged(self):
        assert _to_ical("20260901") == "20260901"

    def test_h3_none_returns_none(self):
        assert _to_ical(None) is None

    def test_h4_empty_returns_none(self):
        assert _to_ical("") is None

    def test_h5_december_date(self):
        assert _to_ical("2026-12-25") == "20261225"

    def test_h6_already_compact_correct_length(self):
        result = _to_ical("20260315")
        assert result == "20260315"
        assert len(result) == 8


# ===========================================================================
# Group I — HTTP OK → status='ok'
# ===========================================================================

class TestGroupI_HTTPOk:

    @pytest.mark.parametrize("status_code", [200, 201, 204])
    def test_i_http_ok(self, monkeypatch, status_code):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{"provider": "hotelbeds", "external_id": "HB-I", "sync_strategy": "ical_fallback"}]

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.return_value = _mock_httpx_ok(status_code)
            results = fire_amend_sync(
                booking_id="bk-i001", property_id="p-i", tenant_id="t-i",
                check_in="20260901", check_out="20260910", channels=channels,
            )
        assert results[0].status == "ok"


# ===========================================================================
# Group J — HTTP error → status='failed' (absorbed, not raised)
# ===========================================================================

class TestGroupJ_HTTPError:

    @pytest.mark.parametrize("status_code", [400, 404, 500, 503])
    def test_j_http_error_absorbed(self, monkeypatch, status_code):
        monkeypatch.setenv("HOTELBEDS_ICAL_URL", "https://hb.test/ical")
        channels = [{"provider": "hotelbeds", "external_id": "HB-J", "sync_strategy": "ical_fallback"}]

        with patch("adapters.outbound.ical_push_adapter.httpx") as mock_httpx:
            mock_httpx.put.return_value = _mock_httpx_ok(status_code)
            results = fire_amend_sync(
                booking_id="bk-j001", property_id="p-j", tenant_id="t-j",
                check_in="20260901", check_out="20260910", channels=channels,
            )
        assert results[0].status == "failed"
        # Must NOT raise — absorbed in fire_amend_sync
