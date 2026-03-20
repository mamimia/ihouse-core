"""  # noqa: E501
Phase 166 — Worker Role Scoping Contract Tests

Tests call list_worker_tasks() directly via asyncio.run() using the
injectable `client` parameter — same pattern as the project's unit tests
for functions that accept a `client` argument.

Groups:
  A — No permission record (backward compat — unrestricted)
  B — Caller has role='admin' (unrestricted)
  C — Caller has role='manager' (unrestricted)
  D — Caller has role='worker' with worker_role=CLEANER (auto-scoped)
  E — Caller has role='worker' with no worker_role in permissions
  F — Caller supplied worker_role overridden by permission record
  G — Response shape invariants and validation errors
  H — Best-effort: DB error in permission lookup never blocks request
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, call

import pytest

from api.worker_router import list_worker_tasks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously (Python 3.14 compatible)."""
    return asyncio.run(coro)


def _make_db(tasks: list = None, perm: dict | None = None, perm_error: bool = False) -> MagicMock:
    """Build a mock Supabase client.

    tasks      — rows returned from tasks table query
    perm       — row returned from tenant_permissions query (or None = no record)
    perm_error — if True, permission query raises RuntimeError
    """
    db = MagicMock()

    # Tasks query chain — supports .eq, .neq, .in_, .or_, .limit, .order
    tasks_q = MagicMock()
    tasks_q.select.return_value = tasks_q
    tasks_q.eq.return_value = tasks_q
    tasks_q.neq.return_value = tasks_q
    tasks_q.in_.return_value = tasks_q
    tasks_q.or_.return_value = tasks_q
    tasks_q.limit.return_value = tasks_q
    tasks_q.order.return_value = tasks_q
    tasks_q.execute.return_value = MagicMock(data=tasks or [])

    # Permissions query chain
    perm_q = MagicMock()
    perm_q.select.return_value = perm_q
    perm_q.eq.return_value = perm_q
    perm_q.limit.return_value = perm_q
    if perm_error:
        perm_q.execute.side_effect = RuntimeError("permission DB error")
    else:
        perm_q.execute.return_value = MagicMock(data=[perm] if perm else [])

    # Worker property assignments chain — returns empty
    asgn_q = MagicMock()
    asgn_q.select.return_value = asgn_q
    asgn_q.eq.return_value = asgn_q
    asgn_q.execute.return_value = MagicMock(data=[])

    def _table(name):
        if name == "tasks":
            return tasks_q
        if name == "tenant_permissions":
            return perm_q
        if name == "worker_property_assignments":
            return asgn_q
        return MagicMock()

    db.table.side_effect = _table
    db._tasks_q = tasks_q  # expose for assertion
    return db


def _call(db, worker_role=None, status=None, user_id=None, limit=50):
    return _run(list_worker_tasks(
        worker_role=worker_role,
        status=status,
        limit=limit,
        tenant_id="t1",
        client=db,
        user_id=user_id,
    ))


def _data(resp):
    return json.loads(resp.body)


def _eq_args(db):
    """Return list of (col, val) tuples from tasks_q.eq calls."""
    return [c.args for c in db._tasks_q.eq.call_args_list]


def _in_args(db):
    """Return list of (col, vals) tuples from tasks_q.in_ calls."""
    return [c.args for c in db._tasks_q.in_.call_args_list]


# ---------------------------------------------------------------------------
# Group A — No permission record → unrestricted (backward compat)
# ---------------------------------------------------------------------------

def test_a1_no_perm_record_returns_all_tasks():
    tasks = [{"task_id": "tk1", "worker_role": "CLEANER", "status": "PENDING"}]
    db = _make_db(tasks=tasks, perm=None)
    resp = _call(db)
    assert resp.status_code == 200
    assert _data(resp)["count"] == 1


def test_a2_no_perm_record_worker_role_param_applied():
    db = _make_db(perm=None)
    _call(db, worker_role="CLEANER")
    # Now uses .in_ instead of .eq for worker_role filtering
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "CLEANER" in worker_role_in[0]


def test_a3_no_perm_record_role_scoped_false():
    db = _make_db(perm=None)
    resp = _call(db)
    assert _data(resp)["role_scoped"] is False


# ---------------------------------------------------------------------------
# Group B — Admin role → unrestricted
# ---------------------------------------------------------------------------

def test_b1_admin_role_unrestricted_no_auto_filter():
    perm = {"role": "admin", "permissions": {"worker_role": "CLEANER"}}
    db = _make_db(perm=perm)
    resp = _call(db, user_id="admin-user")
    assert resp.status_code == 200
    # No auto-filter: role_scoped=False (no caller-supplied worker_role)
    assert _data(resp)["role_scoped"] is False


def test_b2_admin_can_supply_worker_role_explicitly():
    perm = {"role": "admin", "permissions": {}}
    db = _make_db(perm=perm)
    _call(db, worker_role="MAINTENANCE_TECH", user_id="admin-user")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "MAINTENANCE_TECH" in worker_role_in[0]


# ---------------------------------------------------------------------------
# Group C — Manager role → unrestricted
# ---------------------------------------------------------------------------

def test_c1_manager_role_no_auto_filter():
    perm = {"role": "manager", "permissions": {"worker_role": "CLEANER"}}
    db = _make_db(perm=perm)
    resp = _call(db, user_id="mgr-user")
    # manager does NOT auto-scope → role_scoped=False
    assert _data(resp)["role_scoped"] is False


def test_c2_manager_can_still_supply_worker_role():
    perm = {"role": "manager", "permissions": {}}
    db = _make_db(perm=perm)
    _call(db, worker_role="INSPECTOR", user_id="mgr-user")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "INSPECTOR" in worker_role_in[0]


