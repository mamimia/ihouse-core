"""
Phase 167 — Manager Delegated Permissions Contract Tests

Groups:
  A — PATCH /permissions/{user_id}/grant — happy paths
  B — PATCH /permissions/{user_id}/grant — validation errors
  C — PATCH /permissions/{user_id}/grant — 404 when no record
  D — PATCH /permissions/{user_id}/revoke — happy paths
  E — PATCH /permissions/{user_id}/revoke — validation errors
  F — PATCH /permissions/{user_id}/revoke — 404 when no record
  G — get_permission_flags() helper unit tests
  H — has_permission() helper unit tests
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from api.permissions_router import grant_permission, revoke_permission
from api.auth import get_permission_flags, has_permission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _make_db(
    existing_permissions: dict | None = None,
    perm_error: bool = False,
) -> MagicMock:
    """
    Build a mock Supabase client.

    existing_permissions:
        None  → record does not exist (empty data from SELECT)
        dict  → record exists with this permissions JSONB
    """
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.limit.return_value = q
    q.update.return_value = q
    q.delete.return_value = q
    q.insert.return_value = q

    if perm_error:
        q.execute.side_effect = RuntimeError("DB error")
    elif existing_permissions is None:
        q.execute.return_value = MagicMock(data=[])
    else:
        q.execute.return_value = MagicMock(
            data=[{"permissions": existing_permissions}]
        )

    db.table.return_value = q
    db._q = q
    return db


def _grant(db, user_id="u1", capabilities=None):
    return _run(grant_permission(
        user_id=user_id,
        body={"capabilities": capabilities or {"can_view_financials": True}},
        tenant_id="t1",
        client=db,
    ))


def _revoke(db, user_id="u1", capabilities=None):
    return _run(revoke_permission(
        user_id=user_id,
        body={"capabilities": capabilities or ["can_view_financials"]},
        tenant_id="t1",
        client=db,
    ))


def _body(resp):
    return json.loads(resp.body)


# ---------------------------------------------------------------------------
# Group A — PATCH /permissions/{user_id}/grant — happy paths
# ---------------------------------------------------------------------------

def test_a1_grant_single_flag_returns_200():
    db = _make_db(existing_permissions={})
    resp = _grant(db)
    assert resp.status_code == 200


def test_a2_grant_response_status_is_granted():
    db = _make_db(existing_permissions={})
    assert _body(_grant(db))["status"] == "granted"


def test_a3_grant_response_includes_permissions():
    db = _make_db(existing_permissions={})
    data = _body(_grant(db, capabilities={"can_view_financials": True}))
    assert "permissions" in data
    assert data["permissions"].get("can_view_financials") is True


def test_a4_grant_merges_with_existing_flags():
    """Existing flag preserved when new flag granted."""
    db = _make_db(existing_permissions={"can_manage_workers": True})
    data = _body(_grant(db, capabilities={"can_view_financials": True}))
    assert data["permissions"].get("can_manage_workers") is True
    assert data["permissions"].get("can_view_financials") is True


def test_a5_grant_overwrites_existing_flag_value():
    """Granting a flag that already exists overwrites it."""
    db = _make_db(existing_permissions={"can_view_financials": False})
    data = _body(_grant(db, capabilities={"can_view_financials": True}))
    assert data["permissions"]["can_view_financials"] is True


def test_a6_grant_multiple_flags():
    db = _make_db(existing_permissions={})
    resp = _grant(db, capabilities={
        "can_approve_owner_statements": True,
        "can_manage_integrations": True,
        "can_view_financials": True,
    })
    assert resp.status_code == 200
    data = _body(resp)
    assert data["permissions"]["can_approve_owner_statements"] is True
    assert data["permissions"]["can_manage_integrations"] is True


def test_a7_grant_response_includes_granted_dict():
    db = _make_db(existing_permissions={})
    data = _body(_grant(db, capabilities={"can_view_financials": True}))
    assert "granted" in data
    assert data["granted"] == {"can_view_financials": True}


def test_a8_grant_response_includes_updated_at():
    db = _make_db(existing_permissions={})
    data = _body(_grant(db))
    assert "updated_at" in data


def test_a9_grant_non_boolean_flag_value_accepted():
    """Flags can be any JSON value, not just booleans."""
    db = _make_db(existing_permissions={})
    data = _body(_grant(db, capabilities={"worker_role": "CLEANER"}))
    assert data["permissions"]["worker_role"] == "CLEANER"


# ---------------------------------------------------------------------------
# Group B — PATCH /permissions/{user_id}/grant — validation errors
# ---------------------------------------------------------------------------

def test_b1_grant_missing_capabilities_key_returns_400():
    db = _make_db(existing_permissions={})
    resp = _run(grant_permission(
        user_id="u1",
        body={},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_b2_grant_capabilities_is_list_returns_400():
    """capabilities must be a dict, not a list."""
    db = _make_db(existing_permissions={})
    resp = _run(grant_permission(
        user_id="u1",
        body={"capabilities": ["can_view_financials"]},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_b3_grant_empty_capabilities_returns_400():
    db = _make_db(existing_permissions={})
    resp = _run(grant_permission(
        user_id="u1",
        body={"capabilities": {}},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_b4_grant_validation_error_code():
    db = _make_db(existing_permissions={})
    resp = _run(grant_permission(
        user_id="u1",
        body={},
        tenant_id="t1",
        client=db,
    ))
    assert _body(resp)["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Group C — PATCH /permissions/{user_id}/grant — 404 when no record
# ---------------------------------------------------------------------------

def test_c1_grant_no_record_returns_404():
    db = _make_db(existing_permissions=None)
    resp = _grant(db)
    assert resp.status_code == 404


def test_c2_grant_404_error_code():
    db = _make_db(existing_permissions=None)
    assert _body(_grant(db))["code"] == "PERMISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Group D — PATCH /permissions/{user_id}/revoke — happy paths
# ---------------------------------------------------------------------------

def test_d1_revoke_existing_flag_returns_200():
    db = _make_db(existing_permissions={"can_view_financials": True})
    resp = _revoke(db)
    assert resp.status_code == 200


def test_d2_revoke_response_status_is_revoked():
    db = _make_db(existing_permissions={"can_view_financials": True})
    assert _body(_revoke(db))["status"] == "revoked"


def test_d3_revoke_flag_removed_from_permissions():
    db = _make_db(existing_permissions={
        "can_view_financials": True,
        "can_manage_workers": True,
    })
    data = _body(_revoke(db, capabilities=["can_view_financials"]))
    assert "can_view_financials" not in data["permissions"]
    assert data["permissions"].get("can_manage_workers") is True


def test_d4_revoke_response_includes_revoked_list():
    db = _make_db(existing_permissions={"can_view_financials": True})
    data = _body(_revoke(db))
    assert "revoked" in data
    assert "can_view_financials" in data["revoked"]


def test_d5_revoke_missing_key_is_idempotent():
    """Revoking a flag that doesn't exist returns 200 with that key in 'ignored'."""
    db = _make_db(existing_permissions={})
    resp = _revoke(db, capabilities=["can_view_financials"])
    assert resp.status_code == 200
    data = _body(resp)
    assert "can_view_financials" in data["ignored"]


