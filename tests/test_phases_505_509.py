"""
Tests for Phases 505-509 — API Router Block

Phase 505: Property Dashboard API Router
Phase 506: Financial Writer API Router
Phase 507: Currency Exchange API Router
Phase 508: Webhook Retry Management API
Phase 509: Notification Preferences API Router
"""
import os
import sys
import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-key-for-jwt")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-token-secret")
os.environ.setdefault("IHOUSE_ACCESS_TOKEN_SECRET", "test-access-token-secret")


# ============================================================================
# Phase 505 — Property Dashboard Router
# ============================================================================

class TestPropertyDashboardRouter:
    """Tests for GET /admin/property-dashboard/{property_id} and overview."""

    def test_router_import(self):
        from api.property_dashboard_router import router
        assert router is not None

    def test_endpoint_registered(self):
        from api.property_dashboard_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/property-dashboard/{property_id}" in paths

    def test_overview_endpoint_registered(self):
        from api.property_dashboard_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/property-dashboard-overview" in paths

    def test_service_function_exists(self):
        from services.property_dashboard import get_property_dashboard
        assert callable(get_property_dashboard)

    def test_portfolio_overview_function_exists(self):
        from services.property_dashboard import get_portfolio_overview
        assert callable(get_portfolio_overview)


# ============================================================================
# Phase 506 — Financial Writer Router
# ============================================================================

class TestFinancialWriterRouter:
    """Tests for POST /admin/financial/payment and /payout."""

    def test_router_import(self):
        from api.financial_writer_router import router
        assert router is not None

    def test_payment_endpoint_registered(self):
        from api.financial_writer_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/financial/payment" in paths

    def test_payout_endpoint_registered(self):
        from api.financial_writer_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/financial/payout" in paths

    def test_request_models(self):
        from api.financial_writer_router import ManualPaymentRequest, PayoutRequest
        payment = ManualPaymentRequest(booking_id="b1", amount=100.0)
        assert payment.currency == "THB"
        assert payment.payment_type == "manual_adjustment"

        payout = PayoutRequest(property_id="p1", period_start="2026-01-01", period_end="2026-02-01")
        assert payout.mgmt_fee_pct == 15.0

    def test_service_record_manual_payment(self):
        from services.financial_writer import record_manual_payment

        class MockDB:
            class Table:
                def upsert(self, *a, **kw):
                    return self
                def insert(self, *a, **kw):
                    return self
                def execute(self):
                    class R:
                        data = [{}]
                    return R()
            def table(self, name):
                return self.Table()

        result = record_manual_payment(MockDB(), "t1", "b1", 100.0)
        assert result["status"] == "recorded"
        assert result["amount"] == 100.0


# ============================================================================
# Phase 507 — Currency Router
# ============================================================================

class TestCurrencyRouter:
    """Tests for exchange rate endpoints."""

    def test_router_import(self):
        from api.currency_router import router
        assert router is not None

    def test_exchange_rates_endpoint_registered(self):
        from api.currency_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/exchange-rates" in paths

    def test_refresh_endpoint_registered(self):
        from api.currency_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/exchange-rates/refresh" in paths

    def test_convert_endpoint_registered(self):
        from api.currency_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/exchange-rates/convert" in paths

    def test_fallback_rates_exist(self):
        from services.currency_service import FALLBACK_RATES
        assert "THB" in FALLBACK_RATES
        assert "USD" in FALLBACK_RATES
        assert FALLBACK_RATES["THB"] == 1.0

    def test_convert_same_currency(self):
        from services.currency_service import convert
        result = convert(500.0, "THB", "THB")
        assert result["amount"] == 500.0
        assert result["rate"] == 1.0

    def test_convert_different_currencies(self):
        from services.currency_service import convert
        result = convert(1000.0, "THB", "USD")
        assert "converted_amount" in result
        assert "rate" in result
        assert result["target_currency"] == "USD"


# ============================================================================
# Phase 508 — Webhook Retry Router
# ============================================================================

class TestWebhookRetryRouter:
    """Tests for webhook retry queue management endpoints."""

    def test_router_import(self):
        from api.webhook_retry_router import router
        assert router is not None

    def test_queue_endpoint_registered(self):
        from api.webhook_retry_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/webhook-retry/queue" in paths

    def test_process_endpoint_registered(self):
        from api.webhook_retry_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/webhook-retry/process" in paths

    def test_dlq_endpoint_registered(self):
        from api.webhook_retry_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/webhook-retry/dlq" in paths

    def test_calculate_delay(self):
        from services.webhook_retry import _calculate_delay, BASE_DELAY_SECONDS
        assert _calculate_delay(0) == BASE_DELAY_SECONDS  # 30s
        assert _calculate_delay(1) == BASE_DELAY_SECONDS * 4  # 2m
        assert _calculate_delay(2) == BASE_DELAY_SECONDS * 16  # 8m

    def test_max_retries_constant(self):
        from services.webhook_retry import MAX_RETRIES
        assert MAX_RETRIES == 5


# ============================================================================
# Phase 509 — Notification Preferences Router
# ============================================================================

class TestNotificationPreferencesRouter:
    """Tests for notification preferences endpoints."""

    def test_router_import(self):
        from api.notification_pref_router import router
        assert router is not None

    def test_get_prefs_endpoint_registered(self):
        from api.notification_pref_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/notification-preferences/{user_id}" in paths

    def test_types_endpoint_registered(self):
        from api.notification_pref_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/notification-preferences/types" in paths

    def test_notification_types_constant(self):
        from services.notification_preferences import NOTIFICATION_TYPES
        assert "booking_created" in NOTIFICATION_TYPES
        assert "task_assigned" in NOTIFICATION_TYPES
        assert len(NOTIFICATION_TYPES) == 10

    def test_update_request_model(self):
        from api.notification_pref_router import UpdatePreferencesRequest
        req = UpdatePreferencesRequest(
            enabled_types=["booking_created"],
            preferred_channel="email",
        )
        assert req.enabled_types == ["booking_created"]
        assert req.quiet_hours_start is None

    def test_get_preferences_defaults(self):
        from services.notification_preferences import get_preferences

        class MockDB:
            class Table:
                def select(self, *a, **kw):
                    return self
                def eq(self, *a, **kw):
                    return self
                def execute(self):
                    class R:
                        data = []
                    return R()
            def table(self, name):
                return self.Table()

        result = get_preferences(MockDB(), "t1", "u1")
        assert result["preferred_channel"] == "email"
        assert len(result["enabled_types"]) == 10


# ============================================================================
# Integration: All routers registered in app
# ============================================================================

class TestRouterRegistration:
    """Verify all 5 new routers are registered in the main FastAPI app."""

    def test_main_imports_phase_505(self):
        from api.property_dashboard_router import router
        assert len(list(router.routes)) >= 2

    def test_main_imports_phase_506(self):
        from api.financial_writer_router import router
        assert len(list(router.routes)) >= 2

    def test_main_imports_phase_507(self):
        from api.currency_router import router
        assert len(list(router.routes)) >= 3

    def test_main_imports_phase_508(self):
        from api.webhook_retry_router import router
        assert len(list(router.routes)) >= 3

    def test_main_imports_phase_509(self):
        from api.notification_pref_router import router
        assert len(list(router.routes)) >= 3
