"""
Contract tests — Phase 299: Notification Dispatch Layer
=========================================================

Covers:
- notification_dispatcher.py: _log_notification, _update_log_status
- notification_dispatcher.py: dispatch_sms (dry-run, sent, failed)
- notification_dispatcher.py: dispatch_email (dry-run, sent, failed)
- notification_dispatcher.py: dispatch_guest_token_notification
- notification_dispatcher.py: list_notification_log
- notification_router: POST /notifications/send-sms
- notification_router: POST /notifications/send-email
- notification_router: POST /notifications/guest-token-send
- notification_router: GET /notifications/log
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-hs256-key-ok")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-secret-hs256")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


def _make_db(row=None):
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value.data = [row or {"notification_id": "n-1"}]
    db.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"notification_id": "n-1"}]
    return db


# ---------------------------------------------------------------------------
# notification_dispatcher.py — service tests
# ---------------------------------------------------------------------------

class TestLogNotification:
    def test_inserts_row(self):
        from services.notification_dispatcher import _log_notification
        db = _make_db({"notification_id": "n-1", "status": "pending"})
        row = _log_notification(
            db, "t1", "sms", "+66800000000", "guest_token", "preview text",
        )
        assert row["notification_id"] == "n-1"

    def test_returns_empty_on_db_error(self):
        from services.notification_dispatcher import _log_notification
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        row = _log_notification(db, "t1", "sms", "+66800000000", "generic", "text")
        assert row == {}


class TestDispatchSmsDryRun:
    def test_dry_run_when_env_absent(self):
        from services.notification_dispatcher import dispatch_sms
        for var in ("IHOUSE_TWILIO_SID", "IHOUSE_TWILIO_TOKEN", "IHOUSE_TWILIO_FROM"):
            os.environ.pop(var, None)
        db = _make_db()
        result = dispatch_sms(db, "t1", "+66800000000", "Test message")
        assert result["status"] == "dry_run"
        assert result["channel"] == "sms"

    def test_dry_run_partial_env(self):
        from services.notification_dispatcher import dispatch_sms
        os.environ["IHOUSE_TWILIO_SID"] = "SID123"
        os.environ.pop("IHOUSE_TWILIO_TOKEN", None)
        os.environ.pop("IHOUSE_TWILIO_FROM", None)
        db = _make_db()
        result = dispatch_sms(db, "t1", "+66800000000", "Test")
        assert result["status"] == "dry_run"
        os.environ.pop("IHOUSE_TWILIO_SID", None)

    def test_sent_when_twilio_succeeds(self):
        from services.notification_dispatcher import dispatch_sms
        os.environ["IHOUSE_TWILIO_SID"] = "SID"
        os.environ["IHOUSE_TWILIO_TOKEN"] = "TOKEN"
        os.environ["IHOUSE_TWILIO_FROM"] = "+1555000"
        db = _make_db()
        mock_msg = MagicMock()
        mock_msg.sid = "SM-12345"
        with patch("services.notification_dispatcher.Client") as mock_client_cls:
            mock_client_cls.return_value.messages.create.return_value = mock_msg
            result = dispatch_sms(db, "t1", "+66800000000", "Hello")
        assert result["status"] == "sent"
        assert result["provider_id"] == "SM-12345"
        for v in ("IHOUSE_TWILIO_SID", "IHOUSE_TWILIO_TOKEN", "IHOUSE_TWILIO_FROM"):
            os.environ.pop(v, None)

    def test_failed_when_twilio_raises(self):
        from services.notification_dispatcher import dispatch_sms
        os.environ["IHOUSE_TWILIO_SID"] = "SID"
        os.environ["IHOUSE_TWILIO_TOKEN"] = "TOKEN"
        os.environ["IHOUSE_TWILIO_FROM"] = "+1555000"
        db = _make_db()
        with patch("services.notification_dispatcher.Client") as mock_client_cls:
            mock_client_cls.return_value.messages.create.side_effect = Exception("Twilio error")
            result = dispatch_sms(db, "t1", "+66800000000", "Hello")
        assert result["status"] == "failed"
        assert "error" in result
        for v in ("IHOUSE_TWILIO_SID", "IHOUSE_TWILIO_TOKEN", "IHOUSE_TWILIO_FROM"):
            os.environ.pop(v, None)


class TestDispatchEmailDryRun:
    def test_dry_run_when_env_absent(self):
        from services.notification_dispatcher import dispatch_email
        os.environ.pop("IHOUSE_SENDGRID_KEY", None)
        os.environ.pop("IHOUSE_SENDGRID_FROM", None)
        db = _make_db()
        result = dispatch_email(db, "t1", "guest@eg.com", "Subject", "<p>Hello</p>")
        assert result["status"] == "dry_run"
        assert result["channel"] == "email"

    def test_failed_when_sendgrid_raises(self):
        from services.notification_dispatcher import dispatch_email
        os.environ["IHOUSE_SENDGRID_KEY"] = "SG.key"
        os.environ["IHOUSE_SENDGRID_FROM"] = "noreply@domaniqo.com"
        db = _make_db()
        with patch("services.notification_dispatcher.sendgrid") as mock_sg:
            mock_sg.SendGridAPIClient.return_value.send.side_effect = Exception("SG error")
            result = dispatch_email(db, "t1", "guest@eg.com", "Subject", "<p>Hello</p>")
        assert result["status"] == "failed"
        os.environ.pop("IHOUSE_SENDGRID_KEY", None)
        os.environ.pop("IHOUSE_SENDGRID_FROM", None)


class TestDispatchGuestTokenNotification:
    def test_no_recipient_raises(self):
        from services.notification_dispatcher import dispatch_guest_token_notification
        db = _make_db()
        with pytest.raises(ValueError, match="At least one"):
            dispatch_guest_token_notification(
                db, "t1", "B1", "raw-token", "https://example.com",
                to_phone=None, to_email=None,
            )

    def test_sms_only_returns_one_result(self):
        from services.notification_dispatcher import dispatch_guest_token_notification
        db = _make_db()
        with patch("services.notification_dispatcher.dispatch_sms",
                   return_value={"status": "dry_run", "channel": "sms"}):
            results = dispatch_guest_token_notification(
                db, "t1", "B1", "raw-token", "https://portal.com",
                to_phone="+66800000000",
            )
        assert len(results) == 1
        assert results[0]["channel"] == "sms"

    def test_both_channels_returns_two_results(self):
        from services.notification_dispatcher import dispatch_guest_token_notification
        db = _make_db()
        with patch("services.notification_dispatcher.dispatch_sms",
                   return_value={"status": "dry_run", "channel": "sms"}), \
             patch("services.notification_dispatcher.dispatch_email",
                   return_value={"status": "dry_run", "channel": "email"}):
            results = dispatch_guest_token_notification(
                db, "t1", "B1", "raw-token", "https://portal.com",
                to_phone="+66800000000",
                to_email="guest@eg.com",
            )
        assert len(results) == 2


class TestListNotificationLog:
    def test_returns_entries(self):
        from services.notification_dispatcher import list_notification_log
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"notification_id": "n-1", "status": "sent"},
        ]
        result = list_notification_log(db, "t1")
        assert len(result) == 1

    def test_returns_empty_on_error(self):
        from services.notification_dispatcher import list_notification_log
        db = MagicMock()
        db.table.side_effect = Exception("DB error")
        result = list_notification_log(db, "t1")
        assert result == []


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.notification_router import router
    _app = FastAPI()
    _app.include_router(router)
    return TestClient(_app)


class TestSendSmsEndpoint:
    def test_sms_dry_run_returns_200(self, client):
        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.dispatch_sms",
                   return_value={"status": "dry_run", "channel": "sms", "recipient": "+66800000000"}):
            resp = client.post(
                "/notifications/send-sms",
                json={"to_number": "+66800000000", "body": "Hello", "notification_type": "generic"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dry_run"


class TestSendEmailEndpoint:
    def test_email_dry_run_returns_200(self, client):
        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.dispatch_email",
                   return_value={"status": "dry_run", "channel": "email", "recipient": "g@eg.com"}):
            resp = client.post(
                "/notifications/send-email",
                json={"to_email": "g@eg.com", "subject": "Hi", "body_html": "<p>Hi</p>"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200


class TestGuestTokenSendEndpoint:
    def test_no_recipient_returns_422(self, client):
        resp = client.post(
            "/notifications/guest-token-send",
            json={"booking_ref": "B1"},
            headers={"Authorization": "Bearer dummy"},
        )
        assert resp.status_code == 422

    def test_success_returns_201(self, client):
        from services.guest_token import issue_guest_token, record_guest_token
        token, exp = issue_guest_token("B1", "", 3600)
        token_record = {"token_id": "t-1"}
        dispatch_results = [{"status": "dry_run", "channel": "sms"}]
        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.issue_guest_token", return_value=(token, exp)), \
             patch("api.notification_router.record_guest_token", return_value=token_record), \
             patch("api.notification_router.dispatch_guest_token_notification",
                   return_value=dispatch_results):
            resp = client.post(
                "/notifications/guest-token-send",
                json={"booking_ref": "B1", "to_phone": "+66800000000"},
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["channels_used"] == 1
        assert body["token_id"] == "t-1"

    def test_no_secret_returns_503(self, client):
        old = os.environ.pop("IHOUSE_GUEST_TOKEN_SECRET", None)
        try:
            resp = client.post(
                "/notifications/guest-token-send",
                json={"booking_ref": "B1", "to_phone": "+66800000000"},
                headers={"Authorization": "Bearer dummy"},
            )
            assert resp.status_code == 503
        finally:
            if old:
                os.environ["IHOUSE_GUEST_TOKEN_SECRET"] = old


class TestNotificationLogEndpoint:
    def test_returns_entries(self, client):
        entries = [{"notification_id": "n-1", "status": "sent"}]
        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.list_notification_log", return_value=entries):
            resp = client.get(
                "/notifications/log",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_reference_id_filter_passes_through(self, client):
        with patch("api.notification_router._get_db"), \
             patch("api.notification_router.list_notification_log", return_value=[]) as mock_list:
            resp = client.get(
                "/notifications/log?reference_id=B1",
                headers={"Authorization": "Bearer dummy"},
            )
        assert resp.status_code == 200
        mock_list.assert_called_once()
        _, kwargs = mock_list.call_args
        assert kwargs.get("reference_id") == "B1"
