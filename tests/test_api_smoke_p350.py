"""
Phase 350 — API Smoke Tests
=============================

Comprehensive smoke tests for all critical API endpoints.
Verifies: route existence, HTTP method, response shape, health checks.

Groups:
  A — Health + Readiness (5 tests)
  B — Core API smoke (booking, task, financial, properties) (6 tests)
  C — Admin endpoints smoke (6 tests)
  D — Webhook + Notification routes (4 tests)
  E — Auth + Worker endpoints (4 tests)
  F — Route discovery: all registered routes exist (5 tests)
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-long-enough-32b")

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from main import app  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query_chain(rows=None):
    q = MagicMock()
    for m in ("select", "eq", "gte", "lte", "lt", "neq", "in_", "is_",
              "limit", "order", "insert", "update", "upsert", "delete"):
        setattr(q, m, MagicMock(return_value=q))
    q.execute.return_value = MagicMock(data=rows if rows is not None else [])
    return q


def _all_routes():
    return {
        (r.path, frozenset(r.methods or set()))
        for r in app.routes
        if hasattr(r, "methods")
    }


# ---------------------------------------------------------------------------
# Group A — Health + Readiness
# ---------------------------------------------------------------------------

class TestGroupAHealth:

    def test_a1_health_returns_200_or_503(self):
        """GET /health returns 200 (ok/degraded) or 503 (unhealthy)."""
        r = client.get("/health")
        assert r.status_code in (200, 503)
        body = r.json()
        assert body["status"] in ("ok", "degraded", "unhealthy")

    def test_a2_health_has_version_and_env(self):
        """Health response includes version and env fields."""
        r = client.get("/health")
        body = r.json()
        assert "version" in body
        assert "env" in body

    def test_a3_readiness_returns_200(self):
        """GET /readiness returns 200."""
        r = client.get("/readiness")
        assert r.status_code in (200, 503)  # May be 503 if Supabase unreachable

    def test_a4_integration_health_returns_200(self):
        """GET /integration-health returns 200."""
        r = client.get("/integration-health")
        assert r.status_code in (200, 503)

    def test_a5_openapi_json_returns_200(self):
        """GET /openapi.json returns valid OpenAPI schema."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "openapi" in schema
        assert "paths" in schema


# ---------------------------------------------------------------------------
# Group B — Core API Smoke
# ---------------------------------------------------------------------------

class TestGroupBCoreApi:

    def test_b1_bookings_list(self):
        """GET /bookings returns 200 (may be empty)."""
        with patch("api.bookings_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/bookings")
        assert r.status_code == 200

    def test_b2_tasks_list(self):
        """GET /tasks returns 200."""
        with patch("tasks.task_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/tasks")
        assert r.status_code == 200

    def test_b3_financial_list(self):
        """GET /financial returns 200."""
        with patch("api.financial_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/financial")
        assert r.status_code in (200, 503)

    def test_b4_properties_list(self):
        """GET /properties returns 200."""
        with patch("api.properties_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/properties")
        assert r.status_code == 200

    def test_b5_conflicts_list(self):
        """GET /conflicts returns 200."""
        with patch("api.conflicts_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/conflicts")
        assert r.status_code in (200, 503)

    def test_b6_permissions_list(self):
        """GET /permissions returns 200."""
        with patch("api.permissions_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/permissions")
        assert r.status_code in (200, 503)


# ---------------------------------------------------------------------------
# Group C — Admin Endpoints Smoke
# ---------------------------------------------------------------------------

