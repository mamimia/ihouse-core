"""
Tests for Phases 515-519 — Contract Tests Block + Job Runner API

Phase 515: Booking Writer + Task Writer Frontend contract tests
Phase 516: Job Runner Management API + contract tests
Phase 517: Guest Feedback + Financial Reconciler contract tests
Phase 518: LLM Service + Property Dashboard contract tests
Phase 519: Webhook Retry + Currency + Notification Preferences contract tests
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("IHOUSE_JWT_SECRET", "test-secret-key-for-jwt")
os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-guest-token-secret")
os.environ.setdefault("IHOUSE_ACCESS_TOKEN_SECRET", "test-access-token-secret")


# ===========================================================================
# Shared mock DB
# ===========================================================================

class MockTable:
    """Mock Supabase table that chains methods and returns empty results."""
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return self
        return method

    def execute(self):
        class R:
            data = []
            count = 0
        return R()


class MockDB:
    def table(self, name):
        return MockTable()


# ===========================================================================
# Phase 515 — Booking Writer Contract Tests
# ===========================================================================

class TestBookingWriterContracts:
    """Contract tests for booking_writer.py mutations."""

    def test_create_manual_booking_returns_booking(self):
        from services.booking_writer import create_manual_booking
        result = create_manual_booking(
            MockDB(), "t1", "p1",
            check_in="2026-04-01", check_out="2026-04-05",
            guest_name="John", source="manual",
        )
        assert result["property_id"] == "p1"
        assert result["status"] == "active"
        assert result["booking_id"].startswith("manual_")

    def test_cancel_booking_returns_canceled(self):
        from services.booking_writer import cancel_booking
        result = cancel_booking(MockDB(), "t1", "booking_abc")
        assert result["booking_id"] == "booking_abc"
        assert result["status"] == "canceled"

    def test_update_booking_dates_returns_booking_id(self):
        from services.booking_writer import update_booking_dates
        result = update_booking_dates(MockDB(), "t1", "b1", "2026-05-01", "2026-05-05")
        assert result["booking_id"] == "b1"

    def test_create_manual_booking_generates_event(self):
        """Verify that event_log.insert is called when creating."""
        calls = []
        class TrackingTable:
            def __init__(self, name):
                self.name = name
            def __getattr__(self, k):
                def method(*a, **kw):
                    return self
                return method
            def insert(self, data):
                calls.append((self.name, data.get("kind", data.get("status", ""))))
                return self
            def execute(self):
                class R:
                    data = [{}]
                return R()

        class TrackingDB:
            def table(self, name):
                return TrackingTable(name)

        from services.booking_writer import create_manual_booking
        create_manual_booking(TrackingDB(), "t1", "p1", "2026-04-01", "2026-04-05")
        table_names = [c[0] for c in calls]
        assert "event_log" in table_names
        assert "booking_state" in table_names


# ===========================================================================
# Phase 516 — Job Runner Management API Contract Tests
# ===========================================================================

class TestJobRunnerContracts:
    """Contract tests for job_runner.py and its API router."""

    def test_jobs_constant_has_all_jobs(self):
        from services.job_runner import JOBS
        expected = {"pre_arrival_scan", "conflict_scan", "sla_escalation", "token_cleanup", "financial_recon"}
        assert set(JOBS.keys()) == expected

    def test_each_job_has_interval(self):
        from services.job_runner import JOBS
        for name, defn in JOBS.items():
            assert "interval_hours" in defn, f"Missing interval_hours for {name}"
            assert defn["interval_hours"] > 0

    def test_each_job_has_description(self):
        from services.job_runner import JOBS
        for name, defn in JOBS.items():
            assert "description" in defn
            assert len(defn["description"]) > 10

    def test_router_import(self):
        from api.job_runner_router import router
        assert router is not None

    def test_router_endpoints_registered(self):
        from api.job_runner_router import router
        paths = [r.path for r in router.routes]
        assert "/admin/jobs/status" in paths
        assert "/admin/jobs/trigger" in paths
        assert "/admin/jobs/history" in paths

    def test_trigger_request_model(self):
        from api.job_runner_router import TriggerJobsRequest
        req = TriggerJobsRequest(dry_run=True)
        assert req.dry_run is True
        assert req.force is False
        assert req.jobs is None


# ===========================================================================
# Phase 517 — Guest Feedback + Financial Reconciler Contract Tests
# ===========================================================================

class TestGuestFeedbackContracts:
    """Contract tests for guest_feedback.py."""

    def test_submit_feedback_validates_rating_range(self):
        from services.guest_feedback import submit_feedback
        result = submit_feedback(MockDB(), "b1", rating=0)
        assert "error" in result
        result = submit_feedback(MockDB(), "b1", rating=6)
        assert "error" in result

    def test_submit_feedback_accepts_valid_rating(self):
        from services.guest_feedback import submit_feedback
        result = submit_feedback(MockDB(), "b1", rating=4, tenant_id="t1", property_id="p1")
        assert "error" not in result or result.get("status") == "submitted"

    def test_property_feedback_summary_empty(self):
        from services.guest_feedback import get_property_feedback_summary
        result = get_property_feedback_summary(MockDB(), "p1", "t1")
        assert result["total_reviews"] == 0
        assert result["average_rating"] == 0.0
        assert "distribution" in result


class TestFinancialReconcilerContracts:
    """Contract tests for financial_reconciler.py."""

    def test_run_reconciliation_returns_expected_shape(self):
        from services.financial_reconciler import run_reconciliation
        result = run_reconciliation(db=MockDB())
        assert result["status"] == "completed"
        assert "total_bookings" in result
        assert "total_with_facts" in result
        assert "coverage_pct" in result
        assert "by_provider" in result

    def test_run_reconciliation_coverage_is_percentage(self):
        from services.financial_reconciler import run_reconciliation
        result = run_reconciliation(db=MockDB())
        assert 0 <= result["coverage_pct"] <= 100


# ===========================================================================
# Phase 518 — LLM Service + Property Dashboard Contract Tests
# ===========================================================================

class TestLLMServiceContracts:
    """Contract tests for llm_service.py."""

    def test_generate_guest_message_template_fallback(self):
        """Without OpenAI key, should fall back to template."""
        # Ensure no key is set
        os.environ.pop("IHOUSE_OPENAI_API_KEY", None)
        from services.llm_service import generate_guest_message
        result = generate_guest_message("welcome", {"guest_name": "Alice", "property_name": "Sunset Villa"})
        assert result["source"] == "template"
        assert "Alice" in result["message"]
        assert "Sunset Villa" in result["message"]

    def test_generate_guest_message_check_in_template(self):
        os.environ.pop("IHOUSE_OPENAI_API_KEY", None)
        from services.llm_service import generate_guest_message
        result = generate_guest_message("check_in_instructions", {"guest_name": "Bob"})
        assert "Bob" in result["message"]
        assert result["source"] == "template"

    def test_generate_operational_suggestion_fallback(self):
        os.environ.pop("IHOUSE_OPENAI_API_KEY", None)
        from services.llm_service import generate_operational_suggestion
        result = generate_operational_suggestion("conflict_resolution", {})
        assert result["source"] == "template"
        assert len(result["suggestion"]) > 10

    def test_generate_operational_suggestion_unknown_type(self):
        os.environ.pop("IHOUSE_OPENAI_API_KEY", None)
        from services.llm_service import generate_operational_suggestion
        result = generate_operational_suggestion("unknown_type", {})
        assert result["source"] == "template"
        assert "unknown_type" in result["suggestion"]


class TestPropertyDashboardContracts:
    """Contract tests for property_dashboard.py."""

    def test_get_property_dashboard_structure(self):
        from services.property_dashboard import get_property_dashboard
        result = get_property_dashboard(MockDB(), "t1", "p1")
        assert result["property_id"] == "p1"
        assert result["tenant_id"] == "t1"
        for key in ("occupancy", "revenue", "tasks", "upcoming", "feedback"):
            assert key in result

    def test_get_portfolio_overview_structure(self):
        from services.property_dashboard import get_portfolio_overview
        result = get_portfolio_overview(MockDB(), "t1")
        assert result["tenant_id"] == "t1"
        assert "total_properties" in result
        assert "total_bookings" in result
        assert "open_tasks" in result


# ===========================================================================
# Phase 519 — Webhook Retry + Currency + Notification Pref Contract Tests
# ===========================================================================

class TestWebhookRetryContracts:
    """Contract tests for webhook_retry.py."""

    def test_enqueue_retry_under_max(self):
        from services.webhook_retry import enqueue_retry
        result = enqueue_retry(MockDB(), "t1", "http://example.com", {"a": 1}, "BOOKING_CREATED", attempt=0)
        assert result["status"] == "queued"
        assert result["attempt"] == 1

    def test_enqueue_retry_at_max_moves_to_dlq(self):
        from services.webhook_retry import enqueue_retry, MAX_RETRIES
        result = enqueue_retry(MockDB(), "t1", "http://example.com", {}, "BOOKING_CREATED", attempt=MAX_RETRIES)
        assert result["status"] == "moved_to_dlq"

    def test_delay_increases_exponentially(self):
        from services.webhook_retry import _calculate_delay
        delays = [_calculate_delay(i) for i in range(5)]
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1]


class TestCurrencyServiceContracts:
    """Contract tests for currency_service.py."""

    def test_convert_same_currency_identity(self):
        from services.currency_service import convert
        result = convert(123.45, "USD", "USD")
        assert result["amount"] == 123.45
        assert result["rate"] == 1.0

    def test_convert_thb_to_usd(self):
        from services.currency_service import convert, FALLBACK_RATES
        result = convert(1000, "THB", "USD")
        assert result["converted_amount"] == round(1000 * FALLBACK_RATES["USD"], 2)

    def test_fallback_rates_thb_is_one(self):
        from services.currency_service import FALLBACK_RATES
        assert FALLBACK_RATES["THB"] == 1.0


class TestNotificationPreferencesContracts:
    """Contract tests for notification_preferences.py."""

    def test_get_preferences_returns_defaults(self):
        from services.notification_preferences import get_preferences
        result = get_preferences(MockDB(), "t1", "u1")
        assert result["preferred_channel"] == "email"
        assert len(result["enabled_types"]) == 10

    def test_update_invalid_channel_returns_error(self):
        from services.notification_preferences import update_preferences
        result = update_preferences(MockDB(), "t1", "u1", preferred_channel="carrier_pigeon")
        assert "error" in result

    def test_update_invalid_notification_type_returns_error(self):
        from services.notification_preferences import update_preferences
        result = update_preferences(MockDB(), "t1", "u1", enabled_types=["nonexistent_type"])
        assert "error" in result

    def test_should_notify_default_is_true(self):
        from services.notification_preferences import should_notify
        result = should_notify(MockDB(), "t1", "u1", "booking_created")
        assert result is True
