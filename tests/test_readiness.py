"""
Phase 211 — Readiness Probe Contract Tests
============================================

Tests for GET /readiness — the Kubernetes-style readiness endpoint.

The readiness probe answers "can this instance serve traffic right now?"
Unlike /health (liveness), readiness should return 503 when Supabase
is unreachable, signaling load balancers to stop routing traffic.
"""
from __future__ import annotations

import types
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Import and return a TestClient for the main app."""
    import main  # noqa: E402
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Test: readiness returns 200 when Supabase is reachable
# ---------------------------------------------------------------------------

class TestReadinessOk:
    """GET /readiness returns 200 when all dependency checks pass."""

    def test_readiness_ok(self):
        """Readiness returns 200 with ready=True when Supabase is reachable."""
        mock_result = types.SimpleNamespace(
            status="ok",
            version="0.1.0",
            env="test",
            checks={"supabase": {"status": "ok", "latency_ms": 42, "http": 200}},
            http_status=200,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            resp = client.get("/readiness")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["status"] == "ok"
        assert "version" in body

    def test_readiness_ok_when_degraded(self):
        """Readiness returns 200 even when status=degraded (DLQ non-empty).

        Degraded means the process can serve traffic but has pending work.
        The readiness probe should still return 200.
        """
        mock_result = types.SimpleNamespace(
            status="degraded",
            version="0.1.0",
            env="test",
            checks={
                "supabase": {"status": "ok", "latency_ms": 55, "http": 200},
                "dlq": {"status": "ok", "unprocessed_count": 3},
            },
            http_status=200,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            resp = client.get("/readiness")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True
        assert body["status"] == "degraded"

    def test_readiness_ok_when_supabase_skipped(self):
        """Readiness returns 200 when SUPABASE_URL is not set (dev mode).

        status=skipped means no URL configured — common in local dev.
        Readiness should still pass.
        """
        mock_result = types.SimpleNamespace(
            status="ok",
            version="0.1.0",
            env="development",
            checks={"supabase": {"status": "skipped", "reason": "SUPABASE_URL not set"}},
            http_status=200,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            resp = client.get("/readiness")

        assert resp.status_code == 200
        body = resp.json()
        assert body["ready"] is True


# ---------------------------------------------------------------------------
# Test: readiness returns 503 when Supabase is unreachable
# ---------------------------------------------------------------------------

class TestReadinessNotReady:
    """GET /readiness returns 503 when Supabase is unreachable."""

    def test_readiness_503_when_supabase_unreachable(self):
        """Readiness returns 503 with ready=False when Supabase is down."""
        mock_result = types.SimpleNamespace(
            status="unhealthy",
            version="0.1.0",
            env="production",
            checks={"supabase": {"status": "unreachable", "error": "Connection refused"}},
            http_status=503,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            resp = client.get("/readiness")

        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False
        assert body["status"] == "unhealthy"

    def test_readiness_503_when_supabase_check_missing(self):
        """Edge case: no supabase key in checks dict → not ready."""
        mock_result = types.SimpleNamespace(
            status="unhealthy",
            version="0.1.0",
            env="production",
            checks={},
            http_status=503,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            resp = client.get("/readiness")

        assert resp.status_code == 503
        body = resp.json()
        assert body["ready"] is False


# ---------------------------------------------------------------------------
# Test: readiness requires no authentication
# ---------------------------------------------------------------------------

class TestReadinessNoAuth:
    """GET /readiness is accessible without JWT (no auth required)."""

    def test_readiness_no_jwt_needed(self):
        """Readiness endpoint must be accessible without authentication.

        Load balancers and Kubernetes probes don't carry JWTs.
        """
        mock_result = types.SimpleNamespace(
            status="ok",
            version="0.1.0",
            env="test",
            checks={"supabase": {"status": "ok", "latency_ms": 10, "http": 200}},
            http_status=200,
        )

        with patch("main.run_health_checks", return_value=mock_result):
            client = _make_client()
            # No Authorization header
            resp = client.get("/readiness")

        # Must not return 401 or 403
        assert resp.status_code == 200