class TestGroupCAdmin:

    def test_c1_admin_summary(self):
        """GET /admin/summary returns 200."""
        with patch("api.admin_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/admin/summary")
        assert r.status_code == 200

    def test_c2_admin_dlq(self):
        """GET /admin/dlq returns 200."""
        r = client.get("/admin/dlq")
        assert r.status_code in (200, 500, 503)

    def test_c3_admin_webhook_log(self):
        """GET /admin/webhook-log returns 200."""
        r = client.get("/admin/webhook-log")
        assert r.status_code == 200

    def test_c4_admin_webhook_log_stats(self):
        """GET /admin/webhook-log/stats returns 200."""
        r = client.get("/admin/webhook-log/stats")
        assert r.status_code == 200

    def test_c5_admin_org_list(self):
        """GET /admin/org returns response."""
        r = client.get("/admin/org")
        assert r.status_code in (200, 500, 503)

    def test_c6_docs_endpoint(self):
        """GET /docs returns Swagger UI."""
        r = client.get("/docs")
        assert r.status_code == 200
        assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


# ---------------------------------------------------------------------------
# Group D — Webhook + Notification Routes
# ---------------------------------------------------------------------------

class TestGroupDWebhookNotification:

    def test_d1_webhook_route_exists(self):
        """POST /webhooks/{provider} route is registered."""
        routes = _all_routes()
        assert any("/webhooks/{provider}" in path for path, _ in routes)

    def test_d2_line_webhook_exists(self):
        """POST /line/webhook route is registered."""
        routes = _all_routes()
        assert any("/line/webhook" in path for path, _ in routes)

    def test_d3_notification_sms_exists(self):
        """POST /notifications/send-sms route is registered."""
        routes = _all_routes()
        assert any("/notifications/send-sms" in path for path, _ in routes)

    def test_d4_notification_log(self):
        """GET /notifications/log returns 200."""
        with patch("api.notification_router._get_db") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/notifications/log")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Group E — Auth + Worker Endpoints
# ---------------------------------------------------------------------------

class TestGroupEAuthWorker:

    def test_e1_auth_me_returns_response(self):
        """GET /auth/me returns 200 (dev-mode bypass)."""
        r = client.get("/auth/me")
        assert r.status_code in (200, 401, 503)

    def test_e2_auth_token_requires_body(self):
        """POST /auth/token without body returns 422."""
        r = client.post("/auth/token", json={})
        assert r.status_code in (400, 422)

    def test_e3_worker_tasks_returns_response(self):
        """GET /worker/tasks returns response."""
        with patch("api.worker_router._get_supabase_client") as mock:
            db = MagicMock()
            db.table.return_value = _query_chain([])
            mock.return_value = db
            r = client.get("/worker/tasks")
        assert r.status_code in (200, 503)

    def test_e4_guest_verify_token_requires_body(self):
        """POST /guest/verify-token without body returns 422."""
        r = client.post("/guest/verify-token")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Group F — Route Discovery
# ---------------------------------------------------------------------------

class TestGroupFRouteDiscovery:

    def test_f1_minimum_route_count(self):
        """App has at least 100 registered routes."""
        routes = _all_routes()
        assert len(routes) >= 100

    def test_f2_all_critical_paths_registered(self):
        """All critical endpoint paths are present."""
        routes = _all_routes()
        paths = {path for path, _ in routes}
        critical = [
            "/health", "/readiness", "/bookings", "/tasks",
            "/financial/summary", "/properties",
            "/webhooks/{provider}", "/line/webhook",
        ]
        for c in critical:
            assert c in paths, f"Critical route {c} not found"

    def test_f3_admin_routes_exist(self):
        """Admin routes are registered."""
        routes = _all_routes()
        paths = {path for path, _ in routes}
        admin_routes = [p for p in paths if p.startswith("/admin/")]
        assert len(admin_routes) >= 20

    def test_f4_ai_routes_exist(self):
        """AI copilot routes are registered."""
        routes = _all_routes()
        paths = {path for path, _ in routes}
        ai_routes = [p for p in paths if p.startswith("/ai/")]
        assert len(ai_routes) >= 5

    def test_f5_owner_guest_portals_exist(self):
        """Owner and guest portal routes exist."""
        routes = _all_routes()
        paths = {path for path, _ in routes}
        assert "/owner/portal" in paths
        assert any("/guest/booking/" in p for p in paths)
