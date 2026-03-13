"""
Phase 486 — Notification Dispatcher Tests

Tests for:
1. WhatsApp dispatch (dry_run mode)
2. SMS dispatch (dry_run mode)
3. Email dispatch (dry_run mode)
4. Booking event auto-notification
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """Mock Supabase client."""
    db = MagicMock()
    # Default: notification_log insert returns a fake row
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"notification_id": "test-notif-123"}]
    )
    db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    return db


# ---------------------------------------------------------------------------
# dispatch_sms tests
# ---------------------------------------------------------------------------

class TestDispatchSms:

    def test_dry_run_no_twilio_credentials(self, mock_db, monkeypatch):
        """Without Twilio env vars, should log dry_run."""
        monkeypatch.delenv("IHOUSE_TWILIO_SID", raising=False)
        monkeypatch.delenv("IHOUSE_TWILIO_TOKEN", raising=False)
        monkeypatch.delenv("IHOUSE_TWILIO_FROM", raising=False)

        from services.notification_dispatcher import dispatch_sms
        result = dispatch_sms(
            db=mock_db,
            tenant_id="t1",
            to_number="+66812345678",
            body="Test message",
            notification_type="test",
        )
        assert result["status"] == "dry_run"
        assert result["channel"] == "sms"
        assert result["recipient"] == "+66812345678"

    def test_sms_logs_to_notification_log(self, mock_db, monkeypatch):
        """Verify insert is called on notification_log."""
        monkeypatch.delenv("IHOUSE_TWILIO_SID", raising=False)
        from services.notification_dispatcher import dispatch_sms
        dispatch_sms(
            db=mock_db,
            tenant_id="t1",
            to_number="+1234567890",
            body="Hello",
        )
        mock_db.table.assert_any_call("notification_log")


# ---------------------------------------------------------------------------
# dispatch_email tests
# ---------------------------------------------------------------------------

class TestDispatchEmail:

    def test_dry_run_no_sendgrid_credentials(self, mock_db, monkeypatch):
        """Without SendGrid env vars, should log dry_run."""
        monkeypatch.delenv("IHOUSE_SENDGRID_KEY", raising=False)
        monkeypatch.delenv("IHOUSE_SENDGRID_FROM", raising=False)

        from services.notification_dispatcher import dispatch_email
        result = dispatch_email(
            db=mock_db,
            tenant_id="t1",
            to_email="user@example.com",
            subject="Test",
            body_html="<p>Hello</p>",
            notification_type="test",
        )
        assert result["status"] == "dry_run"
        assert result["channel"] == "email"


# ---------------------------------------------------------------------------
# dispatch_whatsapp tests — Phase 486
# ---------------------------------------------------------------------------

class TestDispatchWhatsapp:

    def test_dry_run_no_whatsapp_credentials(self, mock_db, monkeypatch):
        """Without Twilio WhatsApp env vars, should log dry_run."""
        monkeypatch.delenv("IHOUSE_TWILIO_SID", raising=False)
        monkeypatch.delenv("IHOUSE_TWILIO_TOKEN", raising=False)
        monkeypatch.delenv("IHOUSE_TWILIO_WHATSAPP_FROM", raising=False)

        from services.notification_dispatcher import dispatch_whatsapp
        result = dispatch_whatsapp(
            db=mock_db,
            tenant_id="t1",
            to_number="+66812345678",
            body="WhatsApp test",
            notification_type="test",
        )
        assert result["status"] == "dry_run"
        assert result["channel"] == "whatsapp"
        assert result["recipient"] == "+66812345678"

    def test_whatsapp_logs_to_notification_log(self, mock_db, monkeypatch):
        """Verify WhatsApp dispatch logs to notification_log."""
        monkeypatch.delenv("IHOUSE_TWILIO_SID", raising=False)
        from services.notification_dispatcher import dispatch_whatsapp
        dispatch_whatsapp(
            db=mock_db,
            tenant_id="t1",
            to_number="+1234567890",
            body="Test",
        )
        mock_db.table.assert_any_call("notification_log")


# ---------------------------------------------------------------------------
# notify_on_booking_event tests — Phase 486
# ---------------------------------------------------------------------------

class TestNotifyOnBookingEvent:

    def test_no_channels_returns_empty(self, mock_db):
        """When no notification channels are registered, returns empty list."""
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )
        from services.notification_dispatcher import notify_on_booking_event
        results = notify_on_booking_event(
            db=mock_db,
            tenant_id="t1",
            booking_id="bk_123",
            event_type="BOOKING_CREATED",
        )
        assert results == []

    def test_dispatches_to_sms_channel(self, mock_db, monkeypatch):
        """When an SMS channel is registered, dispatches via SMS."""
        monkeypatch.delenv("IHOUSE_TWILIO_SID", raising=False)

        # First call for notification_channels query
        chan_mock = MagicMock()
        chan_mock.data = [
            {"user_id": "u1", "channel_type": "sms", "channel_id": "+66812345678"},
        ]
        # Need to handle the chained eq calls for notification_channels
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = chan_mock

        from services.notification_dispatcher import notify_on_booking_event
        results = notify_on_booking_event(
            db=mock_db,
            tenant_id="t1",
            booking_id="airbnb_ABC",
            event_type="BOOKING_CREATED",
            property_id="PROP1",
            guest_name="John Doe",
        )
        # Should have at least one dispatch result
        assert len(results) >= 1

    def test_dispatches_to_email_channel(self, mock_db, monkeypatch):
        """When an email channel is registered, dispatches via email."""
        monkeypatch.delenv("IHOUSE_SENDGRID_KEY", raising=False)

        chan_mock = MagicMock()
        chan_mock.data = [
            {"user_id": "u1", "channel_type": "email", "channel_id": "mgr@hotel.com"},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = chan_mock

        from services.notification_dispatcher import notify_on_booking_event
        results = notify_on_booking_event(
            db=mock_db,
            tenant_id="t1",
            booking_id="booking_XYZ",
            event_type="BOOKING_CANCELED",
        )
        assert len(results) >= 1
