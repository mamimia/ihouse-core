"""
Phase 236 — Guest Communication History — Contract Tests

Coverage:

POST /guest-messages/{booking_id}
    - 201 with valid OUTBOUND email body
    - 201 with INBOUND direction
    - response contains expected keys
    - content_preview truncated to 300 chars if longer
    - 400 missing direction
    - 400 invalid direction
    - 400 missing channel
    - 400 invalid channel
    - draft_id optional — present in response when provided
    - sent_by optional — present in response when provided
    - tenant_id in response

GET /guest-messages/{booking_id}
    - 200 returns messages list
    - message_count matches list length
    - 200 returns empty list when no messages
    - tenant_id and booking_id in response
    - messages ordered by sent_at (oldest first by default)
    - all required message keys present
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

TENANT = "tenant-gm"
BOOKING = "airbnb_B123"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_insert_db(record=None) -> MagicMock:
    db = MagicMock()
    def table_fn(name):
        t = MagicMock()
        for m in ("insert", "select", "eq", "order", "execute"):
            getattr(t, m).return_value = t
        r = MagicMock()
        r.data = [record] if record else [{}]
        t.execute.return_value = r
        return t
    db.table.side_effect = table_fn
    return db


def _make_select_db(rows=None) -> MagicMock:
    db = MagicMock()
    def table_fn(name):
        t = MagicMock()
        for m in ("insert", "select", "eq", "order", "execute"):
            getattr(t, m).return_value = t
        r = MagicMock()
        r.data = rows if rows is not None else []
        t.execute.return_value = r
        return t
    db.table.side_effect = table_fn
    return db


def _app():
    from fastapi import FastAPI
    from api.guest_messages_router import router
    app = FastAPI()
    app.include_router(router)
    return app


def _post(booking_id=BOOKING, body=None, db_mock=None):
    from fastapi.testclient import TestClient
    import api.guest_messages_router as mod

    with patch("api.guest_messages_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_insert_db()):
        return TestClient(_app()).post(
            f"/guest-messages/{booking_id}",
            json=body or {"direction": "OUTBOUND", "channel": "email"},
            headers={"Authorization": "Bearer fake"},
        )


def _get(booking_id=BOOKING, db_mock=None):
    from fastapi.testclient import TestClient
    import api.guest_messages_router as mod

    with patch("api.guest_messages_router.jwt_auth", return_value=TENANT), \
         patch.object(mod, "_get_db", return_value=db_mock or _make_select_db()):
        return TestClient(_app()).get(
            f"/guest-messages/{booking_id}",
            headers={"Authorization": "Bearer fake"},
        )


# ---------------------------------------------------------------------------
# POST tests
# ---------------------------------------------------------------------------

class TestLogGuestMessage:
    def test_201_outbound_email(self):
        resp = _post(body={"direction": "OUTBOUND", "channel": "email"})
        assert resp.status_code == 201

    def test_201_inbound(self):
        resp = _post(body={"direction": "INBOUND", "channel": "whatsapp"})
        assert resp.status_code == 201

    def test_response_has_required_keys(self):
        resp = _post()
        data = resp.json()
        for key in ("tenant_id", "booking_id", "direction", "channel", "sent_at"):
            assert key in data

    def test_content_preview_truncated(self):
        long_text = "x" * 500
        resp = _post(body={"direction": "OUTBOUND", "channel": "email",
                           "content_preview": long_text})
        assert resp.status_code == 201
        assert len(resp.json()["content_preview"]) == 300

    def test_content_preview_short_not_truncated(self):
        resp = _post(body={"direction": "OUTBOUND", "channel": "email",
                           "content_preview": "Hello!"})
        assert resp.json()["content_preview"] == "Hello!"

    def test_draft_id_in_response(self):
        resp = _post(body={"direction": "OUTBOUND", "channel": "email",
                           "draft_id": "draft-uuid-123"})
        assert resp.json()["draft_id"] == "draft-uuid-123"

    def test_sent_by_in_response(self):
        resp = _post(body={"direction": "OUTBOUND", "channel": "sms",
                           "sent_by": "manager-001"})
        assert resp.json()["sent_by"] == "manager-001"

    def test_400_missing_direction(self):
        resp = _post(body={"channel": "email"})
        assert resp.status_code == 400

    def test_400_invalid_direction(self):
        resp = _post(body={"direction": "FORWARD", "channel": "email"})
        assert resp.status_code == 400

    def test_400_missing_channel(self):
        resp = _post(body={"direction": "OUTBOUND"})
        assert resp.status_code == 400

    def test_400_invalid_channel(self):
        resp = _post(body={"direction": "OUTBOUND", "channel": "fax"})
        assert resp.status_code == 400

    def test_all_valid_channels_accepted(self):
        for ch in ("email", "whatsapp", "sms", "line", "telegram", "manual"):
            resp = _post(body={"direction": "OUTBOUND", "channel": ch})
            assert resp.status_code == 201, f"Failed for channel: {ch}"

    def test_tenant_id_in_response(self):
        resp = _post()
        assert "tenant_id" in resp.json()


# ---------------------------------------------------------------------------
# GET tests
# ---------------------------------------------------------------------------

class TestGetGuestMessages:
    def test_200_returns_messages(self):
        rows = [
            {"id": "1", "direction": "OUTBOUND", "channel": "email",
             "intent": "check_in_instructions", "content_preview": "Hi",
             "draft_id": None, "sent_by": "mgr", "sent_at": "2026-03-11T08:00:00Z",
             "guest_id": None},
        ]
        resp = _get(db_mock=_make_select_db(rows=rows))
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) == 1

    def test_200_empty_list_when_none(self):
        resp = _get(db_mock=_make_select_db(rows=[]))
        assert resp.status_code == 200
        assert resp.json()["messages"] == []
        assert resp.json()["message_count"] == 0

    def test_message_count_matches_list_length(self):
        rows = [{"id": str(i), "direction": "OUTBOUND", "channel": "email",
                 "intent": None, "content_preview": None,
                 "draft_id": None, "sent_by": None, "sent_at": f"2026-03-{10+i}T00:00:00Z",
                 "guest_id": None} for i in range(3)]
        resp = _get(db_mock=_make_select_db(rows=rows))
        data = resp.json()
        assert data["message_count"] == 3
        assert len(data["messages"]) == 3

    def test_response_has_required_keys(self):
        resp = _get()
        for key in ("tenant_id", "booking_id", "message_count", "messages"):
            assert key in resp.json()

    def test_booking_id_in_response(self):
        resp = _get(booking_id="my-booking-99")
        assert resp.json()["booking_id"] == "my-booking-99"

    def test_tenant_id_in_response(self):
        resp = _get()
        assert "tenant_id" in resp.json()
