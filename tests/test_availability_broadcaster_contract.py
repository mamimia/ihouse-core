"""
Phase 173 — Contract Tests: IPI Proactive Availability Broadcasting

Tests the outbound_availability_broadcaster service and the
POST /admin/broadcast/availability endpoint.

Groups:
    A — broadcast_availability: no channels configured (noop)
    B — broadcast_availability: no active bookings (noop)
    C — broadcast_availability: PROPERTY_ONBOARDED — all channels, all bookings
    D — broadcast_availability: CHANNEL_ADDED — single target channel only
    E — broadcast_availability: source_provider exclusion
    F — broadcast_availability: fail-isolated — one booking failure does not abort others
    G — broadcast_availability: DB setup failure graceful return
    H — API endpoint: validation — missing / invalid fields
    I — API endpoint: valid PROPERTY_ONBOARDED request
    J — API endpoint: valid CHANNEL_ADDED request
    K — serialise_broadcast_report: shape and completeness
"""
from __future__ import annotations

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.outbound_availability_broadcaster import (
    broadcast_availability,
    serialise_broadcast_report,
    BroadcastMode,
    BroadcastReport,
    BookingBroadcastResult,
    _fetch_channels,
    _fetch_registry,
    _fetch_active_booking_ids,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(*, channels=None, registry_rows=None, bookings=None):
    """Build a mock Supabase client stub."""
    db = MagicMock()

    channels = channels or []
    registry_rows = registry_rows or []
    bookings = bookings or []

    def _table_select(table_name):
        tbl = MagicMock()
        tbl.select.return_value = tbl
        tbl.eq.return_value = tbl
        tbl.neq.return_value = tbl
        tbl.limit.return_value = tbl

        if table_name == "property_channel_map":
            result = MagicMock()
            result.data = channels
            tbl.execute.return_value = result
        elif table_name == "provider_capability_registry":
            result = MagicMock()
            result.data = registry_rows
            tbl.execute.return_value = result
        elif table_name == "booking_state":
            result = MagicMock()
            result.data = bookings
            tbl.execute.return_value = result

        return tbl

    db.table.side_effect = _table_select
    return db


def _api_adapter_ok(provider, external_id, booking_id, rate_limit):
    from services.outbound_executor import ExecutionResult
    return ExecutionResult(
        provider=provider,
        external_id=external_id,
        strategy="api_first",
        status="ok",
        http_status=200,
        message="ok",
    )


def _api_adapter_fail(provider, external_id, booking_id, rate_limit):
    from services.outbound_executor import ExecutionResult
    return ExecutionResult(
        provider=provider,
        external_id=external_id,
        strategy="api_first",
        status="failed",
        http_status=503,
        message="upstream error",
    )


class _OkAdapter:
    send = staticmethod(_api_adapter_ok)


class _FailAdapter:
    send = staticmethod(_api_adapter_fail)


_REGISTRY_ROWS = [
    {
        "provider": "bookingcom",
        "tier": "A",
        "supports_api_write": True,
        "supports_ical_push": False,
        "supports_ical_pull": False,
        "rate_limit_per_min": 60,
    },
    {
        "provider": "airbnb",
        "tier": "A",
        "supports_api_write": True,
        "supports_ical_push": False,
        "supports_ical_pull": False,
        "rate_limit_per_min": 60,
    },
]

_CHANNELS = [
    {"provider": "bookingcom", "external_id": "ext_bc_001", "sync_mode": "api_first", "enabled": True},
    {"provider": "airbnb",     "external_id": "ext_ab_001", "sync_mode": "api_first", "enabled": True},
]

_BOOKINGS = [
    {"booking_id": "airbnb_B001"},
    {"booking_id": "airbnb_B002"},
]


# ---------------------------------------------------------------------------
# Group A — No channels configured
# ---------------------------------------------------------------------------

class TestGroupA_NoChannels:
    def test_no_channels_returns_zero_bookings_found(self):
        db = _make_db(channels=[], registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert report.bookings_found == 0
        assert report.bookings_ok == 0
        assert report.results == []

    def test_no_channels_returns_broadcast_report_instance(self):
        db = _make_db(channels=[])
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert isinstance(report, BroadcastReport)

    def test_no_channels_mode_stored_correctly(self):
        db = _make_db(channels=[])
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert report.mode == BroadcastMode.PROPERTY_ONBOARDED


# ---------------------------------------------------------------------------
# Group B — No active bookings
# ---------------------------------------------------------------------------

class TestGroupB_NoBookings:
    def test_no_bookings_returns_zero_found(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=[])
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_OkAdapter,
        )
        assert report.bookings_found == 0
        assert report.results == []

    def test_no_bookings_no_failures(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=[])
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert report.bookings_failed == 0


# ---------------------------------------------------------------------------
# Group C — PROPERTY_ONBOARDED broadcasts all bookings
# ---------------------------------------------------------------------------

class TestGroupC_PropertyOnboarded:
    def test_all_bookings_broadcast(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_OkAdapter,
        )
        assert report.bookings_found == 2
        assert len(report.results) == 2

    def test_all_ok_increments_bookings_ok(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_OkAdapter,
        )
        assert report.bookings_ok == 2
        assert report.bookings_failed == 0

    def test_booking_result_fields_present(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_OkAdapter,
        )
        for r in report.results:
            assert isinstance(r, BookingBroadcastResult)
            assert r.booking_id in ("airbnb_B001", "airbnb_B002")
            assert r.property_id == "prop_001"

    def test_property_id_in_report(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_XYZ",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_OkAdapter,
        )
        assert report.property_id == "prop_XYZ"


# ---------------------------------------------------------------------------
# Group D — CHANNEL_ADDED broadcasts only target channel
# ---------------------------------------------------------------------------

class TestGroupD_ChannelAdded:
    def test_only_target_channel_queried(self):
        """When mode=CHANNEL_ADDED with target_provider, only one channel row returned."""
        single_channel = [_CHANNELS[0]]  # bookingcom only
        db = _make_db(channels=single_channel, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.CHANNEL_ADDED,
            target_provider="bookingcom",
            api_adapter=_OkAdapter,
        )
        # Both bookings should be processed
        assert report.bookings_found == 2

    def test_channel_added_mode_stored(self):
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.CHANNEL_ADDED,
            target_provider="airbnb",
            api_adapter=_OkAdapter,
        )
        assert report.mode == BroadcastMode.CHANNEL_ADDED