def test_d6_revoke_response_includes_ignored_list():
    db = _make_db(existing_permissions={"can_manage_workers": True})
    data = _body(_revoke(db, capabilities=["can_view_financials"]))
    assert "ignored" in data
    assert "can_view_financials" in data["ignored"]


def test_d7_revoke_multiple_flags():
    db = _make_db(existing_permissions={
        "can_view_financials": True,
        "can_approve_owner_statements": True,
    })
    data = _body(_revoke(db, capabilities=["can_view_financials", "can_approve_owner_statements"]))
    assert "can_view_financials" not in data["permissions"]
    assert "can_approve_owner_statements" not in data["permissions"]


def test_d8_revoke_response_includes_updated_at():
    db = _make_db(existing_permissions={"can_view_financials": True})
    assert "updated_at" in _body(_revoke(db))


# ---------------------------------------------------------------------------
# Group E — PATCH /permissions/{user_id}/revoke — validation errors
# ---------------------------------------------------------------------------

def test_e1_revoke_capabilities_is_dict_returns_400():
    """revoke capabilities must be a list, not a dict."""
    db = _make_db(existing_permissions={})
    resp = _run(revoke_permission(
        user_id="u1",
        body={"capabilities": {"flag": True}},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_e2_revoke_capabilities_missing_returns_400():
    db = _make_db(existing_permissions={})
    resp = _run(revoke_permission(
        user_id="u1",
        body={},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_e3_revoke_empty_list_returns_400():
    db = _make_db(existing_permissions={})
    resp = _run(revoke_permission(
        user_id="u1",
        body={"capabilities": []},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_e4_revoke_non_string_entry_returns_400():
    db = _make_db(existing_permissions={})
    resp = _run(revoke_permission(
        user_id="u1",
        body={"capabilities": ["valid", 123]},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Group F — PATCH /permissions/{user_id}/revoke — 404 when no record
# ---------------------------------------------------------------------------

def test_f1_revoke_no_record_returns_404():
    db = _make_db(existing_permissions=None)
    resp = _revoke(db)
    assert resp.status_code == 404


def test_f2_revoke_404_error_code():
    db = _make_db(existing_permissions=None)
    assert _body(_revoke(db))["code"] == "PERMISSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Group G — get_permission_flags() helper
# ---------------------------------------------------------------------------

def _make_scope_db(permissions: dict) -> MagicMock:
    """Build a mock that returns a full permissions row."""
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.limit.return_value = q
    q.execute.return_value = MagicMock(
        data=[{"role": "manager", "permissions": permissions}]
    )
    db.table.return_value = q
    return db


def test_g1_get_permission_flags_returns_present_flags():
    db = _make_scope_db({"can_view_financials": True, "can_manage_workers": False})
    flags = get_permission_flags(db, "t1", "u1", ["can_view_financials", "can_manage_workers"])
    assert flags["can_view_financials"] is True
    assert flags["can_manage_workers"] is False


def test_g2_get_permission_flags_missing_flag_returns_none():
    db = _make_scope_db({})
    flags = get_permission_flags(db, "t1", "u1", ["can_view_financials"])
    assert flags["can_view_financials"] is None


def test_g3_get_permission_flags_returns_all_requested():
    db = _make_scope_db({"can_approve_owner_statements": True})
    flags = get_permission_flags(db, "t1", "u1", [
        "can_approve_owner_statements",
        "can_manage_integrations",
    ])
    assert set(flags.keys()) == {"can_approve_owner_statements", "can_manage_integrations"}


def test_g4_get_permission_flags_db_error_returns_none_dict():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    flags = get_permission_flags(db, "t1", "u1", ["can_view_financials"])
    assert flags["can_view_financials"] is None


# ---------------------------------------------------------------------------
# Group H — has_permission() helper
# ---------------------------------------------------------------------------

def test_h1_has_permission_true_when_flag_truthy():
    db = _make_scope_db({"can_view_financials": True})
    assert has_permission(db, "t1", "u1", "can_view_financials") is True


def test_h2_has_permission_false_when_flag_false():
    db = _make_scope_db({"can_view_financials": False})
    assert has_permission(db, "t1", "u1", "can_view_financials") is False


def test_h3_has_permission_false_when_flag_missing():
    db = _make_scope_db({})
    assert has_permission(db, "t1", "u1", "can_approve_owner_statements") is False


def test_h4_has_permission_false_on_db_error():
    db = MagicMock()
    db.table.side_effect = RuntimeError("DB down")
    assert has_permission(db, "t1", "u1", "can_view_financials") is False
