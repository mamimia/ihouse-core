"""
Phase 169 — Admin Settings: PATCH /admin/registry/providers/{provider} contract tests

All 15 tests for the partial-update endpoint.

Groups:
  A — success: single field update
  B — success: multiple fields
  C — 404 when provider not found
  D — validation: empty body, bad auth_method, bad bool, bad rate_limit, bad tier, unknown-only fields
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

from api.capability_registry_router import patch_provider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


_PROVIDER_ROW = {
    "id": 1,
    "provider": "airbnb",
    "tier": "A",
    "supports_api_write": True,
    "supports_ical_push": True,
    "supports_ical_pull": True,
    "rate_limit_per_min": 60,
    "auth_method": "oauth2",
    "write_api_base_url": None,
    "notes": None,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


def _make_db(found: bool = True) -> MagicMock:
    db = MagicMock()
    q = MagicMock()
    q.select.return_value = q
    q.eq.return_value = q
    q.limit.return_value = q
    q.update.return_value = q

    if found:
        # First execute (check) returns the record; second execute (update) returns updated row
        q.execute.side_effect = [
            MagicMock(data=[{"provider": "airbnb"}]),
            MagicMock(data=[_PROVIDER_ROW]),
        ]
    else:
        q.execute.return_value = MagicMock(data=[])

    db.table.return_value = q
    return db


def _patch(db, provider="airbnb", body=None):
    return _run(patch_provider(
        provider=provider,
        body=body or {"rate_limit_per_min": 30},
        tenant_id="t1",
        client=db,
    ))


def _body(resp):
    return json.loads(resp.body)


# ---------------------------------------------------------------------------
# Group A — Success: single field update
# ---------------------------------------------------------------------------

def test_a1_patch_returns_200():
    db = _make_db(found=True)
    assert _patch(db).status_code == 200


def test_a2_patch_rate_limit_returns_provider_record():
    db = _make_db(found=True)
    data = _body(_patch(db, body={"rate_limit_per_min": 30}))
    assert "provider" in data


def test_a3_patch_notes_accepted():
    db = _make_db(found=True)
    resp = _patch(db, body={"notes": "Updated via admin UI"})
    assert resp.status_code == 200


def test_a4_patch_supports_api_write_toggle():
    db = _make_db(found=True)
    resp = _patch(db, body={"supports_api_write": False})
    assert resp.status_code == 200


def test_a5_patch_auth_method_accepted():
    db = _make_db(found=True)
    resp = _patch(db, body={"auth_method": "api_key"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group B — Success: multiple fields
# ---------------------------------------------------------------------------

def test_b1_patch_multiple_fields():
    db = _make_db(found=True)
    resp = _patch(db, body={
        "rate_limit_per_min": 45,
        "supports_ical_push": True,
        "notes": "batch update",
    })
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Group C — 404 when provider not registered
# ---------------------------------------------------------------------------

def test_c1_patch_unknown_provider_returns_404():
    db = _make_db(found=False)
    resp = _patch(db, provider="nonexistent")
    assert resp.status_code == 404


def test_c2_patch_404_error_code():
    db = _make_db(found=False)
    data = _body(_patch(db, provider="nonexistent"))
    assert data.get("code") == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Group D — Validation errors
# ---------------------------------------------------------------------------

def test_d1_empty_body_returns_400():
    db = _make_db()
    resp = _run(patch_provider(
        provider="airbnb",
        body={},
        tenant_id="t1",
        client=db,
    ))
    assert resp.status_code == 400


def test_d2_invalid_auth_method_returns_400():
    db = _make_db()
    resp = _patch(db, body={"auth_method": "mtls"})
    assert resp.status_code == 400


def test_d3_invalid_bool_field_returns_400():
    db = _make_db()
    resp = _patch(db, body={"supports_api_write": "yes"})
    assert resp.status_code == 400


def test_d4_negative_rate_limit_returns_400():
    db = _make_db()
    resp = _patch(db, body={"rate_limit_per_min": -5})
    assert resp.status_code == 400


def test_d5_invalid_tier_returns_400():
    db = _make_db()
    resp = _patch(db, body={"tier": "Z"})
    assert resp.status_code == 400


def test_d6_unknown_only_fields_returns_400():
    """Only unknown fields supplied — none pass the allowed-field filter."""
    db = _make_db()
    resp = _patch(db, body={"created_at": "2026-01-01", "id": 99})
    assert resp.status_code == 400


def test_d7_validation_error_code():
    db = _make_db()
    data = _body(_patch(db, body={"rate_limit_per_min": -1}))
    assert data.get("code") == "VALIDATION_ERROR"