# ---------------------------------------------------------------------------
# Group E — source_provider exclusion
# ---------------------------------------------------------------------------

class TestGroupE_SourceExclusion:
    def test_all_channels_excluded_returns_empty(self):
        """If both channels are the source, no sync runs."""
        # Only bookingcom channel mapped; source_provider=bookingcom → all excluded
        single_channel = [_CHANNELS[0]]
        db = _make_db(channels=single_channel, registry_rows=_REGISTRY_ROWS, bookings=_BOOKINGS)
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            source_provider="bookingcom",
            api_adapter=_OkAdapter,
        )
        assert report.bookings_found == 0

    def test_source_excluded_remaining_synced(self):
        """Non-source channel still gets synced."""
        db = _make_db(channels=_CHANNELS, registry_rows=_REGISTRY_ROWS, bookings=[_BOOKINGS[0]])
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            source_provider="bookingcom",  # exclude bookingcom; airbnb remains
            api_adapter=_OkAdapter,
        )
        # airbnb still active → should be processed
        assert report.bookings_found == 1
        assert report.bookings_ok == 1


# ---------------------------------------------------------------------------
# Group F — Fail isolation
# ---------------------------------------------------------------------------

class TestGroupF_FailIsolation:
    def test_one_fail_does_not_abort_others(self):
        """First booking fails; second booking still processed."""
        call_count = {"n": 0}

        class _AlternatingAdapter:
            @staticmethod
            def send(provider, external_id, booking_id, rate_limit):
                from services.outbound_executor import ExecutionResult
                call_count["n"] += 1
                status = "failed" if call_count["n"] == 1 else "ok"
                return ExecutionResult(
                    provider=provider,
                    external_id=external_id,
                    strategy="api_first",
                    status=status,
                    http_status=503 if status == "failed" else 200,
                    message=status,
                )

        db = _make_db(
            channels=[_CHANNELS[0]],   # single channel
            registry_rows=[_REGISTRY_ROWS[0]],
            bookings=_BOOKINGS,
        )
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_AlternatingAdapter,
        )
        assert report.bookings_found == 2
        assert len(report.results) == 2

    def test_failed_booking_counted_separately(self):
        db = _make_db(
            channels=[_CHANNELS[0]],
            registry_rows=[_REGISTRY_ROWS[0]],
            bookings=_BOOKINGS,
        )
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            api_adapter=_FailAdapter,
        )
        assert report.bookings_failed == 2
        assert report.bookings_ok == 0


