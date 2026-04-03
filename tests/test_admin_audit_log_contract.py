"""
Phase 171 — Admin Audit Log Contract Tests

Groups:
  A — write_audit_event: happy paths
  B — write_audit_event: optional fields (before/after state, metadata)
  C — write_audit_event: DB error returns False (best-effort)
  D — GET /admin/audit-log: happy paths (no filters)
  E — GET /admin/audit-log: filter by action
  F — GET /admin/audit-log: filter by actor_user_id
  G — GET /admin/audit-log: filter by target_type + target_id
  H — GET /admin/audit-log: limit validation
  I — GET /admin/audit-log: DB error returns 500
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, call

from api.admin_router import write_audit_event, get_audit_log

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _body(resp):
    return json.loads(resp.body)


_AUDIT_ROW = {
    "id": 1,
    "actor_user_id": "actor-1",
    "action": "grant_permission",
    "target_type": "permission",
    "target_id": "user-42",
    "before_state": None,
    "after_state": {"can_view_financials": True},
    "metadata": {},
    "occurred_at": "2026-03-10T09:00:00Z",
}


def _make_db(rows: list | None = None, insert_error: bool = False, query_error: bool = False) -> MagicMock:
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.insert.return_value = q
    q.eq.return_value = q
    q.order.return_value = q
    q.limit.return_value = q

    if insert_error or query_error:
        q.execute.side_effect = RuntimeError("DB error")
    else:
        q.execute.return_value = MagicMock(data=rows or [])

    db.table.return_value = q
    db._q = q
    return db


def _audit_get(db, **kwargs):
    return _run(get_audit_log(
        action=kwargs.get("action"),
        actor_user_id=kwargs.get("actor_user_id"),
        target_type=kwargs.get("target_type"),
        target_id=kwargs.get("target_id"),
        limit=kwargs.get("limit", 100),
        identity={"tenant_id": "t1", "role": "admin"},
        client=db,
    ))


# ---------------------------------------------------------------------------
# Group A — write_audit_event: happy paths
# ---------------------------------------------------------------------------

def test_a1_write_audit_event_returns_true():
    db = _make_db()
    result = write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="admin-1",
        action="grant_permission",
        target_type="permission",
        target_id="user-42",
    )
    assert result is True


def test_a2_write_audit_event_calls_insert():
    db = _make_db()
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="admin-1",
        action="patch_provider",
        target_type="provider",
        target_id="airbnb",
    )
    db.table.assert_called_with("admin_audit_log")
    db._q.insert.assert_called_once()


def test_a3_write_audit_event_row_has_required_fields():
    db = _make_db()
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="admin-1",
        action="revoke_permission",
        target_type="permission",
        target_id="user-7",
    )
    inserted_row = db._q.insert.call_args[0][0]
    assert inserted_row["tenant_id"] == "t1"
    assert inserted_row["actor_user_id"] == "admin-1"
    assert inserted_row["action"] == "revoke_permission"
    assert inserted_row["target_type"] == "permission"
    assert inserted_row["target_id"] == "user-7"


def test_a4_write_audit_event_target_id_coerced_to_str():
    db = _make_db()
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="replay_dlq",
        target_type="dlq_entry",
        target_id=999,   # int
    )
    inserted_row = db._q.insert.call_args[0][0]
    assert inserted_row["target_id"] == "999"


# ---------------------------------------------------------------------------
# Group B — write_audit_event: optional fields
# ---------------------------------------------------------------------------

def test_b1_before_state_present_in_row():
    db = _make_db()
    before = {"can_view_financials": False}
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="grant_permission",
        target_type="permission",
        target_id="u1",
        before_state=before,
    )
    row = db._q.insert.call_args[0][0]
    assert row["before_state"] == before


def test_b2_after_state_present_in_row():
    db = _make_db()
    after = {"can_view_financials": True}
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="grant_permission",
        target_type="permission",
        target_id="u1",
        after_state=after,
    )
    row = db._q.insert.call_args[0][0]
    assert row["after_state"] == after


def test_b3_metadata_is_forwarded():
    db = _make_db()
    meta = {"source_ip": "1.2.3.4", "user_agent": "curl"}
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="patch_provider",
        target_type="provider",
        target_id="airbnb",
        metadata=meta,
    )
    row = db._q.insert.call_args[0][0]
    assert row["metadata"] == meta


def test_b4_no_before_state_key_absent():
    """before_state should not appear in row at all when not supplied."""
    db = _make_db()
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="patch_provider",
        target_type="provider",
        target_id="airbnb",
    )
    row = db._q.insert.call_args[0][0]
    assert "before_state" not in row


def test_b5_default_metadata_is_empty_dict():
    db = _make_db()
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="replay_dlq",
        target_type="dlq_entry",
        target_id="e-1",
    )
    row = db._q.insert.call_args[0][0]
    assert row["metadata"] == {}


# ---------------------------------------------------------------------------
# Group C — write_audit_event: DB error → False (best-effort)
# ---------------------------------------------------------------------------

def test_c1_db_error_returns_false():
    db = _make_db(insert_error=True)
    result = write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="grant_permission",
        target_type="permission",
        target_id="u1",
    )
    assert result is False


def test_c2_db_error_does_not_raise():
    db = _make_db(insert_error=True)
    # Must not raise any exception
    write_audit_event(
        db,
        tenant_id="t1",
        actor_user_id="a",
        action="patch_provider",
        target_type="provider",
        target_id="airbnb",
    )


# ---------------------------------------------------------------------------
# Group D — GET /admin/audit-log: happy paths
# ---------------------------------------------------------------------------

def test_d1_returns_200():
    db = _make_db(rows=[_AUDIT_ROW])
    assert _audit_get(db).status_code == 200


def test_d2_response_includes_entries():
    db = _make_db(rows=[_AUDIT_ROW])
    data = _body(_audit_get(db))
    assert "entries" in data


def test_d3_count_matches_rows():
    db = _make_db(rows=[_AUDIT_ROW, _AUDIT_ROW])
    data = _body(_audit_get(db))
    assert data["count"] == 2


def test_d4_empty_audit_log_returns_empty_entries():
    db = _make_db(rows=[])
    data = _body(_audit_get(db))
    assert data["entries"] == []
    assert data["count"] == 0


def test_d5_entry_shape_contains_required_keys():
    db = _make_db(rows=[_AUDIT_ROW])
    entry = _body(_audit_get(db))["entries"][0]
    for key in ("id", "actor_user_id", "action", "target_type", "target_id", "occurred_at"):
        assert key in entry, f"Missing key: {key}"


def test_d6_response_includes_filters_dict():
    db = _make_db(rows=[])
    data = _body(_audit_get(db))
    assert "filters" in data


# ---------------------------------------------------------------------------
# Group E — filter by action
# ---------------------------------------------------------------------------

def test_e1_action_filter_calls_eq():
    db = _make_db(rows=[])
    _audit_get(db, action="grant_permission")
    eq_calls = [c.args for c in db._q.eq.call_args_list]
    assert ("action", "grant_permission") in eq_calls


def test_e2_action_filter_in_response_filters():
    db = _make_db(rows=[])
    data = _body(_audit_get(db, action="grant_permission"))
    assert data["filters"]["action"] == "grant_permission"


# ---------------------------------------------------------------------------
# Group F — filter by actor_user_id
# ---------------------------------------------------------------------------

def test_f1_actor_filter_calls_eq():
    db = _make_db(rows=[])
    _audit_get(db, actor_user_id="admin-1")
    eq_calls = [c.args for c in db._q.eq.call_args_list]
    assert ("actor_user_id", "admin-1") in eq_calls


# ---------------------------------------------------------------------------
# Group G — filter by target_type + target_id
# ---------------------------------------------------------------------------

def test_g1_target_type_filter_calls_eq():
    db = _make_db(rows=[])
    _audit_get(db, target_type="provider")
    eq_calls = [c.args for c in db._q.eq.call_args_list]
    assert ("target_type", "provider") in eq_calls


def test_g2_target_id_filter_calls_eq():
    db = _make_db(rows=[])
    _audit_get(db, target_id="airbnb")
    eq_calls = [c.args for c in db._q.eq.call_args_list]
    assert ("target_id", "airbnb") in eq_calls


# ---------------------------------------------------------------------------
# Group H — limit validation
# ---------------------------------------------------------------------------

def test_h1_limit_zero_returns_400():
    db = _make_db()
    assert _audit_get(db, limit=0).status_code == 400


def test_h2_limit_501_returns_400():
    db = _make_db()
    assert _audit_get(db, limit=501).status_code == 400


def test_h3_limit_1_accepted():
    db = _make_db(rows=[])
    assert _audit_get(db, limit=1).status_code == 200


def test_h4_limit_500_accepted():
    db = _make_db(rows=[])
    assert _audit_get(db, limit=500).status_code == 200


def test_h5_limit_echoed_in_response():
    db = _make_db(rows=[])
    data = _body(_audit_get(db, limit=25))
    assert data["limit"] == 25


# ---------------------------------------------------------------------------
# Group I — DB error returns 500
# ---------------------------------------------------------------------------

def test_i1_query_error_returns_500():
    db = _make_db(query_error=True)
    assert _audit_get(db).status_code == 500
