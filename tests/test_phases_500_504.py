"""
Phases 500-504 — Block 4 Combined Tests

Phase 500: Webhook Retry
Phase 501: Currency Service
Phase 502: Financial Writer
Phase 503: Notification Preferences
Phase 504: Checkpoint (covered by full suite run)
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
    db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"id": "test"}])
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return db


# ---------------------------------------------------------------------------
# Phase 500: Webhook Retry Tests
# ---------------------------------------------------------------------------

class TestWebhookRetry:

    def test_calculate_delay(self):
        from services.webhook_retry import _calculate_delay
        assert _calculate_delay(0) == 30       # 30 seconds
        assert _calculate_delay(1) == 120      # 2 minutes
        assert _calculate_delay(2) == 480      # 8 minutes
        assert _calculate_delay(3) == 1920     # 32 minutes

    def test_enqueue_retry_queues(self, mock_db):
        from services.webhook_retry import enqueue_retry
        result = enqueue_retry(
            db=mock_db,
            tenant_id="t1",
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            event_type="booking_created",
            attempt=0,
        )
        assert result["status"] == "queued"
        assert result["attempt"] == 1

    def test_enqueue_retry_moves_to_dlq(self, mock_db):
        from services.webhook_retry import enqueue_retry, MAX_RETRIES
        result = enqueue_retry(
            db=mock_db,
            tenant_id="t1",
            webhook_url="https://example.com/webhook",
            payload={"event": "test"},
            event_type="booking_created",
            attempt=MAX_RETRIES,
        )
        assert result["status"] == "moved_to_dlq"


# ---------------------------------------------------------------------------
# Phase 501: Currency Service Tests
# ---------------------------------------------------------------------------

class TestCurrencyService:

    def test_convert_same_currency(self):
        from services.currency_service import convert
        result = convert(100, "THB", "THB")
        assert result["amount"] == 100
        assert result["rate"] == 1.0

    def test_convert_with_rates(self):
        from services.currency_service import convert
        rates = {"THB": 1.0, "USD": 0.028}
        result = convert(1000, "THB", "USD", rates)
        assert result["converted_amount"] == 28.0
        assert result["target_currency"] == "USD"

    def test_fallback_rates_exist(self):
        from services.currency_service import FALLBACK_RATES
        assert "THB" in FALLBACK_RATES
        assert "USD" in FALLBACK_RATES
        assert "EUR" in FALLBACK_RATES
        assert FALLBACK_RATES["THB"] == 1.0


# ---------------------------------------------------------------------------
# Phase 502: Financial Writer Tests
# ---------------------------------------------------------------------------

class TestFinancialWriter:

    def test_record_manual_payment(self, mock_db):
        from services.financial_writer import record_manual_payment
        result = record_manual_payment(
            db=mock_db,
            tenant_id="t1",
            booking_id="bk_123",
            amount=5000.0,
            currency="THB",
            notes="Cash payment",
        )
        assert result.get("status") == "recorded"
        assert result["amount"] == 5000.0

    def test_generate_payout_record(self, mock_db):
        mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[
                {"booking_id": "bk1", "total_gross": "10000", "net_to_property": "8500", "management_fee": "1500"},
                {"booking_id": "bk2", "total_gross": "8000", "net_to_property": "6800", "management_fee": "1200"},
            ]
        )

        from services.financial_writer import generate_payout_record
        result = generate_payout_record(
            db=mock_db,
            tenant_id="t1",
            property_id="prop1",
            period_start="2026-03-01",
            period_end="2026-04-01",
            mgmt_fee_pct=15.0,
        )
        assert result["total_gross"] == 18000.0
        assert result["management_fee"] == 2700.0
        assert result["net_payout"] == 15300.0
        assert result["bookings_count"] == 2


# ---------------------------------------------------------------------------
# Phase 503: Notification Preferences Tests
# ---------------------------------------------------------------------------

class TestNotificationPreferences:

    def test_get_defaults(self, mock_db):
        from services.notification_preferences import get_preferences, NOTIFICATION_TYPES
        result = get_preferences(mock_db, "t1", "user1")
        assert result["user_id"] == "user1"
        assert result["enabled_types"] == NOTIFICATION_TYPES

    def test_update_invalid_channel(self, mock_db):
        from services.notification_preferences import update_preferences
        result = update_preferences(
            db=mock_db,
            tenant_id="t1",
            user_id="user1",
            preferred_channel="carrier_pigeon",
        )
        assert "error" in result

    def test_update_valid_prefs(self, mock_db):
        from services.notification_preferences import update_preferences
        result = update_preferences(
            db=mock_db,
            tenant_id="t1",
            user_id="user1",
            enabled_types=["booking_created", "task_assigned"],
            preferred_channel="whatsapp",
        )
        assert "error" not in result

    def test_notification_types_defined(self):
        from services.notification_preferences import NOTIFICATION_TYPES
        assert "booking_created" in NOTIFICATION_TYPES
        assert "task_escalated" in NOTIFICATION_TYPES
        assert len(NOTIFICATION_TYPES) >= 8
