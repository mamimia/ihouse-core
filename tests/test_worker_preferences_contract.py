"""
Phase 201 — Worker Channel Preferences — Contract Tests

Endpoints:
    GET    /worker/preferences
    PUT    /worker/preferences
    DELETE /worker/preferences/{channel_type}

Groups:
    A — GET /worker/preferences
    B — PUT /worker/preferences — happy path + validation
    C — DELETE /worker/preferences/{channel_type}
    D — Auth guard (403)
    E — 500 guard / DB errors
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _channel_row(
    tenant_id: str = "tenant_test",
    user_id: str = "tenant_test",
    channel_type: str = "line",
    channel_id: str = "U1234567890abcdef",
    active: bool = True,
) -> dict:
    return {
        "channel_type": channel_type,
        "channel_id": channel_id,
        "active": active,
        "created_at": "2026-03-10T10:00:00+00:00",
        "updated_at": "2026-03-10T10:00:00+00:00",
    }


def _mock_db_list(rows: list) -> MagicMock:
    """Mock for simple SELECT queries on notification_channels."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.eq.return_value = chain
    chain.select.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _mock_db_upsert(upserted_row: dict | None = None) -> MagicMock:
    """Mock for upsert (PUT) on notification_channels."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[upserted_row] if upserted_row else [])
    chain.eq.return_value = chain
    chain.upsert.return_value = chain
    db = MagicMock()
    db.table.return_value.upsert.return_value = chain
    return db


def _mock_db_update(updated_row: dict | None = None) -> MagicMock:
    """Mock for update (DELETE sets active=False) on notification_channels."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[updated_row] if updated_row else [])
    chain.eq.return_value = chain
    chain.update.return_value = chain
    db = MagicMock()
    db.table.return_value.update.return_value = chain
    return db


def _make_app(tenant_id: str = "tenant_test") -> TestClient:
    from fastapi import FastAPI
    from api.worker_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_reject_app() -> TestClient:
    from fastapi import FastAPI, HTTPException
    from api.worker_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


# ===========================================================================
# Group A — GET /worker/preferences
# ===========================================================================

