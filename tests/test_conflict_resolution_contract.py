"""
Phase 184 — Contract tests for conflict resolution engine

Groups:
    A — conflict_resolution_writer: happy path (ConflictTask + OverrideRequest written)
    B — conflict_resolution_writer: edge cases (empty artifacts, DB errors swallowed)
    C — conflict_resolution_writer: audit event written to admin_audit_log
    D — POST /conflicts/resolve: no-conflict path (allowed=True, no artifacts)
    E — POST /conflicts/resolve: conflict path (PendingResolution + ConflictTask)
    F — POST /conflicts/resolve: validation errors (missing request_id, invalid body)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from services.conflict_resolution_writer import write_resolution

client = TestClient(app, raise_server_exceptions=False)

# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------

def _valid_token(tenant: str = "T1") -> str:
    import os
    import jwt as _jwt
    secret = os.environ.get("IHOUSE_JWT_SECRET", "dev-secret")
    return _jwt.encode(
        {"sub": tenant, "tenant_id": tenant, "exp": 9999999999},
        secret, algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_BASE_PAYLOAD = {
    "actor": {"actor_id": "U-1", "role": "worker"},
    "booking_candidate": {
        "booking_id": "airbnb_ABC",
        "property_id": "P-1",
        "start_utc": "2026-05-01",
        "end_utc": "2026-05-05",
    },
    "existing_bookings": [],
    "policy": {
        "statuses_blocking": ["ACTIVE"],
        "allow_admin_override": False,
        "conflict_task_type_id": "CONFLICT_REVIEW",
        "override_request_type_id": "CONFLICT_OVERRIDE",
    },
    "idempotency": {"request_id": "REQ-1"},
    "time": {"now_utc": "2026-05-01T12:00:00Z"},
}

_CONFLICTING_PAYLOAD = {
    **_BASE_PAYLOAD,
    "existing_bookings": [
        {
            "booking_id": "bookingcom_XYZ",
            "property_id": "P-1",
            "start_utc": "2026-05-03",
            "end_utc": "2026-05-07",
            "status": "ACTIVE",
        }
    ],
}


def _make_db() -> MagicMock:
    db = MagicMock()
    return db


# ---------------------------------------------------------------------------
# Group A — write_resolution: happy path
# ---------------------------------------------------------------------------

class TestGroupAWriterHappyPath:

    def test_a1_conflict_task_written_to_db(self):
        db = _make_db()
        artifacts = [{
            "artifact_type": "ConflictTask",
            "type_id": "CONFLICT_REVIEW",
            "priority": "High",
            "property_id": "P-1",
            "booking_id": "airbnb_ABC",
            "conflicts_found": ["bookingcom_XYZ"],
            "request_id": "REQ-1",
        }]
        written, _ = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        assert written == 1
        db.table.assert_called_with("conflict_resolution_queue")

    def test_a2_override_request_written(self):
        db = _make_db()
        artifacts = [
            {
                "artifact_type": "ConflictTask",
                "type_id": "CR", "priority": "High",
                "property_id": "P-1", "booking_id": "B-1",
                "conflicts_found": ["B-2"], "request_id": "R-1",
            },
            {
                "artifact_type": "OverrideRequest",
                "type_id": "CO", "required_approver_role": "admin",
                "property_id": "P-1", "booking_id": "B-1",
                "conflicts_found": ["B-2"], "request_id": "R-1",
            },
        ]
        written, _ = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        assert written == 2

    def test_a3_row_contains_tenant_id(self):
        db = _make_db()
        artifacts = [{
            "artifact_type": "ConflictTask", "type_id": "CR", "priority": "High",
            "property_id": "P-1", "booking_id": "B-1",
            "conflicts_found": [], "request_id": "R-1",
        }]
        write_resolution(
            db=db, tenant_id="MYTENANT",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        upserted = db.table.return_value.upsert.call_args[0][0]
        assert upserted["tenant_id"] == "MYTENANT"

    def test_a4_row_contains_conflict_id_uuid(self):
        import uuid
        db = _make_db()
        artifacts = [{
            "artifact_type": "ConflictTask", "type_id": "CR", "priority": "High",
            "property_id": "P-1", "booking_id": "B-1",
            "conflicts_found": [], "request_id": "R-1",
        }]
        write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        upserted = db.table.return_value.upsert.call_args[0][0]
        assert uuid.UUID(upserted["conflict_id"])

    def test_a5_upsert_uses_idempotency_conflict_key(self):
        db = _make_db()
        artifacts = [{
            "artifact_type": "ConflictTask", "type_id": "CR", "priority": "High",
            "property_id": "P-1", "booking_id": "B-1",
            "conflicts_found": [], "request_id": "R-1",
        }]
        write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        _, kwargs = db.table.return_value.upsert.call_args
        assert kwargs.get("on_conflict") == "booking_id,request_id,artifact_type"


# ---------------------------------------------------------------------------
# Group B — write_resolution: edge cases
# ---------------------------------------------------------------------------

class TestGroupBWriterEdgeCases:

    def test_b1_empty_artifacts_writes_nothing(self):
        db = _make_db()
        written, _ = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=[], events_to_emit=[],
        )
        assert written == 0

    def test_b2_unknown_artifact_type_skipped(self):
        db = _make_db()
        artifacts = [{
            "artifact_type": "UnknownThing",
            "property_id": "P-1", "booking_id": "B-1",
            "conflicts_found": [], "request_id": "R-1",
        }]
        written, _ = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        assert written == 0

    def test_b3_db_error_swallowed_returns_zero(self):
        db = _make_db()
        db.table.return_value.upsert.return_value.execute.side_effect = RuntimeError("DB down")
        artifacts = [{
            "artifact_type": "ConflictTask", "type_id": "CR", "priority": "High",
            "property_id": "P-1", "booking_id": "B-1",
            "conflicts_found": [], "request_id": "R-1",
        }]
        written, _ = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=artifacts, events_to_emit=[],
        )
        assert written == 0

    def test_b4_never_raises_on_any_exception(self):
        db = MagicMock()
        db.table.side_effect = Exception("Unexpected")
        result = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=[{"artifact_type": "ConflictTask", "property_id": "P-1",
                                   "booking_id": "B", "conflicts_found": [], "request_id": "R"}],
            events_to_emit=[],
        )
        assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# Group C — write_resolution: audit event
# ---------------------------------------------------------------------------

class TestGroupCAuditEvent:

    def test_c1_audit_event_written_to_admin_audit_log(self):
        db = _make_db()
        events = [{
            "event_type": "AuditEvent",
            "request_id": "R-1",
            "actor_id": "U-1",
            "role": "worker",
            "action": "booking_conflict_resolve",
            "entity_type": "booking",
            "entity_id": "B-1",
        }]
        _, audit_written = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=[], events_to_emit=events,
        )
        assert audit_written == 1
        db.table.assert_any_call("admin_audit_log")

    def test_c2_non_audit_events_skipped(self):
        db = _make_db()
        events = [{"event_type": "SomethingElse"}]
        _, audit_written = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=[], events_to_emit=events,
        )
        assert audit_written == 0

    def test_c3_audit_db_error_swallowed(self):
        db = _make_db()
        db.table.return_value.insert.return_value.execute.side_effect = RuntimeError("DB")
        events = [{
            "event_type": "AuditEvent", "request_id": "R-1",
            "actor_id": "U-1", "role": "worker",
            "action": "booking_conflict_resolve", "entity_type": "booking", "entity_id": "B-1",
        }]
        _, audit_written = write_resolution(
            db=db, tenant_id="T1",
            artifacts_to_create=[], events_to_emit=events,
        )
        assert audit_written == 0  # failed but no raise


# ---------------------------------------------------------------------------
# Group D — POST /conflicts/resolve: no conflict path
# ---------------------------------------------------------------------------

class TestGroupDEndpointNoConflict:

    def test_d1_no_conflicts_returns_200(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(0, 0)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_BASE_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        assert resp.status_code == 200

    def test_d2_no_conflicts_allowed_true(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(0, 0)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_BASE_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        data = resp.json()
        assert data["decision"]["allowed"] is True

    def test_d3_no_conflicts_no_artifacts_created(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(0, 0)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_BASE_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        data = resp.json()
        assert data["artifacts_created"] == []

    def test_d4_response_contains_tenant_id(self):
        import os
        from unittest.mock import patch as _patch
        with _patch.dict(os.environ, {"IHOUSE_JWT_SECRET": "dev-secret"}), \
             patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(0, 0)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_BASE_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token('T1')}"},
            )
        assert resp.json()["tenant_id"] == "T1"


# ---------------------------------------------------------------------------
# Group E — POST /conflicts/resolve: conflict path
# ---------------------------------------------------------------------------

class TestGroupEEndpointConflict:

    def test_e1_conflict_returns_200(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(1, 1)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_CONFLICTING_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        assert resp.status_code == 200

    def test_e2_conflict_enforced_status_pending_resolution(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(1, 1)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_CONFLICTING_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        data = resp.json()
        assert data["decision"]["enforced_status"] == "PendingResolution"

    def test_e3_conflict_conflict_task_in_artifacts(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(1, 1)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_CONFLICTING_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        artifacts = resp.json()["artifacts_created"]
        assert any(a["artifact_type"] == "ConflictTask" for a in artifacts)

    def test_e4_conflict_conflicts_found_not_empty(self):
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(1, 1)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=_CONFLICTING_PAYLOAD,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        assert resp.json()["decision"]["conflicts_found"] != []

    def test_e5_admin_with_override_gets_override_request(self):
        payload = {
            **_CONFLICTING_PAYLOAD,
            "actor": {"actor_id": "ADMIN-1", "role": "admin"},
            "policy": {**_CONFLICTING_PAYLOAD["policy"], "allow_admin_override": True},
        }
        with patch("api.conflicts_router._get_supabase_client") as mock_db, \
             patch("api.conflicts_router.write_resolution", return_value=(2, 1)):
            mock_db.return_value = _make_db()
            resp = client.post(
                "/conflicts/resolve",
                json=payload,
                headers={"Authorization": f"Bearer {_valid_token()}"},
            )
        artifacts = resp.json()["artifacts_created"]
        types = {a["artifact_type"] for a in artifacts}
        assert "OverrideRequest" in types


# ---------------------------------------------------------------------------
# Group F — POST /conflicts/resolve: validation
# ---------------------------------------------------------------------------

class TestGroupFValidation:

    def test_f1_missing_request_id_returns_400(self):
        payload = {**_BASE_PAYLOAD, "idempotency": {}}
        resp = client.post(
            "/conflicts/resolve",
            json=payload,
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )
        assert resp.status_code == 400

    def test_f2_missing_auth_returns_401(self):
        import os
        from unittest.mock import patch as _patch
        with _patch.dict(os.environ, {"IHOUSE_JWT_SECRET": "test-secret-for-auth-check"}):
            resp = client.post("/conflicts/resolve", json=_BASE_PAYLOAD)
        assert resp.status_code in {401, 403}

    def test_f3_invalid_json_returns_400(self):
        resp = client.post(
            "/conflicts/resolve",
            content=b"not-json",
            headers={
                "Authorization": f"Bearer {_valid_token()}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400

    def test_f4_invalid_window_returns_400(self):
        """start_utc >= end_utc → skill returns INVALID_WINDOW → 400."""
        payload = {
            **_BASE_PAYLOAD,
            "booking_candidate": {
                **_BASE_PAYLOAD["booking_candidate"],
                "start_utc": "2026-05-05",
                "end_utc": "2026-05-01",  # end before start
            },
        }
        resp = client.post(
            "/conflicts/resolve",
            json=payload,
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )
        assert resp.status_code == 400

    def test_f5_endpoint_registered_in_openapi(self):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json()["paths"]
        assert "/conflicts/resolve" in paths
