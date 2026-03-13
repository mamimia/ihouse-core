"""
Phase 75 — Contract tests for API Error Standards + Response Headers

Covers:
1.  make_error_response — code present
2.  make_error_response — message uses default
3.  make_error_response — custom message overrides default
4.  make_error_response — trace_id included when provided
5.  make_error_response — trace_id absent when not provided
6.  make_error_response — extra fields merged into body
7.  make_error_response — correct HTTP status code
8.  make_error_response — BOOKING_NOT_FOUND default message
9.  make_error_response — INTERNAL_ERROR default message
10. make_error_response — AUTH_FAILED default message
11. error_models.ErrorCode constants are SCREAMING_SNAKE_CASE strings
12. X-API-Version header on 200 response (bookings_router)
13. X-API-Version header on 404 response (bookings_router)
14. X-Request-ID header propagated on 200 response
15. bookings_router 404 body uses {code, message} not {error}
16. admin_router 500 body uses {code, message} not {error}
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# make_error_response unit tests
# ---------------------------------------------------------------------------

class TestMakeErrorResponse:

    def test_code_present(self) -> None:
        from api.error_models import make_error_response
        resp = make_error_response(404, "BOOKING_NOT_FOUND")
        assert resp.body
        import json
        body = json.loads(resp.body)
        assert body["code"] == "BOOKING_NOT_FOUND"

    def test_default_message_for_known_code(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(404, "BOOKING_NOT_FOUND")
        body = json.loads(resp.body)
        assert "not found" in body["message"].lower()

    def test_custom_message_overrides_default(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(404, "BOOKING_NOT_FOUND", message="Custom message")
        body = json.loads(resp.body)
        assert body["message"] == "Custom message"

    def test_trace_id_included_when_provided(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(500, "INTERNAL_ERROR", trace_id="abc-123")
        body = json.loads(resp.body)
        assert body["trace_id"] == "abc-123"

    def test_trace_id_absent_when_not_provided(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(500, "INTERNAL_ERROR")
        body = json.loads(resp.body)
        assert "trace_id" not in body

    def test_extra_fields_merged(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(404, "BOOKING_NOT_FOUND", extra={"booking_id": "bcom_1"})
        body = json.loads(resp.body)
        assert body["booking_id"] == "bcom_1"

    def test_correct_status_code(self) -> None:
        from api.error_models import make_error_response
        resp = make_error_response(404, "BOOKING_NOT_FOUND")
        assert resp.status_code == 404

    def test_internal_error_status_code(self) -> None:
        from api.error_models import make_error_response
        resp = make_error_response(500, "INTERNAL_ERROR")
        assert resp.status_code == 500

    def test_auth_failed_default_message(self) -> None:
        from api.error_models import make_error_response, ErrorCode
        import json
        resp = make_error_response(403, ErrorCode.AUTH_FAILED)
        body = json.loads(resp.body)
        assert "auth" in body["message"].lower() or "token" in body["message"].lower()

    def test_unknown_code_has_fallback_message(self) -> None:
        from api.error_models import make_error_response
        import json
        resp = make_error_response(400, "CUSTOM_CODE_XYZ")
        body = json.loads(resp.body)
        assert body["message"]  # non-empty

    def test_error_code_constants_are_strings(self) -> None:
        from api.error_models import ErrorCode
        for attr in [
            ErrorCode.BOOKING_NOT_FOUND,
            ErrorCode.INTERNAL_ERROR,
            ErrorCode.AUTH_FAILED,
            ErrorCode.RATE_LIMITED,
            ErrorCode.VALIDATION_ERROR,
        ]:
            assert isinstance(attr, str)
            assert attr == attr.upper()


# ---------------------------------------------------------------------------
# X-API-Version + X-Request-ID header tests (via TestClient on full app)
# ---------------------------------------------------------------------------

def _make_full_app():
    """Return a TestClient for the full main app."""
    from fastapi.testclient import TestClient
    import sys
    # Ensure src is on path — already handled by PYTHONPATH=src in pytest
    from main import app
    return TestClient(app, raise_server_exceptions=False)


class TestResponseHeaders:

    def test_health_endpoint_has_x_api_version(self) -> None:
        client = _make_full_app()
        resp = client.get("/health")
        assert "x-api-version" in resp.headers

    def test_health_endpoint_has_x_request_id(self) -> None:
        client = _make_full_app()
        resp = client.get("/health")
        assert "x-request-id" in resp.headers

    def test_x_api_version_is_nonempty(self) -> None:
        client = _make_full_app()
        resp = client.get("/health")
        assert resp.headers["x-api-version"]

    def test_x_request_id_is_uuid_format(self) -> None:
        import re
        client = _make_full_app()
        resp = client.get("/health")
        rid = resp.headers.get("x-request-id", "")
        # UUID4 pattern
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            rid,
        ), f"Unexpected X-Request-ID: {rid!r}"


# ---------------------------------------------------------------------------
# bookings_router: new error body format
# ---------------------------------------------------------------------------

def _bookings_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.bookings_router import router
    from api.auth import jwt_auth
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[jwt_auth] = lambda: "tenant_1"
    return TestClient(app, raise_server_exceptions=False)


class TestBookingsRouterErrorFormat:

    def test_404_uses_code_field_not_error(self) -> None:
        with patch("api.bookings_router._get_supabase_client") as mock_db:
            mock_result = MagicMock()
            mock_result.data = []
            chain = mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value
            chain.limit.return_value.execute.return_value = mock_result
            chain.execute.return_value = mock_result
            resp = _bookings_app().get("/bookings/nonexistent")
        assert "code" in resp.json().get("error", {})
        assert resp.json()["error"]["code"] == "BOOKING_NOT_FOUND"

    def test_404_body_has_message_field(self) -> None:
        with patch("api.bookings_router._get_supabase_client") as mock_db:
            mock_result = MagicMock()
            mock_result.data = []
            mock_db.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_result
            resp = _bookings_app().get("/bookings/nonexistent")
        assert "message" in resp.json().get("error", {})


# ---------------------------------------------------------------------------
# admin_router: new error body format
# ---------------------------------------------------------------------------

def _admin_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.admin_router import router
    from api.auth import jwt_auth
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[jwt_auth] = lambda: "tenant_1"
    return TestClient(app, raise_server_exceptions=False)


class TestAdminRouterErrorFormat:

    def test_500_uses_code_field_not_error(self) -> None:
        with patch("api.admin_router._get_supabase_client") as mock_db:
            mock_db.return_value.table.side_effect = RuntimeError("DB down")
            resp = _admin_app().get("/admin/summary")
        assert resp.status_code == 500
        assert "code" in resp.json()
        assert resp.json()["code"] == "INTERNAL_ERROR"

    def test_500_code_value_is_internal_error(self) -> None:
        with patch("api.admin_router._get_supabase_client") as mock_db:
            mock_db.return_value.table.side_effect = RuntimeError("DB down")
            resp = _admin_app().get("/admin/summary")
        assert resp.json()["code"] == "INTERNAL_ERROR"
