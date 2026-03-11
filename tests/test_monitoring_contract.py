"""
Phase 263 — Production Monitoring Contract Tests
=================================================

Tests: 20 across 5 groups.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from main import app
import services.monitoring as mon

client = TestClient(app, raise_server_exceptions=False)
_AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def reset():
    mon.reset_metrics()
    yield
    mon.reset_metrics()


# ---------------------------------------------------------------------------
# Group A — Service: record_request + route prefix
# ---------------------------------------------------------------------------

class TestGroupARecordRequest:

    def test_a1_request_increments_count(self):
        mon.record_request("/admin/webhook-log", 200, 0.05)
        assert mon.get_request_counts().get("/admin", 0) >= 1

    def test_a2_4xx_status_increments_error(self):
        mon.record_request("/guest/booking/x", 404, 0.01)
        counts = mon.get_error_counts()
        assert counts.get("/guest", {}).get("4xx", 0) == 1

    def test_a3_5xx_status_increments_error(self):
        mon.record_request("/admin/bulk", 500, 0.1)
        counts = mon.get_error_counts()
        assert counts.get("/admin", {}).get("5xx", 0) == 1

    def test_a4_2xx_does_not_increment_errors(self):
        mon.record_request("/admin/metrics", 200, 0.02)
        counts = mon.get_error_counts()
        assert counts.get("/admin", {}).get("4xx", 0) == 0
        assert counts.get("/admin", {}).get("5xx", 0) == 0


# ---------------------------------------------------------------------------
# Group B — Service: latency stats
# ---------------------------------------------------------------------------

class TestGroupBLatencyStats:

    def test_b1_latency_stats_empty_returns_none_fields(self):
        stats = mon.get_latency_stats("/admin/metrics")
        assert stats.get("/admin", {}).get("count", 0) == 0

    def test_b2_latency_stats_after_recording(self):
        for t in [0.01, 0.02, 0.03, 0.10]:
            mon.record_request("/admin/test", 200, t)
        stats = mon.get_latency_stats("/admin/test")
        prefix = list(stats.keys())[0]
        assert stats[prefix]["count"] == 4
        assert stats[prefix]["min_ms"] < stats[prefix]["max_ms"]
        assert stats[prefix]["p95_ms"] is not None

    def test_b3_avg_is_sensible(self):
        mon.record_request("/admin/x", 200, 0.10)
        mon.record_request("/admin/x", 200, 0.20)
        stats = mon.get_latency_stats("/admin/x")
        avg = stats.get("/admin", {}).get("avg_ms")
        assert avg is not None
        assert 100 <= avg <= 200

    def test_b4_uptime_positive(self):
        assert mon.get_uptime_seconds() > 0


# ---------------------------------------------------------------------------
# Group C — HTTP: GET /admin/metrics
# ---------------------------------------------------------------------------

class TestGroupCHttpMetrics:

    def test_c1_metrics_returns_200(self):
        resp = client.get("/admin/monitor", headers=_AUTH)
        assert resp.status_code == 200

    def test_c2_metrics_has_expected_keys(self):
        resp = client.get("/admin/monitor", headers=_AUTH)
        body = resp.json()
        assert "uptime_seconds" in body
        assert "request_counts" in body
        assert "error_counts" in body
        assert "latency" in body

    def test_c3_uptime_is_positive(self):
        resp = client.get("/admin/monitor", headers=_AUTH)
        assert resp.json()["uptime_seconds"] > 0


# ---------------------------------------------------------------------------
# Group D — HTTP: GET /admin/metrics/health
# ---------------------------------------------------------------------------

class TestGroupDHttpHealth:

    def test_d1_health_returns_200_when_no_errors(self):
        resp = client.get("/admin/monitor/health", headers=_AUTH)
        assert resp.status_code == 200

    def test_d2_health_body_has_status(self):
        resp = client.get("/admin/monitor/health", headers=_AUTH)
        assert resp.json()["status"] in ("ok", "degraded")

    def test_d3_health_body_has_uptime(self):
        resp = client.get("/admin/monitor/health", headers=_AUTH)
        assert resp.json()["uptime_seconds"] > 0

    def test_d4_degraded_when_high_5xx_rate(self):
        # Force >10% 5xx rate
        for _ in range(5):
            mon.record_request("/admin/x", 500, 0.01)
        mon.record_request("/admin/x", 200, 0.01)  # 1 ok, 5 bad → ~83% 5xx
        resp = client.get("/admin/monitor/health", headers=_AUTH)
        body = resp.json()
        assert body["degraded"] is True
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Group E — HTTP: GET /admin/metrics/latency
# ---------------------------------------------------------------------------

class TestGroupEHttpLatency:

    def test_e1_latency_returns_200(self):
        resp = client.get("/admin/monitor/latency", headers=_AUTH)
        assert resp.status_code == 200

    def test_e2_latency_has_prefix_key(self):
        resp = client.get("/admin/monitor/latency", headers=_AUTH)
        assert "latency_by_prefix" in resp.json()

    def test_e3_latency_reflects_recorded_samples(self):
        mon.record_request("/admin/someop", 200, 0.05)
        resp = client.get("/admin/monitor/latency", headers=_AUTH)
        data = resp.json()["latency_by_prefix"]
        assert "/admin" in data
        assert data["/admin"]["count"] >= 1
