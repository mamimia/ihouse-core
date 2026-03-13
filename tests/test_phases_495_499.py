"""
Phases 495-499 — Block 3 Combined Tests

Phase 495: Job Runner
Phase 496: Guest Feedback
Phase 497: Financial Reconciliation
Phase 498: LLM Service
Phase 499: Property Dashboard
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "test"}]
    )
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    return db


# ---------------------------------------------------------------------------
# Phase 495: Job Runner Tests
# ---------------------------------------------------------------------------

class TestJobRunner:

    def test_jobs_defined(self):
        from services.job_runner import JOBS
        assert "pre_arrival_scan" in JOBS
        assert "conflict_scan" in JOBS
        assert "sla_escalation" in JOBS
        assert "token_cleanup" in JOBS
        assert "financial_recon" in JOBS

    def test_job_intervals(self):
        from services.job_runner import JOBS
        assert JOBS["pre_arrival_scan"]["interval_hours"] == 6
        assert JOBS["sla_escalation"]["interval_hours"] == 0.25  # 15 min

    @patch("services.job_runner._get_db")
    def test_run_all_due_dry_run(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        # All jobs should return "not run before" → should_run = True
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        from services.job_runner import run_all_due_jobs
        result = run_all_due_jobs(dry_run=True, force=True)
        assert result["dry_run"] is True
        assert result["total_jobs"] == 5


# ---------------------------------------------------------------------------
# Phase 496: Guest Feedback Tests
# ---------------------------------------------------------------------------

class TestGuestFeedback:

    def test_submit_valid_feedback(self, mock_db):
        from services.guest_feedback import submit_feedback
        result = submit_feedback(
            db=mock_db,
            booking_id="bk_123",
            rating=5,
            comment="Great stay!",
            tenant_id="t1",
            property_id="prop1",
        )
        assert "error" not in result
        mock_db.table.assert_any_call("guest_feedback")

    def test_submit_invalid_rating(self, mock_db):
        from services.guest_feedback import submit_feedback
        result = submit_feedback(
            db=mock_db,
            booking_id="bk_123",
            rating=6,
            tenant_id="t1",
        )
        assert "error" in result

    def test_submit_zero_rating(self, mock_db):
        from services.guest_feedback import submit_feedback
        result = submit_feedback(
            db=mock_db,
            booking_id="bk_123",
            rating=0,
            tenant_id="t1",
        )
        assert "error" in result

    def test_feedback_summary_empty(self, mock_db):
        from services.guest_feedback import get_property_feedback_summary
        result = get_property_feedback_summary(mock_db, "prop1", "t1")
        assert result["total_reviews"] == 0
        assert result["average_rating"] == 0.0


# ---------------------------------------------------------------------------
# Phase 497: Financial Reconciliation Tests
# ---------------------------------------------------------------------------

class TestFinancialReconciler:

    @patch("services.financial_reconciler._get_db")
    def test_reconciliation_report(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # 3 bookings
        booking_mock = MagicMock()
        booking_mock.data = [
            {"booking_id": "bk1", "provider": "airbnb"},
            {"booking_id": "bk2", "provider": "airbnb"},
            {"booking_id": "bk3", "provider": "bookingcom"},
        ]
        booking_mock.count = 3

        # 2 financial facts (bk3 missing)
        facts_mock = MagicMock()
        facts_mock.data = [
            {"booking_id": "bk1", "provider": "airbnb", "total_gross": "100"},
            {"booking_id": "bk2", "provider": "airbnb", "total_gross": "200"},
        ]
        facts_mock.count = 2

        call_count = [0]
        def table_side_effect(name):
            call_count[0] += 1
            result = MagicMock()
            if name == "booking_state":
                result.select.return_value.execute.return_value = booking_mock
                result.select.return_value.eq.return_value.execute.return_value = booking_mock
            elif name == "booking_financial_facts":
                result.select.return_value.execute.return_value = facts_mock
                result.select.return_value.eq.return_value.execute.return_value = facts_mock
            return result

        mock_db.table.side_effect = table_side_effect

        from services.financial_reconciler import run_reconciliation
        result = run_reconciliation(db=mock_db)

        assert result["status"] == "completed"
        assert result["total_bookings"] == 3
        assert result["total_with_facts"] == 2
        assert result["missing_facts"] == 1


# ---------------------------------------------------------------------------
# Phase 498: LLM Service Tests
# ---------------------------------------------------------------------------

class TestLlmService:

    def test_guest_message_template_fallback(self, monkeypatch):
        """Without OpenAI key, should use template."""
        monkeypatch.delenv("IHOUSE_OPENAI_API_KEY", raising=False)

        from services.llm_service import generate_guest_message
        result = generate_guest_message(
            intent="check_in_instructions",
            context={"property_name": "Beach Villa", "guest_name": "Jane"},
        )
        assert result["source"] == "template"
        assert "Beach Villa" in result["message"]
        assert "Jane" in result["message"]

    def test_operational_suggestion_fallback(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_OPENAI_API_KEY", raising=False)

        from services.llm_service import generate_operational_suggestion
        result = generate_operational_suggestion(
            issue_type="conflict_resolution",
            context={},
        )
        assert result["source"] == "template"
        assert "guests" in result["suggestion"].lower()


# ---------------------------------------------------------------------------
# Phase 499: Property Dashboard Tests
# ---------------------------------------------------------------------------

class TestPropertyDashboard:

    def test_dashboard_sections(self, mock_db):
        # Make chained queries return empty results
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.order.return_value.execute.return_value = MagicMock(data=[])

        from services.property_dashboard import get_property_dashboard
        result = get_property_dashboard(mock_db, "t1", "prop1")

        assert "occupancy" in result
        assert "revenue" in result
        assert "tasks" in result
        assert "upcoming" in result
        assert "feedback" in result
