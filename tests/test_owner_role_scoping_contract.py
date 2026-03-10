"""
Phase 166 — Owner Role Scoping Contract Tests

Tests cover:
  - owner_statement_router.get_owner_statement() — property allow-list enforcement
  - financial_aggregation_router._get_owner_property_filter() — pure logic
  - financial_aggregation_router._fetch_period_rows() — property_ids DB filter

Groups:
  A — Owner accessing allowed property (200 / 404)
  B — Owner accessing forbidden property (403)
  C — Admin and Manager are unrestricted
  D — No permission record → unrestricted
  E — _get_owner_property_filter unit tests (pure logic)
  F — _fetch_period_rows with property_ids filter
  G — Best-effort: permission error never blocks
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from api.owner_statement_router import get_owner_statement
from api.financial_aggregation_router import (
    _get_owner_property_filter,
    _fetch_period_rows,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _make_owner_db(
    fin_rows: list = None,
    perm: dict | None = None,
    perm_error: bool = False,
) -> MagicMock:
    db = MagicMock()

    fin_q = MagicMock()
    fin_q.select.return_value = fin_q
    fin_q.eq.return_value = fin_q
    fin_q.gte.return_value = fin_q
    fin_q.lt.return_value = fin_q
    fin_q.order.return_value = fin_q
    fin_q.execute.return_value = MagicMock(data=fin_rows or [])

    perm_q = MagicMock()
    perm_q.select.return_value = perm_q
    perm_q.eq.return_value = perm_q
    perm_q.limit.return_value = perm_q
    if perm_error:
        perm_q.execute.side_effect = RuntimeError("perm DB error")
    else:
        perm_q.execute.return_value = MagicMock(data=[perm] if perm else [])

    def _table(name):
        if name == "booking_financial_facts":
            return fin_q
        if name == "tenant_permissions":
            return perm_q
        return MagicMock()

    db.table.side_effect = _table
    return db


def _make_agg_db(
    fin_rows: list = None,
    perm: dict | None = None,
    perm_error: bool = False,
) -> MagicMock:
    db = MagicMock()

    fin_q = MagicMock()
    fin_q.select.return_value = fin_q
    fin_q.eq.return_value = fin_q
    fin_q.in_.return_value = fin_q
    fin_q.gte.return_value = fin_q
    fin_q.lt.return_value = fin_q
    fin_q.order.return_value = fin_q
    fin_q.execute.return_value = MagicMock(data=fin_rows or [])

    perm_q = MagicMock()
    perm_q.select.return_value = perm_q
    perm_q.eq.return_value = perm_q
    perm_q.limit.return_value = perm_q
    if perm_error:
        perm_q.execute.side_effect = RuntimeError("perm DB error")
    else:
        perm_q.execute.return_value = MagicMock(data=[perm] if perm else [])

    def _table(name):
        if name == "booking_financial_facts":
            return fin_q
        if name == "tenant_permissions":
            return perm_q
        return MagicMock()

    db.table.side_effect = _table
    db._fin_q = fin_q
    return db


def _get_stmt(db, property_id="prop-1", user_id=None, month="2026-03"):
    return _run(get_owner_statement(
        property_id=property_id,
        month=month,
        management_fee_pct=None,
        format=None,
        tenant_id="t1",
        client=db,
        user_id=user_id,
    ))


def _body(resp):
    return json.loads(resp.body)


# ---------------------------------------------------------------------------
# Group A — Owner accessing allowed property (200 or 404 — never 403)
# ---------------------------------------------------------------------------

def test_a1_owner_accessing_allowed_property_not_403():
    perm = {"role": "owner", "permissions": {"property_ids": ["prop-1", "prop-2"]}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-1", user_id="owner-1")
    assert resp.status_code != 403


def test_a2_owner_can_access_each_of_their_properties():
    perm = {"role": "owner", "permissions": {"property_ids": ["propA", "propB", "propC"]}}
    for prop_id in ["propA", "propB", "propC"]:
        db = _make_owner_db(perm=perm)
        resp = _get_stmt(db, property_id=prop_id, user_id="owner-1")
        assert resp.status_code != 403, f"Got 403 for allowed property {prop_id}"


# ---------------------------------------------------------------------------
# Group B — Owner accessing forbidden property (403)
# ---------------------------------------------------------------------------

def test_b1_owner_forbidden_property_returns_403():
    perm = {"role": "owner", "permissions": {"property_ids": ["prop-1"]}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-FORBIDDEN", user_id="owner-1")
    assert resp.status_code == 403


def test_b2_owner_forbidden_error_code_is_forbidden():
    perm = {"role": "owner", "permissions": {"property_ids": ["prop-allowed"]}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-other", user_id="owner-1")
    assert _body(resp).get("code") == "FORBIDDEN"


def test_b3_owner_empty_property_ids_blocks_all():
    perm = {"role": "owner", "permissions": {"property_ids": []}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-1", user_id="owner-1")
    assert resp.status_code == 403


def test_b4_owner_missing_property_ids_key_blocks_all():
    """Owner with permissions={} has empty list → any property returns 403."""
    perm = {"role": "owner", "permissions": {}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-X", user_id="owner-1")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Group C — Admin and Manager are unrestricted (not 403)
# ---------------------------------------------------------------------------

def test_c1_admin_not_restricted_to_property_ids():
    perm = {"role": "admin", "permissions": {"property_ids": ["prop-A"]}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-ANY", user_id="admin-1")
    assert resp.status_code != 403


def test_c2_manager_not_restricted():
    perm = {"role": "manager", "permissions": {"property_ids": ["prop-X"]}}
    db = _make_owner_db(perm=perm)
    resp = _get_stmt(db, property_id="prop-Y", user_id="mgr-1")
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Group D — No permission record → unrestricted
# ---------------------------------------------------------------------------

def test_d1_no_perm_record_access_any_property():
    db = _make_owner_db(perm=None)
    resp = _get_stmt(db, property_id="any-prop", user_id="unknown-user")
    assert resp.status_code != 403


def test_d2_no_user_id_no_restriction():
    db = _make_owner_db(perm=None)
    resp = _get_stmt(db, property_id="prop-1", user_id=None)
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# Group E — _get_owner_property_filter pure logic
# ---------------------------------------------------------------------------

def test_e1_owner_role_returns_property_ids():
    perm = {"role": "owner", "permissions": {"property_ids": ["p1", "p2"]}}
    db = _make_agg_db(perm=perm)
    result = _get_owner_property_filter(db, "t1", "owner-1")
    assert result == ["p1", "p2"]


def test_e2_admin_role_returns_none():
    perm = {"role": "admin", "permissions": {"property_ids": ["p1"]}}
    db = _make_agg_db(perm=perm)
    assert _get_owner_property_filter(db, "t1", "admin-1") is None


def test_e3_manager_role_returns_none():
    perm = {"role": "manager", "permissions": {"property_ids": ["p1"]}}
    db = _make_agg_db(perm=perm)
    assert _get_owner_property_filter(db, "t1", "mgr-1") is None


def test_e4_no_perm_record_returns_none():
    db = _make_agg_db(perm=None)
    assert _get_owner_property_filter(db, "t1", "u1") is None


def test_e5_no_user_id_returns_none():
    db = _make_agg_db()
    assert _get_owner_property_filter(db, "t1", None) is None


def test_e6_owner_no_property_ids_key_returns_empty_list():
    perm = {"role": "owner", "permissions": {}}
    db = _make_agg_db(perm=perm)
    result = _get_owner_property_filter(db, "t1", "owner-1")
    assert result == []


# ---------------------------------------------------------------------------
# Group F — _fetch_period_rows with property_ids filter
# ---------------------------------------------------------------------------

def test_f1_fetch_no_property_filter_no_in_call():
    db = _make_agg_db(fin_rows=[])
    _fetch_period_rows(db, "t1", "2026-03", property_ids=None)
    assert not db._fin_q.in_.called


def test_f2_fetch_with_property_ids_calls_in_():
    db = _make_agg_db(fin_rows=[])
    _fetch_period_rows(db, "t1", "2026-03", property_ids=["p1"])
    db._fin_q.in_.assert_called_once_with("property_id", ["p1"])


def test_f3_fetch_empty_property_ids_no_in_call():
    db = _make_agg_db(fin_rows=[])
    _fetch_period_rows(db, "t1", "2026-03", property_ids=[])
    assert not db._fin_q.in_.called


def test_f4_fetch_multiple_property_ids():
    db = _make_agg_db(fin_rows=[])
    _fetch_period_rows(db, "t1", "2026-03", property_ids=["p1", "p2", "p3"])
    db._fin_q.in_.assert_called_once_with("property_id", ["p1", "p2", "p3"])


# ---------------------------------------------------------------------------
# Group G — Best-effort: permission error never blocks the request
# ---------------------------------------------------------------------------

def test_g1_perm_error_owner_statement_not_blocked():
    db = _make_owner_db(perm_error=True)
    resp = _get_stmt(db, property_id="any-prop", user_id="owner-1")
    assert resp.status_code != 403


def test_g2_perm_error_get_owner_filter_returns_none():
    db = _make_agg_db(perm_error=True)
    assert _get_owner_property_filter(db, "t1", "owner-1") is None