# ---------------------------------------------------------------------------
# Group G — DB setup failure
# ---------------------------------------------------------------------------

class TestGroupG_DBFailure:
    def test_db_exception_returns_empty_report(self):
        db = MagicMock()
        db.table.side_effect = Exception("connection refused")
        report = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert isinstance(report, BroadcastReport)
        assert report.bookings_found == 0
        assert report.results == []

    def test_db_exception_does_not_raise(self):
        db = MagicMock()
        db.table.side_effect = RuntimeError("db gone")
        # Must never raise
        result = broadcast_availability(
            db,
            tenant_id="t_test",
            property_id="prop_001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Group H — API validation
# ---------------------------------------------------------------------------

class TestGroupH_APIValidation:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def test_missing_property_id_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            json={"mode": "PROPERTY_ONBOARDED"},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_missing_mode_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            json={"property_id": "prop_001"},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_invalid_mode_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            json={"property_id": "prop_001", "mode": "INVALID_MODE"},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_channel_added_without_target_provider_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            json={"property_id": "prop_001", "mode": "CHANNEL_ADDED"},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_empty_body_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            json={},
            headers=self.headers,
        )
        assert resp.status_code == 400

    def test_invalid_json_schema_returns_400(self):
        resp = self.client.post(
            "/admin/broadcast/availability",
            content="not-json",
            headers={**self.headers, "Content-Type": "application/json"},
        )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Group I — API: valid PROPERTY_ONBOARDED
# ---------------------------------------------------------------------------

class TestGroupI_APIOnboarded:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def _mock_broadcaster(self, report):
        return patch(
            "api.broadcaster_router.broadcast_availability",
            return_value=report,
        )

    def _make_report(self):
        return BroadcastReport(
            property_id="prop_001",
            mode="PROPERTY_ONBOARDED",
            bookings_found=2,
            bookings_ok=2,
            bookings_failed=0,
            bookings_skipped=0,
            results=[
                BookingBroadcastResult("b1", "prop_001", 2, 0, 0, False),
                BookingBroadcastResult("b2", "prop_001", 2, 0, 0, False),
            ],
        )

    def test_valid_request_returns_200(self):
        report = self._make_report()
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={"property_id": "prop_001", "mode": "PROPERTY_ONBOARDED"},
                headers=self.headers,
            )
        assert resp.status_code == 200

    def test_response_contains_property_id(self):
        report = self._make_report()
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={"property_id": "prop_001", "mode": "PROPERTY_ONBOARDED"},
                headers=self.headers,
            )
        body = resp.json()
        assert body["property_id"] == "prop_001"

    def test_response_contains_mode(self):
        report = self._make_report()
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={"property_id": "prop_001", "mode": "PROPERTY_ONBOARDED"},
                headers=self.headers,
            )
        body = resp.json()
        assert body["mode"] == "PROPERTY_ONBOARDED"

    def test_response_contains_bookings_found(self):
        report = self._make_report()
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={"property_id": "prop_001", "mode": "PROPERTY_ONBOARDED"},
                headers=self.headers,
            )
        body = resp.json()
        assert body["bookings_found"] == 2

    def test_response_contains_results_list(self):
        report = self._make_report()
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={"property_id": "prop_001", "mode": "PROPERTY_ONBOARDED"},
                headers=self.headers,
            )
        body = resp.json()
        assert isinstance(body["results"], list)
        assert len(body["results"]) == 2


# ---------------------------------------------------------------------------
# Group J — API: valid CHANNEL_ADDED
# ---------------------------------------------------------------------------

