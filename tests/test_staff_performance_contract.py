"""
Phase 253 — Staff Performance Dashboard API
Contract test suite.

Groups:
    A — GET /admin/staff/performance — happy path
    B — GET /admin/staff/performance — metrics correctness
    C — GET /admin/staff/performance — empty
    D — GET /admin/staff/performance/{worker_id} — happy path
    E — GET /admin/staff/performance/{worker_id} — 404
    F — _compute_worker_metrics unit tests
    G — Route registration
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.staff_performance_router import _compute_worker_metrics
from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_URL = "/admin/staff/performance"
_PATCH_DB = "api.staff_performance_router._get_supabase_client"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kw):
    base = {
        "worker_id": "w1", "state": "done", "kind": "cleaning",
        "priority": "normal", "created_at": "2026-01-10T08:00:00+00:00",
        "acknowledged_at": "2026-01-10T08:03:00+00:00",
        "completed_at": "2026-01-10T09:00:00+00:00",
        "notification_channel": "line",
    }
    return {**base, **kw}


def _make_db(rows):
    class _R:
        def __init__(self, d): self.data = d
    class _Q:
        def __init__(self, c): self._c = c
        def select(self, *a): return self
        def eq(self, *a): return self
        def gte(self, *a): return self
        def lte(self, *a): return self
        def execute(self): return _R(self._c)
    class _DB:
        def __init__(self, c): self._c = c
        def table(self, *a): return _Q(self._c)
    return _DB(rows)


def _get(rows=None, url=None, **params):
    db = _make_db(rows if rows is not None else [_task()])
    qs = "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
    target = url or _URL
    if qs:
        target += "?" + qs
    with patch(_PATCH_DB, return_value=db):
        return client.get(target, headers=_BEARER)


# ---------------------------------------------------------------------------
# Group A — GET all staff — happy path
# ---------------------------------------------------------------------------

class TestGroupAAll:
    def test_a1_returns_200(self):
        assert _get().status_code == 200

    def test_a2_has_staff_list(self):
        b = _get().json()
        assert "staff" in b and isinstance(b["staff"], list)

    def test_a3_total_workers_correct(self):
        rows = [_task(worker_id="w1"), _task(worker_id="w2")]
        b = _get(rows=rows).json()
        assert b["total_workers"] == 2

    def test_a4_total_tasks_correct(self):
        rows = [_task(), _task(), _task()]
        b = _get(rows=rows).json()
        assert b["total_tasks"] == 3

    def test_a5_tenant_id_echoed(self):
        b = _get().json()
        assert b["tenant_id"] == "dev-tenant"


# ---------------------------------------------------------------------------
# Group B — metrics correctness
# ---------------------------------------------------------------------------

class TestGroupBMetrics:
    def test_b1_completion_rate_100_all_done(self):
        rows = [_task(state="done"), _task(state="done")]
        b = _get(rows=rows).json()
        assert b["staff"][0]["completion_rate"] == 100.0

    def test_b2_completion_rate_50(self):
        rows = [_task(state="done"), _task(state="pending")]
        b = _get(rows=rows).json()
        assert b["staff"][0]["completion_rate"] == 50.0

    def test_b3_avg_ack_minutes_computed(self):
        # 3 minutes from created to acknowledged
        b = _get().json()
        assert b["staff"][0]["avg_ack_minutes"] == 3.0

    def test_b4_sla_compliance_critical_met(self):
        rows = [_task(priority="critical")]  # 3 min < 5 min SLA
        b = _get(rows=rows).json()
        assert b["staff"][0]["sla_compliance_pct"] == 100.0

    def test_b5_sla_compliance_critical_breached(self):
        rows = [_task(
            priority="critical",
            created_at="2026-01-10T08:00:00+00:00",
            acknowledged_at="2026-01-10T08:10:00+00:00",  # 10 min > 5 min
        )]
        b = _get(rows=rows).json()
        assert b["staff"][0]["sla_compliance_pct"] == 0.0

    def test_b6_preferred_channel_line(self):
        b = _get().json()
        assert b["staff"][0]["preferred_channel"] == "line"

    def test_b7_kind_breakdown_present(self):
        b = _get().json()
        assert "kind_breakdown" in b["staff"][0]


# ---------------------------------------------------------------------------
# Group C — empty
# ---------------------------------------------------------------------------

class TestGroupCEmpty:
    def test_c1_empty_200(self):
        assert _get(rows=[]).status_code == 200

    def test_c2_empty_staff_list(self):
        b = _get(rows=[]).json()
        assert b["staff"] == []

    def test_c3_empty_total_zero(self):
        b = _get(rows=[]).json()
        assert b["total_workers"] == 0


# ---------------------------------------------------------------------------
# Group D — individual worker happy path
# ---------------------------------------------------------------------------

class TestGroupDIndividual:
    def test_d1_returns_200(self):
        assert _get(url=f"{_URL}/w1").status_code == 200

    def test_d2_worker_id_echoed(self):
        b = _get(url=f"{_URL}/w1").json()
        assert b["worker_id"] == "w1"

    def test_d3_has_metrics(self):
        b = _get(url=f"{_URL}/w1").json()
        for key in ("total_tasks_assigned", "completion_rate", "avg_ack_minutes"):
            assert key in b


# ---------------------------------------------------------------------------
# Group E — individual worker 404
# ---------------------------------------------------------------------------

class TestGroupE404:
    def test_e1_no_tasks_404(self):
        assert _get(rows=[], url=f"{_URL}/unknown").status_code == 404


# ---------------------------------------------------------------------------
# Group F — _compute_worker_metrics unit tests
# ---------------------------------------------------------------------------

class TestGroupFUnit:
    def test_f1_empty_rows(self):
        m = _compute_worker_metrics([])
        assert m["total_tasks_assigned"] == 0
        assert m["completion_rate"] == 0.0

    def test_f2_no_ack_yields_none(self):
        rows = [_task(acknowledged_at=None)]
        m = _compute_worker_metrics(rows)
        assert m["avg_ack_minutes"] is None

    def test_f3_tasks_per_day(self):
        rows = [_task(), _task()]  # same day
        m = _compute_worker_metrics(rows)
        assert m["tasks_per_day"] == 2.0


# ---------------------------------------------------------------------------
# Group G — Route registration
# ---------------------------------------------------------------------------

class TestGroupGRoutes:
    def test_g1_aggregate_route(self):
        routes = [r.path for r in app.routes]
        assert "/admin/staff/performance" in routes

    def test_g2_individual_route(self):
        routes = [r.path for r in app.routes]
        assert "/admin/staff/performance/{worker_id}" in routes
