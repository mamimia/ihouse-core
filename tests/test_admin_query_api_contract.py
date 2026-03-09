"""
Phase 82 — Contract tests for Admin Query API endpoints.

Tests:
  A — GET /admin/metrics (idempotency + DLQ metrics)
  B — GET /admin/dlq (DLQ pending + rejection breakdown)
  C — GET /admin/health/providers (per-provider last ingest)
  D — GET /admin/bookings/{id}/timeline (booking event history)
  E — Auth / 500 guards
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def _make_app(tenant_id: str = "tenant-a") -> TestClient:
    from api.admin_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth() -> str:
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app)


def _reject_app() -> TestClient:
    """App where jwt_auth always rejects."""
    from api.admin_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Group A — GET /admin/metrics
# ---------------------------------------------------------------------------

class TestAdminMetrics:

    def _mock_report(self, **kwargs):
        from adapters.ota.idempotency_monitor import IdempotencyReport
        defaults = dict(
            total_dlq_rows=10,
            pending_dlq_rows=3,
            already_applied_count=7,
            idempotency_rejection_count=2,
            ordering_buffer_depth=1,
            checked_at="2026-03-09T00:00:00+00:00",
        )
        defaults.update(kwargs)
        return IdempotencyReport(**defaults)

    def test_A1_200_status_code(self) -> None:
        report = self._mock_report()
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app().get("/admin/metrics")
        assert resp.status_code == 200

    def test_A2_all_fields_present(self) -> None:
        report = self._mock_report()
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app().get("/admin/metrics")
        body = resp.json()
        for field in ("tenant_id", "total_dlq_rows", "pending_dlq_rows",
                      "already_applied_count", "idempotency_rejection_count",
                      "ordering_buffer_depth", "checked_at"):
            assert field in body, f"Missing field: {field}"

    def test_A3_tenant_id_in_response(self) -> None:
        report = self._mock_report()
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app(tenant_id="acme").get("/admin/metrics")
        assert resp.json()["tenant_id"] == "acme"

    def test_A4_pending_dlq_rows_value(self) -> None:
        report = self._mock_report(pending_dlq_rows=5)
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app().get("/admin/metrics")
        assert resp.json()["pending_dlq_rows"] == 5

    def test_A5_ordering_buffer_depth_value(self) -> None:
        report = self._mock_report(ordering_buffer_depth=4)
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app().get("/admin/metrics")
        assert resp.json()["ordering_buffer_depth"] == 4

    def test_A6_checked_at_present(self) -> None:
        report = self._mock_report(checked_at="2026-03-09T12:00:00+00:00")
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report", return_value=report):
            resp = _make_app().get("/admin/metrics")
        assert resp.json()["checked_at"] == "2026-03-09T12:00:00+00:00"

    def test_A7_500_on_db_error(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.idempotency_monitor.collect_idempotency_report",
                   side_effect=RuntimeError("boom")):
            resp = _make_app().get("/admin/metrics")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_A8_403_when_auth_rejected(self) -> None:
        resp = _reject_app().get("/admin/metrics")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group B — GET /admin/dlq
# ---------------------------------------------------------------------------

class TestAdminDLQ:

    def test_B1_200_status_code(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count", return_value=3), \
             patch("adapters.ota.dlq_inspector.get_replayed_count", return_value=7), \
             patch("adapters.ota.dlq_inspector.get_rejection_breakdown", return_value=[]):
            resp = _make_app().get("/admin/dlq")
        assert resp.status_code == 200

    def test_B2_pending_and_replayed_counts(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count", return_value=3), \
             patch("adapters.ota.dlq_inspector.get_replayed_count", return_value=7), \
             patch("adapters.ota.dlq_inspector.get_rejection_breakdown", return_value=[]):
            resp = _make_app().get("/admin/dlq")
        body = resp.json()
        assert body["pending"] == 3
        assert body["replayed"] == 7

    def test_B3_breakdown_in_response(self) -> None:
        breakdown = [
            {"event_type": "BOOKING_CANCELED", "rejection_code": "BOOKING_NOT_FOUND",
             "total": 2, "pending": 2, "replayed": 0}
        ]
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count", return_value=2), \
             patch("adapters.ota.dlq_inspector.get_replayed_count", return_value=0), \
             patch("adapters.ota.dlq_inspector.get_rejection_breakdown", return_value=breakdown):
            resp = _make_app().get("/admin/dlq")
        assert resp.json()["breakdown"] == breakdown

    def test_B4_tenant_id_in_response(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count", return_value=0), \
             patch("adapters.ota.dlq_inspector.get_replayed_count", return_value=0), \
             patch("adapters.ota.dlq_inspector.get_rejection_breakdown", return_value=[]):
            resp = _make_app(tenant_id="my-tenant").get("/admin/dlq")
        assert resp.json()["tenant_id"] == "my-tenant"

    def test_B5_empty_breakdown_is_list(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count", return_value=0), \
             patch("adapters.ota.dlq_inspector.get_replayed_count", return_value=0), \
             patch("adapters.ota.dlq_inspector.get_rejection_breakdown", return_value=[]):
            resp = _make_app().get("/admin/dlq")
        assert isinstance(resp.json()["breakdown"], list)

    def test_B6_500_on_exception(self) -> None:
        db = MagicMock()
        with patch("api.admin_router._get_supabase_client", return_value=db), \
             patch("adapters.ota.dlq_inspector.get_pending_count",
                   side_effect=RuntimeError("DB down")):
            resp = _make_app().get("/admin/dlq")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Group C — GET /admin/health/providers
# ---------------------------------------------------------------------------

class TestAdminHealthProviders:

    def _make_db_for_providers(self, provider_rows: dict) -> MagicMock:
        """
        provider_rows: {"bookingcom": [{"recorded_at": "2026-..."}], "airbnb": [], ...}
        Each call to db.table("event_log").select(...).eq(tenant).eq(source).order().limit().execute()
        returns the matching data.
        """
        db = MagicMock()
        call_count = [0]
        providers_list = ["bookingcom", "airbnb", "expedia", "agoda", "tripcom"]

        def _execute():
            idx = call_count[0]
            call_count[0] += 1
            provider = providers_list[idx] if idx < len(providers_list) else None
            data = provider_rows.get(provider, []) if provider else []
            return MagicMock(data=data)

        chain = db.table.return_value.select.return_value
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.side_effect = lambda: _execute()
        return db

    def test_C1_200_status_code(self) -> None:
        db = self._make_db_for_providers({})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        assert resp.status_code == 200

    def test_C2_providers_list_present(self) -> None:
        db = self._make_db_for_providers({})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        body = resp.json()
        assert "providers" in body
        assert isinstance(body["providers"], list)

    def test_C3_known_providers_in_response(self) -> None:
        db = self._make_db_for_providers({})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        names = {p["provider"] for p in resp.json()["providers"]}
        assert "bookingcom" in names
        assert "airbnb" in names

    def test_C4_ok_status_when_data_found(self) -> None:
        db = self._make_db_for_providers({"bookingcom": [{"recorded_at": "2026-03-09T10:00:00Z"}]})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        providers = resp.json()["providers"]
        bc = next(p for p in providers if p["provider"] == "bookingcom")
        assert bc["status"] == "ok"
        assert bc["last_ingest_at"] == "2026-03-09T10:00:00Z"

    def test_C5_unknown_status_when_no_data(self) -> None:
        db = self._make_db_for_providers({})  # all providers empty
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        providers = resp.json()["providers"]
        for p in providers:
            assert p["status"] == "unknown"
            assert p["last_ingest_at"] is None

    def test_C6_checked_at_present(self) -> None:
        db = self._make_db_for_providers({})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/health/providers")
        assert "checked_at" in resp.json()

    def test_C7_tenant_id_in_response(self) -> None:
        db = self._make_db_for_providers({})
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app(tenant_id="hotel-corp").get("/admin/health/providers")
        assert resp.json()["tenant_id"] == "hotel-corp"


# ---------------------------------------------------------------------------
# Group D — GET /admin/bookings/{id}/timeline
# ---------------------------------------------------------------------------

class TestAdminBookingTimeline:

    def _mock_db_timeline(self, events: list) -> MagicMock:
        db = MagicMock()
        chain = db.table.return_value.select.return_value
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.execute.return_value = MagicMock(data=events)
        return db

    def _event(self, kind: str = "BOOKING_CREATED", occurred_at: str = "2026-10-01T00:00:00Z") -> dict:
        return {
            "event_kind": kind,
            "occurred_at": occurred_at,
            "recorded_at": "2026-10-01T00:01:00Z",
            "envelope_id": "env-001",
        }

    def test_D1_200_when_events_found(self) -> None:
        db = self._mock_db_timeline([self._event()])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/bookingcom_res1/timeline")
        assert resp.status_code == 200

    def test_D2_events_list_in_response(self) -> None:
        db = self._mock_db_timeline([self._event(), self._event("BOOKING_AMENDED")])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/bookingcom_res1/timeline")
        body = resp.json()
        assert "events" in body
        assert len(body["events"]) == 2

    def test_D3_event_fields_present(self) -> None:
        db = self._mock_db_timeline([self._event()])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/bookingcom_res1/timeline")
        event = resp.json()["events"][0]
        for field in ("event_kind", "occurred_at", "recorded_at", "envelope_id"):
            assert field in event, f"Missing field: {field}"

    def test_D4_booking_id_in_response(self) -> None:
        db = self._mock_db_timeline([self._event()])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/bookingcom_res99/timeline")
        assert resp.json()["booking_id"] == "bookingcom_res99"

    def test_D5_tenant_id_in_response(self) -> None:
        db = self._mock_db_timeline([self._event()])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app(tenant_id="tenant-x").get("/admin/bookings/bk1/timeline")
        assert resp.json()["tenant_id"] == "tenant-x"

    def test_D6_404_when_no_events(self) -> None:
        db = self._mock_db_timeline([])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/unknown_booking/timeline")
        assert resp.status_code == 404

    def test_D7_404_body_code(self) -> None:
        db = self._mock_db_timeline([])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/unknown_booking/timeline")
        assert resp.json()["code"] == "BOOKING_NOT_FOUND"

    def test_D8_404_body_includes_booking_id(self) -> None:
        db = self._mock_db_timeline([])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app().get("/admin/bookings/bk_404_test/timeline")
        assert resp.json()["booking_id"] == "bk_404_test"

    def test_D9_cross_tenant_returns_404(self) -> None:
        """event_log filtering by tenant_id on DB side → empty → 404."""
        db = self._mock_db_timeline([])
        with patch("api.admin_router._get_supabase_client", return_value=db):
            resp = _make_app(tenant_id="attacker").get("/admin/bookings/victim_bk/timeline")
        assert resp.status_code == 404

    def test_D10_500_on_unexpected_exception(self) -> None:
        """
        _get_booking_timeline swallows internal DB errors and returns [].
        To trigger the outer 500 handler we must patch _get_booking_timeline itself.
        """
        with patch("api.admin_router._get_booking_timeline",
                   side_effect=RuntimeError("fatal error")), \
             patch("api.admin_router._get_supabase_client", return_value=MagicMock()):
            resp = _make_app().get("/admin/bookings/bk1/timeline")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Group E — Shared auth guard tests
# ---------------------------------------------------------------------------

class TestAdminAuthGuards:

    def test_E1_metrics_403_when_auth_rejected(self) -> None:
        resp = _reject_app().get("/admin/metrics")
        assert resp.status_code == 403

    def test_E2_dlq_403_when_auth_rejected(self) -> None:
        resp = _reject_app().get("/admin/dlq")
        assert resp.status_code == 403

    def test_E3_health_providers_403_when_auth_rejected(self) -> None:
        resp = _reject_app().get("/admin/health/providers")
        assert resp.status_code == 403

    def test_E4_timeline_403_when_auth_rejected(self) -> None:
        resp = _reject_app().get("/admin/bookings/bk1/timeline")
        assert resp.status_code == 403