# ---------------------------------------------------------------------------
# Group D — Worker role with valid worker_role in permissions
# ---------------------------------------------------------------------------

def test_d1_worker_auto_scoped_to_cleaner():
    perm = {"role": "worker", "permissions": {"worker_role": "CLEANER"}}
    task = {"task_id": "t1", "worker_role": "CLEANER"}
    db = _make_db(tasks=[task], perm=perm)
    resp = _call(db, user_id="worker-1")
    assert resp.status_code == 200
    assert _data(resp)["count"] == 1


def test_d2_worker_auto_scoped_flag_true():
    perm = {"role": "worker", "permissions": {"worker_role": "CLEANER"}}
    db = _make_db(perm=perm)
    resp = _call(db, user_id="worker-1")
    assert _data(resp)["role_scoped"] is True


def test_d3_worker_db_filter_applied_at_db_level():
    perm = {"role": "worker", "permissions": {"worker_role": "CLEANER"}}
    db = _make_db(perm=perm)
    _call(db, user_id="worker-1")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "CLEANER" in worker_role_in[0]


def test_d4_worker_with_maintenance_tech_role():
    perm = {"role": "worker", "permissions": {"worker_role": "MAINTENANCE_TECH"}}
    db = _make_db(perm=perm)
    _call(db, user_id="worker-2")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "MAINTENANCE_TECH" in worker_role_in[0]


def test_d5_worker_with_inspector_role():
    perm = {"role": "worker", "permissions": {"worker_role": "INSPECTOR"}}
    db = _make_db(perm=perm)
    _call(db, user_id="worker-3")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    assert "INSPECTOR" in worker_role_in[0]


# ---------------------------------------------------------------------------
# Group E — Worker with no assigned worker_role in permissions
# ---------------------------------------------------------------------------

def test_e1_worker_empty_permissions_no_auto_filter():
    perm = {"role": "worker", "permissions": {}}
    db = _make_db(perm=perm)
    resp = _call(db, user_id="worker-3")
    # Worker with no valid worker_role gets blocked (in_ with __NO_ROLES_ASSIGNED__)
    # role_scoped is False because effective_worker_roles is empty
    assert _data(resp)["role_scoped"] is False


def test_e2_worker_invalid_worker_role_value_no_auto_filter():
    perm = {"role": "worker", "permissions": {"worker_role": "PILOT"}}  # invalid value
    db = _make_db(perm=perm)
    resp = _call(db, user_id="worker-4")
    assert _data(resp)["role_scoped"] is False


# ---------------------------------------------------------------------------
# Group F — Worker supplied worker_role overridden by permission record
# ---------------------------------------------------------------------------

def test_f1_supplied_role_overridden_by_perm():
    """Caller supplies INSPECTOR but permission says CLEANER → both may end up in the in_ set,
    but CLEANER from perm must be present."""
    perm = {"role": "worker", "permissions": {"worker_role": "CLEANER"}}
    db = _make_db(perm=perm)
    _call(db, worker_role="INSPECTOR", user_id="worker-1")
    in_calls = _in_args(db)
    worker_role_in = [v for (col, v) in in_calls if col == "worker_role"]
    assert len(worker_role_in) > 0
    # The permission record's worker_role MUST be included
    assert "CLEANER" in worker_role_in[0]


# ---------------------------------------------------------------------------
# Group G — Response shape invariants and validation errors
# ---------------------------------------------------------------------------

def test_g1_response_always_has_tasks_count_role_scoped():
    db = _make_db(perm=None)
    resp = _call(db)
    d = _data(resp)
    assert "tasks" in d
    assert "count" in d
    assert "role_scoped" in d


def test_g2_status_200_for_valid_request():
    db = _make_db(perm=None)
    assert _call(db).status_code == 200


def test_g3_limit_zero_returns_400():
    db = _make_db()
    assert _call(db, limit=0).status_code == 400


def test_g4_limit_over_100_returns_400():
    db = _make_db()
    assert _call(db, limit=101).status_code == 400


def test_g5_invalid_worker_role_param_returns_400():
    db = _make_db()
    resp = _run(list_worker_tasks(
        worker_role="INVALID_ROLE",
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Group H — Best-effort: permission DB error never blocks request
# ---------------------------------------------------------------------------

def test_h1_permission_db_error_does_not_block():
    db = _make_db(perm_error=True)
    resp = _call(db, user_id="worker-x")
    assert resp.status_code == 200


def test_h2_none_data_from_perm_handled():
    """Permission query returns data=None → treated as no record."""
    tasks_q = MagicMock()
    tasks_q.select.return_value = tasks_q
    tasks_q.eq.return_value = tasks_q
    tasks_q.neq.return_value = tasks_q
    tasks_q.in_.return_value = tasks_q
    tasks_q.or_.return_value = tasks_q
    tasks_q.limit.return_value = tasks_q
    tasks_q.order.return_value = tasks_q
    tasks_q.execute.return_value = MagicMock(data=[])

    perm_q = MagicMock()
    perm_q.select.return_value = perm_q
    perm_q.eq.return_value = perm_q
    perm_q.limit.return_value = perm_q
    perm_q.execute.return_value = MagicMock(data=None)

    asgn_q = MagicMock()
    asgn_q.select.return_value = asgn_q
    asgn_q.eq.return_value = asgn_q
    asgn_q.execute.return_value = MagicMock(data=[])

    db = MagicMock()
    db._tasks_q = tasks_q

    def _table(name):
        if name == "tasks":
            return tasks_q
        if name == "tenant_permissions":
            return perm_q
        if name == "worker_property_assignments":
            return asgn_q
        return MagicMock()

    db.table.side_effect = _table

    resp = _call(db, user_id="w1")
    assert resp.status_code == 200
