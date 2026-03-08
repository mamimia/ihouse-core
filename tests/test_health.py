"""
Contract tests for Phase 64 — Enhanced Health Check (src/api/health.py).

All checks are CI-safe: Supabase calls are mocked.
Tests run_health_checks() directly — no HTTP server needed for unit tests.
HTTP-level tests verify /health status codes via TestClient.

Coverage:
    1.  No SUPABASE_URL set → checks skipped, status=ok
    2.  Supabase ping succeeds → checks.supabase.status=ok, latency_ms present
    3.  Supabase ping fails → status=unhealthy, http_status=503
    4.  DLQ count=0 → status=ok
    5.  DLQ count>0 → status=degraded (still 200)
    6.  HTTP GET /health → 200 when checks succeed (TestClient, mocked)
    7.  HTTP GET /health → 503 when Supabase unreachable (TestClient, mocked)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int, body: bytes = b"[]", headers: dict | None = None):
    """Build a mock urllib response context manager."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = body
    mock_resp.headers = MagicMock()
    mock_resp.headers.get = lambda k, d="": {
        "Content-Range": f"0-0/{headers.get('count', 0)}" if headers else ""
    }.get(k, d)
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1: No SUPABASE_URL → checks skipped
# ---------------------------------------------------------------------------

def test_no_supabase_url_skips_checks(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from api.health import run_health_checks
    result = run_health_checks(version="0.1.0", env="test")
    assert result.status == "ok"
    assert result.checks["supabase"]["status"] == "skipped"
    assert result.checks["dlq"]["status"] == "skipped"


# ---------------------------------------------------------------------------
# Test 2: Supabase ping succeeds → ok + latency_ms
# ---------------------------------------------------------------------------

def test_supabase_ping_ok(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    mock_ping = _make_response(200, b"[]", {"count": 0})
    mock_dlq = _make_response(200, b"[]", {"count": 0})

    responses = [mock_ping, mock_dlq]
    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        from api.health import run_health_checks
        result = run_health_checks(version="0.1.0", env="test")

    assert result.status in ("ok", "degraded")  # depends on DLQ
    assert result.checks["supabase"]["status"] == "ok"
    assert "latency_ms" in result.checks["supabase"]


# ---------------------------------------------------------------------------
# Test 3: Supabase ping fails → unhealthy + 503
# ---------------------------------------------------------------------------

def test_supabase_ping_fails_returns_503(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")

    import urllib.error
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        from api.health import run_health_checks
        result = run_health_checks(version="0.1.0", env="test")

    assert result.status == "unhealthy"
    assert result.http_status == 503
    assert result.checks["supabase"]["status"] == "unreachable"


# ---------------------------------------------------------------------------
# Test 4: DLQ count=0 → status=ok
# ---------------------------------------------------------------------------

def test_dlq_empty_status_ok(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    mock_ping = _make_response(200, b"[]", {"count": 0})
    mock_dlq = _make_response(200, b"[]", {"count": 0})
    responses = [mock_ping, mock_dlq]
    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        from api.health import run_health_checks
        result = run_health_checks(version="0.1.0", env="test")

    assert result.status == "ok"
    assert result.checks["dlq"]["unprocessed_count"] == 0


# ---------------------------------------------------------------------------
# Test 5: DLQ count>0 → degraded (still 200)
# ---------------------------------------------------------------------------

def test_dlq_non_empty_status_degraded(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    mock_ping = _make_response(200, b"[]", {"count": 0})
    mock_dlq = _make_response(200, b"[]", {"count": 5})
    responses = [mock_ping, mock_dlq]
    call_count = 0

    def fake_urlopen(req, timeout=None):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    with patch("urllib.request.urlopen", fake_urlopen):
        from api.health import run_health_checks
        result = run_health_checks(version="0.1.0", env="test")

    assert result.status == "degraded"
    assert result.http_status == 200
    assert result.checks["dlq"]["unprocessed_count"] == 5


# ---------------------------------------------------------------------------
# Test 6: HTTP /health returns 200 (mocked happy path)
# ---------------------------------------------------------------------------

def test_health_endpoint_200(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "unhealthy")
    assert "version" in body
    assert "checks" in body


# ---------------------------------------------------------------------------
# Test 7: HTTP /health returns 503 when Supabase unreachable
# ---------------------------------------------------------------------------

def test_health_endpoint_503_when_db_down(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    from fastapi.testclient import TestClient
    from main import app

    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/health")

    assert resp.status_code == 503
    assert resp.json()["status"] == "unhealthy"
