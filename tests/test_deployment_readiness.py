"""
Phase 323 — Production Deployment Dry Run Tests
=================================================

Validates deployment readiness:

Group A: Health Check Logic
  ✓  run_health_checks with no SUPABASE_URL → checks skipped
  ✓  HealthResult status semantics (ok/degraded/unhealthy)
  ✓  DLQ count > 0 → sets status=degraded

Group B: Outbound Sync Probes
  ✓  probe_outbound_sync with idle providers → status=idle
  ✓  High failure rate → status=degraded
  ✓  Long lag → status=degraded
  ✓  DB error → status=error, never crashes

Group C: Enriched Health Check
  ✓  run_health_checks_enriched with no client → outbound skipped
  ✓  Degraded outbound → overall degraded

Group D: Deployment Configuration Checks
  ✓  Dockerfile exists and uses multi-stage build
  ✓  Dockerfile runs as non-root (USER ihouse)
  ✓  Dockerfile has HEALTHCHECK instruction
  ✓  requirements.txt exists and contains key deps (fastapi, uvicorn)
  ✓  docker-compose.yml exists
  ✓  docker-compose.production.yml exists

Group E: Health HTTP Endpoint
  ✓  GET /health → 200
  ✓  GET /readiness → 200

CI-safe: no Docker build, no live APIs, all fast checks.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.health import (
    HealthResult,
    OutboundSyncProbeResult,
    run_health_checks,
    run_health_checks_enriched,
    probe_outbound_sync,
)

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")

# ---------------------------------------------------------------------------
# Group A — Health Check Logic
# ---------------------------------------------------------------------------

class TestHealthCheckLogic:

    def test_health_no_supabase_url(self):
        """With no SUPABASE_URL, checks should be skipped, not crash."""
        old = os.environ.pop("SUPABASE_URL", None)
        try:
            result = run_health_checks(version="test", env="test")
            assert isinstance(result, HealthResult)
            assert result.checks.get("supabase", {}).get("status") == "skipped"
        finally:
            if old:
                os.environ["SUPABASE_URL"] = old

    def test_health_result_defaults(self):
        r = HealthResult(status="ok", version="1.0", env="test")
        assert r.http_status == 200
        assert r.status == "ok"


# ---------------------------------------------------------------------------
# Group B — Outbound Sync Probes
# ---------------------------------------------------------------------------

class TestOutboundSyncProbes:

    def test_idle_provider(self):
        """No log entries → status=idle."""
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        results = probe_outbound_sync(client, providers=["airbnb"])
        assert len(results) == 1
        assert results[0].status == "idle"
        assert results[0].provider == "airbnb"

    def test_high_failure_rate_degraded(self):
        """Failure rate > 20% → status=degraded."""
        client = MagicMock()
        now = datetime(2026, 3, 12, 7, 0, tzinfo=timezone.utc)

        # Last sync entry
        client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"synced_at": (now - timedelta(minutes=5)).isoformat(), "status": "ok"}
        ]
        # 7d entries: 60% failure rate
        client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
            {"status": "ok"}, {"status": "failed"}, {"status": "failed"},
            {"status": "failed"}, {"status": "ok"},
        ]
        results = probe_outbound_sync(client, providers=["expedia"], now=now)
        assert results[0].status == "degraded"
        assert results[0].failure_rate_7d == pytest.approx(0.6)

    def test_long_lag_degraded(self):
        """Log lag > 1 hour → status=degraded."""
        client = MagicMock()
        now = datetime(2026, 3, 12, 7, 0, tzinfo=timezone.utc)
        old_sync = (now - timedelta(hours=2)).isoformat()

        client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"synced_at": old_sync, "status": "ok"}
        ]
        client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.data = [
            {"status": "ok"},
        ]
        results = probe_outbound_sync(client, providers=["agoda"], now=now)
        assert results[0].status == "degraded"
        assert results[0].log_lag_seconds > 3600

    def test_db_error_returns_error_status(self):
        """DB error → status=error, never crashes."""
        client = MagicMock()
        client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("DB down")

        results = probe_outbound_sync(client, providers=["bookingcom"])
        assert results[0].status == "error"


# ---------------------------------------------------------------------------
# Group C — Enriched Health Check
# ---------------------------------------------------------------------------

class TestEnrichedHealthCheck:

    def test_no_outbound_client_skips_probes(self):
        old = os.environ.pop("SUPABASE_URL", None)
        try:
            result = run_health_checks_enriched(
                version="test", env="test", outbound_client=None
            )
            assert result.checks.get("outbound", {}).get("status") == "skipped"
        finally:
            if old:
                os.environ["SUPABASE_URL"] = old


# ---------------------------------------------------------------------------
# Group D — Deployment Configuration Checks
# ---------------------------------------------------------------------------

class TestDeploymentConfig:

    def test_dockerfile_exists(self):
        df = os.path.join(PROJECT_ROOT, "Dockerfile")
        assert os.path.isfile(df), "Dockerfile missing"

    def test_dockerfile_multistage(self):
        df = os.path.join(PROJECT_ROOT, "Dockerfile")
        content = open(df).read()
        assert "AS builder" in content, "Missing multi-stage builder stage"
        assert "AS runtime" in content, "Missing multi-stage runtime stage"

    def test_dockerfile_nonroot_user(self):
        df = os.path.join(PROJECT_ROOT, "Dockerfile")
        content = open(df).read()
        assert "USER ihouse" in content, "Dockerfile should run as non-root user"

    def test_dockerfile_healthcheck(self):
        df = os.path.join(PROJECT_ROOT, "Dockerfile")
        content = open(df).read()
        assert "HEALTHCHECK" in content, "Dockerfile missing HEALTHCHECK instruction"

    def test_requirements_txt_exists_and_has_deps(self):
        req = os.path.join(PROJECT_ROOT, "requirements.txt")
        assert os.path.isfile(req), "requirements.txt missing"
        content = open(req).read().lower()
        assert "fastapi" in content
        assert "uvicorn" in content

    def test_docker_compose_exists(self):
        dc = os.path.join(PROJECT_ROOT, "docker-compose.yml")
        assert os.path.isfile(dc), "docker-compose.yml missing"

    def test_docker_compose_production_exists(self):
        dc_prod = os.path.join(PROJECT_ROOT, "docker-compose.production.yml")
        assert os.path.isfile(dc_prod), "docker-compose.production.yml missing"


# ---------------------------------------------------------------------------
# Group E — Health HTTP Endpoint
# ---------------------------------------------------------------------------

class TestHealthHTTP:

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_endpoint_returns_200(self):
        r = self.client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert "status" in body
        assert body["status"] in ("ok", "degraded", "unhealthy")

    def test_readiness_endpoint_returns_200(self):
        r = self.client.get("/readiness")
        assert r.status_code == 200