class TestGroupA_GetPreferences:

    def test_a1_get_empty_channels_returns_200(self) -> None:
        """A1: No channels registered → 200 with empty list."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert "user_id" in body
        assert body["channels"] == []

    def test_a2_get_returns_active_channels(self) -> None:
        """A2: One active channel → 200, channels list has 1 entry."""
        c = _make_app()
        row = _channel_row()
        db = _mock_db_list([row])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["channels"]) == 1
        assert body["channels"][0]["channel_type"] == "line"

    def test_a3_get_returns_user_id(self) -> None:
        """A3: Response includes user_id matching the tenant (fallback)."""
        c = _make_app(tenant_id="tenant-abc")
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/preferences").json()
        assert body["user_id"] == "tenant-abc"

    def test_a4_get_multiple_channels(self) -> None:
        """A4: Multiple channels → all returned."""
        c = _make_app()
        rows = [
            _channel_row(channel_type="line", channel_id="U123"),
            _channel_row(channel_type="whatsapp", channel_id="+6600000001"),
        ]
        db = _mock_db_list(rows)
        with patch("api.worker_router._get_supabase_client", return_value=db):
            body = c.get("/worker/preferences").json()
        assert len(body["channels"]) == 2

    def test_a5_get_db_error_returns_500(self) -> None:
        """A5: DB error on GET → 500 INTERNAL_ERROR."""
        c = _make_app()
        chain = MagicMock()
        chain.execute.side_effect = RuntimeError("db down")
        chain.eq.return_value = chain
        chain.select.return_value = chain
        db = MagicMock()
        db.table.return_value.select.return_value = chain
        with patch("api.worker_router._get_supabase_client", return_value=db):
            resp = c.get("/worker/preferences")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ===========================================================================
# Group B — PUT /worker/preferences
# ===========================================================================

class TestGroupB_PutPreferences:

    def _make_register_mock(self) -> MagicMock:
        """Stub for register_channel — upserts and returns status dict."""
        mock = MagicMock(return_value={
            "status": "registered",
            "tenant_id": "tenant_test",
            "user_id": "tenant_test",
            "channel_type": "line",
            "channel_id": "U1234567890abcdef",
        })
        return mock

    def test_b1_put_line_channel_returns_200(self) -> None:
        """B1: PUT with valid line channel → 200 registered."""
        c = _make_app()
        mock_reg = self._make_register_mock()
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.register_channel", mock_reg):
            resp = c.put("/worker/preferences", json={
                "channel_type": "line",
                "channel_id": "U1234567890abcdef",
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "registered"

    def test_b2_put_whatsapp_channel_returns_200(self) -> None:
        """B2: PUT with whatsapp → 200 registered."""
        c = _make_app()
        mock_reg = MagicMock(return_value={
            "status": "registered",
            "tenant_id": "tenant_test",
            "user_id": "tenant_test",
            "channel_type": "whatsapp",
            "channel_id": "+6600000001",
        })
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.register_channel", mock_reg):
            resp = c.put("/worker/preferences", json={
                "channel_type": "whatsapp",
                "channel_id": "+6600000001",
            })
        assert resp.status_code == 200

    def test_b3_put_telegram_channel_returns_200(self) -> None:
        """B3: PUT with telegram → 200 registered."""
        c = _make_app()
        mock_reg = MagicMock(return_value={
            "status": "registered",
            "tenant_id": "tenant_test",
            "user_id": "tenant_test",
            "channel_type": "telegram",
            "channel_id": "123456789",
        })
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.register_channel", mock_reg):
            resp = c.put("/worker/preferences", json={
                "channel_type": "telegram",
                "channel_id": "123456789",
            })
        assert resp.status_code == 200

    def test_b4_put_invalid_channel_type_returns_400(self) -> None:
        """B4: PUT with invalid channel_type → 400 VALIDATION_ERROR."""
        c = _make_app()
        resp = c.put("/worker/preferences", json={
            "channel_type": "fax",
            "channel_id": "1234567890",
        })
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b5_put_missing_channel_type_returns_400(self) -> None:
        """B5: PUT with empty channel_type → 400."""
        c = _make_app()
        resp = c.put("/worker/preferences", json={"channel_id": "U123"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b6_put_missing_channel_id_returns_400(self) -> None:
        """B6: PUT with missing channel_id → 400."""
        c = _make_app()
        resp = c.put("/worker/preferences", json={"channel_type": "line"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_b7_put_no_body_returns_400(self) -> None:
        """B7: PUT with no body → 400."""
        c = _make_app()
        resp = c.put("/worker/preferences")
        assert resp.status_code == 400

    def test_b8_put_fcm_not_allowed_returns_400(self) -> None:
        """B8: PUT with fcm → 400 (not in selectable set)."""
        c = _make_app()
        resp = c.put("/worker/preferences", json={
            "channel_type": "fcm",
            "channel_id": "sometoken",
        })
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"


# ===========================================================================
# Group C — DELETE /worker/preferences/{channel_type}
# ===========================================================================

class TestGroupC_DeletePreferences:

    def _make_deregister_mock(self, channel_type: str = "line") -> MagicMock:
        return MagicMock(return_value={
            "status": "deregistered",
            "tenant_id": "tenant_test",
            "user_id": "tenant_test",
            "channel_type": channel_type,
        })

    def test_c1_delete_line_returns_200(self) -> None:
        """C1: DELETE /worker/preferences/line → 200 deregistered."""
        c = _make_app()
        mock_dereg = self._make_deregister_mock("line")
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.deregister_channel", mock_dereg):
            resp = c.delete("/worker/preferences/line")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deregistered"

    def test_c2_delete_whatsapp_returns_200(self) -> None:
        """C2: DELETE /worker/preferences/whatsapp → 200."""
        c = _make_app()
        mock_dereg = self._make_deregister_mock("whatsapp")
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.deregister_channel", mock_dereg):
            resp = c.delete("/worker/preferences/whatsapp")
        assert resp.status_code == 200

    def test_c3_delete_invalid_channel_type_returns_400(self) -> None:
        """C3: DELETE invalid channel_type → 400 VALIDATION_ERROR."""
        c = _make_app()
        resp = c.delete("/worker/preferences/smoke_signal")
        assert resp.status_code == 400
        assert resp.json()["code"] == "VALIDATION_ERROR"

    def test_c4_delete_fcm_not_allowed_returns_400(self) -> None:
        """C4: DELETE fcm → 400 (not in selectable set)."""
        c = _make_app()
        resp = c.delete("/worker/preferences/fcm")
        assert resp.status_code == 400

    def test_c5_delete_channel_type_case_insensitive(self) -> None:
        """C5: DELETE /worker/preferences/LINE (uppercase) → 200 (normalized)."""
        c = _make_app()
        mock_dereg = self._make_deregister_mock("line")
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.deregister_channel", mock_dereg):
            resp = c.delete("/worker/preferences/LINE")
        assert resp.status_code == 200

    def test_c6_delete_db_error_returns_500(self) -> None:
        """C6: DB error on deregister → 500 INTERNAL_ERROR."""
        c = _make_app()
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.deregister_channel",
                   side_effect=RuntimeError("db down")):
            resp = c.delete("/worker/preferences/line")
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"


# ===========================================================================
# Group D — Auth guard (403)
# ===========================================================================

class TestGroupD_AuthGuard:

    def test_d1_get_without_auth_returns_403(self) -> None:
        """D1: GET /worker/preferences without auth → 403."""
        assert _make_reject_app().get("/worker/preferences").status_code == 403

    def test_d2_put_without_auth_returns_403(self) -> None:
        """D2: PUT /worker/preferences without auth → 403."""
        assert _make_reject_app().put(
            "/worker/preferences",
            json={"channel_type": "line", "channel_id": "U123"},
        ).status_code == 403

    def test_d3_delete_without_auth_returns_403(self) -> None:
        """D3: DELETE /worker/preferences/line without auth → 403."""
        assert _make_reject_app().delete("/worker/preferences/line").status_code == 403


# ===========================================================================
# Group E — Error isolation
# ===========================================================================

class TestGroupE_ErrorIsolation:

    def test_e1_put_db_error_returns_500(self) -> None:
        """E1: DB error on upsert → 500 INTERNAL_ERROR."""
        c = _make_app()
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.register_channel",
                   side_effect=RuntimeError("db down")):
            resp = c.put("/worker/preferences", json={
                "channel_type": "line",
                "channel_id": "U123",
            })
        assert resp.status_code == 500
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_e2_500_does_not_leak_exception(self) -> None:
        """E2: 500 body does not contain raw exception text."""
        c = _make_app()
        with patch("api.worker_router._get_supabase_client", return_value=MagicMock()), \
             patch("channels.notification_dispatcher.register_channel",
                   side_effect=RuntimeError("super_secret_error_text")):
            body = c.put("/worker/preferences", json={
                "channel_type": "line",
                "channel_id": "U123",
            }).json()
        assert "super_secret_error_text" not in str(body)

    def test_e3_notification_channels_table_queried_not_booking_state(self) -> None:
        """E3: GET preferences must query notification_channels, not booking_state."""
        c = _make_app()
        db = _mock_db_list([])
        with patch("api.worker_router._get_supabase_client", return_value=db):
            c.get("/worker/preferences")
        calls = [str(ca) for ca in db.table.call_args_list]
        assert any("notification_channels" in ca for ca in calls)
        assert not any("booking_state" in ca for ca in calls)
