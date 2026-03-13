"""
Phases 490-494 — Block 2 Combined Tests

Phase 490: Guest Token Batch Issuance
Phase 491: Owner Portal Statement (service exists)
Phase 492: Outbound Sync Runner
Phase 493: Booking Writer (manual create, cancel, amend)
Phase 494: Task Writer Frontend (create, claim, status, notes)
"""
from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "test-123"}]
    )
    db.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"id": "test-123"}]
    )
    db.table.return_value.upsert.return_value.execute.return_value = MagicMock(
        data=[{"id": "test-123"}]
    )
    return db


# ---------------------------------------------------------------------------
# Phase 490: Guest Token Batch Tests
# ---------------------------------------------------------------------------

class TestGuestTokenBatch:

    @patch("services.guest_token_batch._get_db")
    def test_batch_dry_run(self, mock_get_db, monkeypatch):
        monkeypatch.setenv("IHOUSE_GUEST_TOKEN_SECRET", "test-secret-key-at-least-32-bytes-long")

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Profiles with email
        mock_profiles = MagicMock()
        mock_profiles.data = [
            {"booking_id": "bk1", "tenant_id": "t1", "guest_email": "a@test.com", "guest_phone": "", "guest_name": "A"},
            {"booking_id": "bk2", "tenant_id": "t1", "guest_email": "b@test.com", "guest_phone": "", "guest_name": "B"},
        ]

        # No existing tokens
        mock_tokens = MagicMock()
        mock_tokens.data = []

        def select_side_effect(*args, **kwargs):
            select_mock = MagicMock()
            eq_mock = MagicMock()
            eq_mock.execute.return_value = mock_profiles
            select_mock.eq.return_value = eq_mock
            return select_mock

        # Use side_effect to return different results per table
        call_count = [0]
        orig_table = mock_db.table

        def table_side_effect(name):
            call_count[0] += 1
            result = MagicMock()
            if name == "guest_profile":
                result.select.return_value.eq.return_value.execute.return_value = mock_profiles
            elif name == "guest_tokens":
                result.select.return_value.eq.return_value.execute.return_value = mock_tokens
            return result

        mock_db.table.side_effect = table_side_effect

        from services.guest_token_batch import batch_issue_tokens
        result = batch_issue_tokens(tenant_id="t1", dry_run=True)

        assert result["total_profiles"] == 2
        assert result["issued"] == 2
        assert result["dry_run"] is True


# ---------------------------------------------------------------------------
# Phase 492: Outbound Sync Runner Tests
# ---------------------------------------------------------------------------

class TestOutboundSyncRunner:

    def test_dispatch_sync_dry_run(self, monkeypatch):
        """Without API key, dispatch should return dry_run."""
        monkeypatch.delenv("IHOUSE_AIRBNB_API_KEY", raising=False)

        from services.outbound_sync_runner import _dispatch_sync
        result = _dispatch_sync("airbnb", "booking_update", {"booking_id": "bk1"})
        assert result["status"] == "dry_run"
        assert result["provider"] == "airbnb"

    def test_dispatch_sync_missing_adapter(self, monkeypatch):
        """Even with key, if adapter module doesn't exist → dry_run."""
        monkeypatch.setenv("IHOUSE_NONEXISTENT_API_KEY", "test-key")

        from services.outbound_sync_runner import _dispatch_sync
        result = _dispatch_sync("nonexistent", "booking_update", {})
        assert result["status"] == "dry_run"


# ---------------------------------------------------------------------------
# Phase 493: Booking Writer Tests
# ---------------------------------------------------------------------------

class TestBookingWriter:

    def test_create_manual_booking(self, mock_db):
        from services.booking_writer import create_manual_booking
        result = create_manual_booking(
            db=mock_db,
            tenant_id="t1",
            property_id="prop1",
            check_in="2026-05-01",
            check_out="2026-05-05",
            guest_name="John Doe",
            guest_email="john@test.com",
        )
        assert result is not None
        # Should have called event_log insert
        mock_db.table.assert_any_call("event_log")

    def test_cancel_booking(self, mock_db):
        from services.booking_writer import cancel_booking
        result = cancel_booking(
            db=mock_db,
            tenant_id="t1",
            booking_id="bk_123",
            reason="Guest requested",
        )
        assert result is not None
        mock_db.table.assert_any_call("event_log")

    def test_update_booking_dates(self, mock_db):
        from services.booking_writer import update_booking_dates
        result = update_booking_dates(
            db=mock_db,
            tenant_id="t1",
            booking_id="bk_123",
            check_in="2026-06-01",
            check_out="2026-06-05",
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Phase 494: Task Writer Frontend Tests
# ---------------------------------------------------------------------------

class TestTaskWriterFrontend:

    def test_create_task(self, mock_db):
        from services.task_writer_frontend import create_task
        result = create_task(
            db=mock_db,
            tenant_id="t1",
            kind="CLEANING",
            property_id="prop1",
            title="Clean unit 3A",
            priority="high",
        )
        assert result is not None
        mock_db.table.assert_any_call("tasks")

    def test_claim_task(self, mock_db):
        from services.task_writer_frontend import claim_task
        result = claim_task(
            db=mock_db,
            tenant_id="t1",
            task_id="task_abc",
            worker_id="worker1",
        )
        assert result is not None

    def test_update_task_status_valid(self, mock_db):
        from services.task_writer_frontend import update_task_status
        result = update_task_status(
            db=mock_db,
            tenant_id="t1",
            task_id="task_abc",
            new_status="completed",
        )
        assert "error" not in result or result.get("error") is None

    def test_update_task_status_invalid(self, mock_db):
        from services.task_writer_frontend import update_task_status
        result = update_task_status(
            db=mock_db,
            tenant_id="t1",
            task_id="task_abc",
            new_status="invalid_status",
        )
        assert "error" in result

    def test_add_task_note(self, mock_db):
        from services.task_writer_frontend import add_task_note
        result = add_task_note(
            db=mock_db,
            tenant_id="t1",
            task_id="task_abc",
            note_text="Completed cleaning, photos uploaded",
            author_id="worker1",
        )
        assert result is not None