class TestGroupJ_APIChannelAdded:
    def setup_method(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer dev-token"}

    def _mock_broadcaster(self, report):
        return patch(
            "api.broadcaster_router.broadcast_availability",
            return_value=report,
        )

    def test_channel_added_with_target_provider_returns_200(self):
        report = BroadcastReport(
            property_id="prop_001",
            mode="CHANNEL_ADDED",
            bookings_found=1,
            bookings_ok=1,
            bookings_failed=0,
            bookings_skipped=0,
        )
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={
                    "property_id": "prop_001",
                    "mode": "CHANNEL_ADDED",
                    "target_provider": "bookingcom",
                },
                headers=self.headers,
            )
        assert resp.status_code == 200

    def test_channel_added_response_mode(self):
        report = BroadcastReport(
            property_id="prop_001",
            mode="CHANNEL_ADDED",
            bookings_found=1,
            bookings_ok=1,
            bookings_failed=0,
            bookings_skipped=0,
        )
        with patch(
            "services.outbound_availability_broadcaster.broadcast_availability",
            return_value=report,
        ), patch("api.broadcaster_router._get_supabase_client", return_value=MagicMock()):
            resp = self.client.post(
                "/admin/broadcast/availability",
                json={
                    "property_id": "prop_001",
                    "mode": "CHANNEL_ADDED",
                    "target_provider": "airbnb",
                },
                headers=self.headers,
            )
        body = resp.json()
        assert body["mode"] == "CHANNEL_ADDED"


# ---------------------------------------------------------------------------
# Group K — serialise_broadcast_report shape
# ---------------------------------------------------------------------------

class TestGroupK_Serialise:
    def test_all_top_level_keys_present(self):
        report = BroadcastReport(
            property_id="p",
            mode="PROPERTY_ONBOARDED",
            bookings_found=3,
            bookings_ok=2,
            bookings_failed=1,
            bookings_skipped=0,
            results=[
                BookingBroadcastResult("b1", "p", 2, 0, 0, False),
                BookingBroadcastResult("b2", "p", 0, 1, 0, False, error="timeout"),
            ],
        )
        out = serialise_broadcast_report(report)
        assert set(out.keys()) == {
            "property_id", "mode", "bookings_found",
            "bookings_ok", "bookings_failed", "bookings_skipped", "results",
        }

    def test_results_list_shape(self):
        report = BroadcastReport(
            property_id="p",
            mode="CHANNEL_ADDED",
            bookings_found=1,
            bookings_ok=1,
            bookings_failed=0,
            bookings_skipped=0,
            results=[BookingBroadcastResult("b1", "p", 2, 0, 0, True)],
        )
        out = serialise_broadcast_report(report)
        r = out["results"][0]
        assert set(r.keys()) == {
            "booking_id", "ok_count", "failed_count",
            "skip_count", "dry_run", "error",
        }

    def test_error_field_none_when_no_error(self):
        report = BroadcastReport(
            property_id="p",
            mode="PROPERTY_ONBOARDED",
            bookings_found=1,
            bookings_ok=1,
            bookings_failed=0,
            bookings_skipped=0,
            results=[BookingBroadcastResult("b1", "p", 2, 0, 0, False)],
        )
        out = serialise_broadcast_report(report)
        assert out["results"][0]["error"] is None

    def test_error_field_populated_on_error(self):
        report = BroadcastReport(
            property_id="p",
            mode="PROPERTY_ONBOARDED",
            bookings_found=1,
            bookings_ok=0,
            bookings_failed=1,
            bookings_skipped=0,
            results=[BookingBroadcastResult("b1", "p", 0, 1, 0, False, error="upstream down")],
        )
        out = serialise_broadcast_report(report)
        assert out["results"][0]["error"] == "upstream down"

    def test_counts_match_report(self):
        report = BroadcastReport(
            property_id="p",
            mode="PROPERTY_ONBOARDED",
            bookings_found=5,
            bookings_ok=3,
            bookings_failed=1,
            bookings_skipped=1,
        )
        out = serialise_broadcast_report(report)
        assert out["bookings_found"] == 5
        assert out["bookings_ok"] == 3
        assert out["bookings_failed"] == 1
        assert out["bookings_skipped"] == 1
