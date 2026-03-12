"""
Phase 248 — Maintenance & Housekeeping Task Templates
Contract test suite.

Groups:
    A — GET /admin/task-templates response shape
    B — GET empty tenant
    C — GET filters (kind, trigger_event, active_only)
    D — POST creates template
    E — POST validation errors
    F — DELETE soft-delete
    G — DELETE not found
    H — Route registration
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_BEARER = {"Authorization": "Bearer test-token"}
_BASE = "/admin/task-templates"
_PATCH_DB = "api.task_template_router._get_supabase_client"


@pytest.fixture(autouse=True)
def _dev_mode(monkeypatch):
    """Phase 283: set dev mode per-test so auth doesn't block."""
    monkeypatch.setenv("IHOUSE_DEV_MODE", "true")


# ---------------------------------------------------------------------------
# Fake DB helpers
# ---------------------------------------------------------------------------

def _row(title="Deep Clean", kind="housekeeping", priority="high",
         est=60, trigger="BOOKING_CREATED", active=True):
    return {
        "id": "t-uuid",
        "title": title,
        "kind": kind,
        "priority": priority,
        "estimated_minutes": est,
        "trigger_event": trigger,
        "instructions": "Step 1...",
        "active": active,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


def _make_db(list_rows=None, check_rows=None, *, upsert_result=None):
    """Minimal DB mock supporting: table → select/eq/order/limit/upsert/update/execute."""
    class _R:
        def __init__(self, d): self.data = d

    class _Q:
        def __init__(self, lr, cr, ur):
            self._lr = lr; self._cr = cr; self._ur = ur
            self._is_upsert = False; self._is_update = False; self._is_check = False

        def select(self, *a): return self
        def eq(self, *a, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a): self._is_check = True; return self

        def upsert(self, row, **kw):
            self._is_upsert = True; self._row = row; return self
        def update(self, row):
            self._is_update = True; self._row = row; return self

        def execute(self):
            if self._is_upsert:
                return _R(self._ur or [self._row])
            if self._is_check:
                return _R(self._cr)
            if self._is_update:
                return _R([])
            return _R(self._lr)

    class _DB:
        def __init__(self, lr, cr, ur): self._lr = lr; self._cr = cr; self._ur = ur
        def table(self, *a): return _Q(self._lr, self._cr, self._ur)

    return _DB(list_rows or [], check_rows or [], upsert_result)


# ---------------------------------------------------------------------------
# Group A — GET response shape
# ---------------------------------------------------------------------------

class TestGroupAShape:
    def _body(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            return client.get(_BASE, headers=_BEARER).json()

    def test_a1_returns_200(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            assert client.get(_BASE, headers=_BEARER).status_code == 200

    def test_a2_required_keys(self):
        for k in ("tenant_id", "count", "filters", "templates"):
            assert k in self._body()

    def test_a3_templates_is_list(self):
        assert isinstance(self._body()["templates"], list)

    def test_a4_filters_echoed(self):
        assert "active_only" in self._body()["filters"]


# ---------------------------------------------------------------------------
# Group B — GET empty
# ---------------------------------------------------------------------------

class TestGroupBEmpty:
    def test_b1_count_zero(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            assert client.get(_BASE, headers=_BEARER).json()["count"] == 0

    def test_b2_templates_empty(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            assert client.get(_BASE, headers=_BEARER).json()["templates"] == []


# ---------------------------------------------------------------------------
# Group C — GET with rows
# ---------------------------------------------------------------------------

class TestGroupCRows:
    def test_c1_count_matches_rows(self):
        with patch(_PATCH_DB, return_value=_make_db([_row(), _row(title="Quick Sweep")])):
            b = client.get(_BASE, headers=_BEARER).json()
        assert b["count"] == 2

    def test_c2_filter_kind_echoed(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            b = client.get(f"{_BASE}?kind=maintenance", headers=_BEARER).json()
        assert b["filters"]["kind"] == "maintenance"

    def test_c3_filter_trigger_echoed(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            b = client.get(f"{_BASE}?trigger_event=BOOKING_CREATED", headers=_BEARER).json()
        assert b["filters"]["trigger_event"] == "BOOKING_CREATED"


# ---------------------------------------------------------------------------
# Group D — POST creates template
# ---------------------------------------------------------------------------

class TestGroupDPost:
    def _post(self, body):
        db = _make_db(upsert_result=[{**body, "active": True}])
        with patch(_PATCH_DB, return_value=db):
            return client.post(_BASE, json=body, headers=_BEARER)

    def test_d1_returns_201(self):
        r = self._post({"title": "Deep Clean", "kind": "housekeeping"})
        assert r.status_code == 201

    def test_d2_response_has_template(self):
        r = self._post({"title": "Deep Clean", "kind": "housekeeping"})
        assert "template" in r.json()

    def test_d3_priority_defaults_to_normal(self):
        body = {"title": "Inspection", "kind": "inspection"}
        db = _make_db(upsert_result=[{**body, "priority": "normal", "active": True}])
        with patch(_PATCH_DB, return_value=db):
            r = client.post(_BASE, json=body, headers=_BEARER)
        assert r.json()["template"].get("priority") == "normal"

    def test_d4_custom_priority(self):
        body = {"title": "Critical Fix", "kind": "maintenance", "priority": "critical"}
        db = _make_db(upsert_result=[body])
        with patch(_PATCH_DB, return_value=db):
            r = client.post(_BASE, json=body, headers=_BEARER)
        assert r.status_code == 201

    def test_d5_trigger_event_stored(self):
        body = {"title": "Post-checkout Clean", "kind": "housekeeping",
                "trigger_event": "BOOKING_CANCELED"}
        db = _make_db(upsert_result=[body])
        with patch(_PATCH_DB, return_value=db):
            r = client.post(_BASE, json=body, headers=_BEARER)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# Group E — POST validation errors
# ---------------------------------------------------------------------------

class TestGroupEValidation:
    def _post(self, body):
        with patch(_PATCH_DB, return_value=_make_db()):
            return client.post(_BASE, json=body, headers=_BEARER)

    def test_e1_missing_title(self):
        assert self._post({"kind": "housekeeping"}).status_code == 400

    def test_e2_missing_kind(self):
        assert self._post({"title": "T"}).status_code == 400

    def test_e3_invalid_priority(self):
        assert self._post({"title": "T", "kind": "maintenance", "priority": "urgent"}).status_code == 400

    def test_e4_estimated_minutes_zero(self):
        assert self._post({"title": "T", "kind": "k", "estimated_minutes": 0}).status_code == 400

    def test_e5_estimated_minutes_negative(self):
        assert self._post({"title": "T", "kind": "k", "estimated_minutes": -5}).status_code == 400


# ---------------------------------------------------------------------------
# Group F — DELETE soft-delete
# ---------------------------------------------------------------------------

class TestGroupFDelete:
    def _delete(self, template_id="t-uuid", check_rows=None):
        cr = check_rows if check_rows is not None else [{"id": template_id, "active": True}]
        db = _make_db(check_rows=cr)
        with patch(_PATCH_DB, return_value=db):
            return client.delete(f"{_BASE}/{template_id}", headers=_BEARER)

    def test_f1_returns_200(self):
        assert self._delete().status_code == 200

    def test_f2_active_false_in_response(self):
        assert self._delete().json()["active"] is False

    def test_f3_template_id_echoed(self):
        assert self._delete("t-uuid").json()["template_id"] == "t-uuid"


# ---------------------------------------------------------------------------
# Group G — DELETE not found
# ---------------------------------------------------------------------------

class TestGroupGNotFound:
    def test_g1_returns_404(self):
        db = _make_db(check_rows=[])
        with patch(_PATCH_DB, return_value=db):
            r = client.delete(f"{_BASE}/nonexistent", headers=_BEARER)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Group H — Route registration
# ---------------------------------------------------------------------------

class TestGroupHRoutes:
    def test_h1_get_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/admin/task-templates" in routes

    def test_h2_delete_route_registered(self):
        routes = [r.path for r in app.routes]
        assert "/admin/task-templates/{template_id}" in routes

    def test_h3_get_returns_200_with_bearer(self):
        with patch(_PATCH_DB, return_value=_make_db()):
            assert client.get(_BASE, headers=_BEARER).status_code == 200
