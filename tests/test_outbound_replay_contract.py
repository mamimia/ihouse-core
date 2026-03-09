"""
Phase 147 — Contract Tests: Failed Sync Replay

POST /admin/outbound-replay

Groups:
  A — Response shape: 200 with replayed:true, booking_id, provider, result, replayed_at
  B — 400 when booking_id missing from body
  C — 400 when provider missing from body
  D — 404 when no prior log row exists for booking+provider
  E — Successful replay: result.status present and is a valid status
  F — execute_single_provider called with correct args
  G — strategy and external_id taken from log row
  H — Tenant isolation: _fetch_last_log_row scoped to tenant
  I — DB error on log lookup → 200 with 404-like (no row means 404)
  J — Router smoke: POST route exists
  K — execute_single_provider unit tests (direct, no HTTP)
  L — _fetch_last_log_row unit tests
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")

TENANT_A   = "dev-tenant"   # what jwt_auth returns in no-secret mode
BOOKING_1  = "airbnb_BK001"
PROVIDER   = "airbnb"
EXT_ID     = "AIRBNB-EXT-001"
STRATEGY   = "api_first"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_log_row(
    provider:    str = PROVIDER,
    external_id: str = EXT_ID,
    strategy:    str = STRATEGY,
    status:      str = "failed",
    synced_at:   str = "2026-03-10T01:00:00+00:00",
) -> dict:
    return {
        "provider":    provider,
        "external_id": external_id,
        "strategy":    strategy,
        "status":      status,
        "synced_at":   synced_at,
    }


def _make_db(rows: Optional[List[dict]] = None, fail: bool = False) -> MagicMock:
    q = MagicMock()
    q.eq.return_value = q
    q.order.return_value = q
    q.limit.return_value = q
    if fail:
        q.execute.side_effect = RuntimeError("DB error")
    else:
        q.execute.return_value = MagicMock(data=rows or [])
    db = MagicMock()
    db.table.return_value.select.return_value = q
    return db


def _make_app() -> TestClient:
    from fastapi import FastAPI
    from api.outbound_log_router import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _stub_execute_result(status: str = "ok") -> MagicMock:
    """Returns a fake ExecutionReport-like object for execute_single_provider mock."""
    from services.outbound_executor import ExecutionReport, ExecutionResult
    result = ExecutionResult(
        provider=PROVIDER,
        external_id=EXT_ID,
        strategy=STRATEGY,
        status=status,
        http_status=200 if status == "ok" else None,
        message="replayed",
    )
    report = ExecutionReport(
        booking_id=BOOKING_1,
        property_id="",
        tenant_id=TENANT_A,
        total_actions=1,
        ok_count=1 if status == "ok" else 0,
        failed_count=0,
        skip_count=0,
        dry_run=False,
        results=[result],
    )
    return report


def _post_replay(
    body: dict,
    db_rows: Optional[List[dict]] = None,
    db_fail: bool = False,
    execute_status: str = "ok",
):
    db = _make_db(rows=db_rows, fail=db_fail)
    c  = _make_app()
    fake_report = _stub_execute_result(execute_status)
    with (
        patch("api.outbound_log_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=TENANT_A),
        patch(
            "api.outbound_log_router.replay_outbound_sync.__globals__",   # won't work — use module patch
        ) if False else patch(
            "services.outbound_executor.execute_single_provider",
            return_value=fake_report,
        ),
    ):
        resp = c.post(
            "/admin/outbound-replay",
            json=body,
            headers={"Authorization": "Bearer fake.jwt"},
        )
    return resp, db


# simpler version that patches correctly
def _replay(
    body: dict,
    db_rows: Optional[List[dict]] = None,
    db_fail: bool = False,
    execute_status: str = "ok",
):
    db = _make_db(rows=db_rows, fail=db_fail)
    c  = _make_app()
    fake_report = _stub_execute_result(execute_status)

    with (
        patch("api.outbound_log_router._get_supabase_client", return_value=db),
        patch("api.auth.jwt_auth", return_value=TENANT_A),
        patch("services.outbound_executor.execute_single_provider", return_value=fake_report),
    ):
        resp = c.post(
            "/admin/outbound-replay",
            json=body,
            headers={"Authorization": "Bearer fake.jwt"},
        )
    return resp, db


# ===========================================================================
# Group A — 200 response shape
# ===========================================================================

class TestResponseShape:

    def _body(self):
        resp, _ = _replay(
            {"booking_id": BOOKING_1, "provider": PROVIDER},
            db_rows=[_make_log_row()],
        )
        return resp.json()

    def test_returns_200(self):
        resp, _ = _replay(
            {"booking_id": BOOKING_1, "provider": PROVIDER},
            db_rows=[_make_log_row()],
        )
        assert resp.status_code == 200

    def test_replayed_true(self):
        assert self._body()["replayed"] is True

    def test_booking_id_in_response(self):
        assert self._body()["booking_id"] == BOOKING_1

    def test_provider_in_response(self):
        assert self._body()["provider"] == PROVIDER

    def test_has_result_field(self):
        assert "result" in self._body()

    def test_has_replayed_at(self):
        body = self._body()
        assert "replayed_at" in body
        assert isinstance(body["replayed_at"], str)

    def test_result_has_status(self):
        result = self._body()["result"]
        assert "status" in result

    def test_result_has_provider(self):
        result = self._body()["result"]
        assert "provider" in result


# ===========================================================================
# Group B — 400 when booking_id missing
# ===========================================================================

class TestMissingBookingId:

    def test_missing_booking_id_returns_400(self):
        resp, _ = _replay({"provider": PROVIDER}, db_rows=[])
        assert resp.status_code == 400

    def test_empty_booking_id_returns_400(self):
        resp, _ = _replay({"booking_id": "  ", "provider": PROVIDER}, db_rows=[])
        assert resp.status_code == 400

    def test_400_body_has_code(self):
        resp, _ = _replay({"provider": PROVIDER}, db_rows=[])
        assert "code" in resp.json()


# ===========================================================================
# Group C — 400 when provider missing
# ===========================================================================

class TestMissingProvider:

    def test_missing_provider_returns_400(self):
        resp, _ = _replay({"booking_id": BOOKING_1}, db_rows=[])
        assert resp.status_code == 400

    def test_empty_provider_returns_400(self):
        resp, _ = _replay({"booking_id": BOOKING_1, "provider": ""}, db_rows=[])
        assert resp.status_code == 400


# ===========================================================================
# Group D — 404 when no prior log row
# ===========================================================================

class TestNoLogRow:

    def test_no_log_row_returns_404(self):
        resp, _ = _replay({"booking_id": BOOKING_1, "provider": PROVIDER}, db_rows=[])
        assert resp.status_code == 404

    def test_404_body_has_code(self):
        resp, _ = _replay({"booking_id": BOOKING_1, "provider": PROVIDER}, db_rows=[])
        assert "code" in resp.json()


# ===========================================================================
# Group E — successful replay statuses
# ===========================================================================

class TestReplayStatuses:

    @pytest.mark.parametrize("status", ["ok", "failed", "dry_run"])
    def test_result_status_propagated(self, status):
        resp, _ = _replay(
            {"booking_id": BOOKING_1, "provider": PROVIDER},
            db_rows=[_make_log_row(status="failed")],
            execute_status=status,
        )
        assert resp.status_code == 200
        assert resp.json()["result"]["status"] == status


# ===========================================================================
# Group F — execute_single_provider called with correct args
# ===========================================================================

class TestExecuteCalledCorrectly:

    def test_execute_called_once(self):
        db = _make_db(rows=[_make_log_row()])
        c  = _make_app()
        fake_report = _stub_execute_result()
        mock_exec = MagicMock(return_value=fake_report)

        with (
            patch("api.outbound_log_router._get_supabase_client", return_value=db),
            patch("api.auth.jwt_auth", return_value=TENANT_A),
            patch("services.outbound_executor.execute_single_provider", mock_exec),
        ):
            c.post(
                "/admin/outbound-replay",
                json={"booking_id": BOOKING_1, "provider": PROVIDER},
                headers={"Authorization": "Bearer fake.jwt"},
            )

        mock_exec.assert_called_once()
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["booking_id"]  == BOOKING_1
        assert kwargs["provider"]    == PROVIDER
        assert kwargs["tenant_id"]   == TENANT_A

    def test_execute_not_called_on_404(self):
        db = _make_db(rows=[])
        c  = _make_app()
        mock_exec = MagicMock()

        with (
            patch("api.outbound_log_router._get_supabase_client", return_value=db),
            patch("api.auth.jwt_auth", return_value=TENANT_A),
            patch("services.outbound_executor.execute_single_provider", mock_exec),
        ):
            c.post(
                "/admin/outbound-replay",
                json={"booking_id": BOOKING_1, "provider": PROVIDER},
                headers={"Authorization": "Bearer fake.jwt"},
            )

        mock_exec.assert_not_called()


# ===========================================================================
# Group G — strategy and external_id taken from log row
# ===========================================================================

class TestStrategyFromLogRow:

    def test_strategy_from_row_passed_to_execute(self):
        db = _make_db(rows=[_make_log_row(strategy="ical_fallback", external_id="ICAL-001")])
        c  = _make_app()
        fake_report = _stub_execute_result()
        mock_exec = MagicMock(return_value=fake_report)

        with (
            patch("api.outbound_log_router._get_supabase_client", return_value=db),
            patch("api.auth.jwt_auth", return_value=TENANT_A),
            patch("services.outbound_executor.execute_single_provider", mock_exec),
        ):
            c.post(
                "/admin/outbound-replay",
                json={"booking_id": BOOKING_1, "provider": PROVIDER},
                headers={"Authorization": "Bearer fake.jwt"},
            )

        kwargs = mock_exec.call_args.kwargs
        assert kwargs["strategy"]    == "ical_fallback"
        assert kwargs["external_id"] == "ICAL-001"


# ===========================================================================
# Group H — tenant isolation in log lookup
# ===========================================================================

class TestTenantIsolation:

    def test_lookup_scoped_to_tenant(self):
        db = _make_db(rows=[_make_log_row()])
        c  = _make_app()
        fake_report = _stub_execute_result()

        with (
            patch("api.outbound_log_router._get_supabase_client", return_value=db),
            patch("api.auth.jwt_auth", return_value=TENANT_A),
            patch("services.outbound_executor.execute_single_provider", return_value=fake_report),
        ):
            c.post(
                "/admin/outbound-replay",
                json={"booking_id": BOOKING_1, "provider": PROVIDER},
                headers={"Authorization": "Bearer fake.jwt"},
            )

        q  = db.table.return_value.select.return_value
        eq_fields = [c[0][0] for c in q.eq.call_args_list]
        assert "tenant_id" in eq_fields


# ===========================================================================
# Group I — DB error on lookup returns 404 (no row = 404)
# ===========================================================================

class TestDbErrorOnLookup:

    def test_db_error_returns_404(self):
        """When _fetch_last_log_row catches an exception it returns None → 404."""
        resp, _ = _replay(
            {"booking_id": BOOKING_1, "provider": PROVIDER},
            db_fail=True,
        )
        assert resp.status_code == 404


# ===========================================================================
# Group J — route smoke
# ===========================================================================

class TestRouteSmoke:

    def test_replay_route_exists(self):
        from api.outbound_log_router import router
        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert "/admin/outbound-replay" in paths

    def test_replay_route_is_post(self):
        from api.outbound_log_router import router
        r = next(x for x in router.routes if x.path == "/admin/outbound-replay")  # type: ignore[attr-defined]
        assert "POST" in r.methods  # type: ignore[attr-defined]


# ===========================================================================
# Group K — execute_single_provider unit tests
# ===========================================================================

class TestExecuteSingleProviderUnit:

    def _run(self, **kwargs):
        from services.outbound_executor import execute_single_provider

        class DryAdapter:
            @staticmethod
            def send(**kw):
                from services.outbound_executor import ExecutionResult
                return ExecutionResult(
                    provider=kw["provider"] if "provider" in kw else PROVIDER,
                    external_id=kw.get("external_id", EXT_ID),
                    strategy="api_first",
                    status="ok",
                    http_status=200,
                    message="ok",
                )

        defaults = dict(
            booking_id="BK1",
            property_id="PROP1",
            tenant_id="t1",
            provider=PROVIDER,
            external_id=EXT_ID,
            strategy="api_first",
            api_adapter=DryAdapter,
            ical_adapter=DryAdapter,
        )
        defaults.update(kwargs)
        return execute_single_provider(**defaults)

    def test_returns_execution_report(self):
        from services.outbound_executor import ExecutionReport
        result = self._run()
        assert isinstance(result, ExecutionReport)

    def test_report_has_one_result(self):
        report = self._run()
        assert len(report.results) == 1

    def test_booking_id_propagated(self):
        report = self._run(booking_id="MY_BOOKING")
        assert report.booking_id == "MY_BOOKING"

    def test_provider_in_result(self):
        report = self._run()
        assert report.results[0].provider == PROVIDER


# ===========================================================================
# Group L — _fetch_last_log_row unit tests
# ===========================================================================

class TestFetchLastLogRowUnit:

    def _call(self, rows: List[dict], fail: bool = False) -> Optional[dict]:
        from api.outbound_log_router import _fetch_last_log_row
        db = _make_db(rows=rows, fail=fail)
        return _fetch_last_log_row(db, TENANT_A, BOOKING_1, PROVIDER)

    def test_returns_none_when_no_rows(self):
        assert self._call([]) is None

    def test_returns_first_row_when_present(self):
        row = _make_log_row()
        result = self._call([row])
        assert result == row

    def test_returns_none_on_db_error(self):
        assert self._call([], fail=True) is None

    def test_tenant_eq_called(self):
        from api.outbound_log_router import _fetch_last_log_row
        db = _make_db(rows=[])
        _fetch_last_log_row(db, TENANT_A, BOOKING_1, PROVIDER)
        q = db.table.return_value.select.return_value
        eq_fields = [c[0][0] for c in q.eq.call_args_list]
        assert "tenant_id" in eq_fields
        assert "booking_id" in eq_fields
        assert "provider"   in eq_fields
