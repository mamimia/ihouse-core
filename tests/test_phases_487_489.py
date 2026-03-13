"""
Phases 487-489 — Combined Tests

Phase 487: Conflict Scanner
Phase 488: Pre-Arrival Scanner (existing service + new endpoint)
Phase 489: Task Template Seeder
"""
from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Phase 487: Conflict Scanner Tests
# ---------------------------------------------------------------------------

class TestConflictScanner:
    """Test scan_property_conflicts pure function."""

    def test_no_overlaps(self):
        from services.conflict_scanner import scan_property_conflicts
        bookings = [
            {"booking_id": "bk1", "check_in": "2026-04-01", "check_out": "2026-04-05", "status": "ACTIVE"},
            {"booking_id": "bk2", "check_in": "2026-04-05", "check_out": "2026-04-10", "status": "ACTIVE"},
        ]
        result = scan_property_conflicts(bookings, "prop1")
        assert len(result) == 0

    def test_detects_overlap(self):
        from services.conflict_scanner import scan_property_conflicts
        bookings = [
            {"booking_id": "bk1", "check_in": "2026-04-01", "check_out": "2026-04-05", "status": "ACTIVE"},
            {"booking_id": "bk2", "check_in": "2026-04-03", "check_out": "2026-04-10", "status": "ACTIVE"},
        ]
        result = scan_property_conflicts(bookings, "prop1")
        assert len(result) == 1
        assert result[0]["overlap_days"] == 2

    def test_skips_canceled_bookings(self):
        from services.conflict_scanner import scan_property_conflicts
        bookings = [
            {"booking_id": "bk1", "check_in": "2026-04-01", "check_out": "2026-04-05", "status": "ACTIVE"},
            {"booking_id": "bk2", "check_in": "2026-04-03", "check_out": "2026-04-10", "status": "CANCELED"},
        ]
        result = scan_property_conflicts(bookings, "prop1")
        assert len(result) == 0

    def test_deterministic_conflict_id(self):
        from services.conflict_scanner import _conflict_id
        id1 = _conflict_id("bk_a", "bk_b", "prop1")
        id2 = _conflict_id("bk_b", "bk_a", "prop1")
        assert id1 == id2  # order-independent

    def test_multiple_overlaps(self):
        from services.conflict_scanner import scan_property_conflicts
        bookings = [
            {"booking_id": "bk1", "check_in": "2026-04-01", "check_out": "2026-04-10", "status": "ACTIVE"},
            {"booking_id": "bk2", "check_in": "2026-04-03", "check_out": "2026-04-07", "status": "ACTIVE"},
            {"booking_id": "bk3", "check_in": "2026-04-05", "check_out": "2026-04-12", "status": "ACTIVE"},
        ]
        result = scan_property_conflicts(bookings, "prop1")
        assert len(result) == 3  # bk1-bk2, bk1-bk3, bk2-bk3


# ---------------------------------------------------------------------------
# Phase 489: Task Template Seeder Tests
# ---------------------------------------------------------------------------

class TestTaskTemplateSeeder:
    """Test seed_default_templates with mocked Supabase."""

    @patch("services.task_template_seeder._get_db")
    def test_seed_dry_run(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # No existing templates
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        from services.task_template_seeder import seed_default_templates, DEFAULT_TEMPLATES
        result = seed_default_templates(tenant_id="t1", dry_run=True)

        assert result["total_templates"] == len(DEFAULT_TEMPLATES)
        assert result["created"] == len(DEFAULT_TEMPLATES)
        assert result["dry_run"] is True

    @patch("services.task_template_seeder._get_db")
    def test_seed_skips_existing(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Simulate 2 existing templates
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"kind": "CLEANING"}, {"kind": "CHECKIN_PREP"}]
        )

        from services.task_template_seeder import seed_default_templates, DEFAULT_TEMPLATES
        result = seed_default_templates(tenant_id="t1", dry_run=True)

        assert result["skipped_existing"] == 2
        assert result["created"] == len(DEFAULT_TEMPLATES) - 2

    def test_default_templates_have_required_fields(self):
        from services.task_template_seeder import DEFAULT_TEMPLATES
        for template in DEFAULT_TEMPLATES:
            assert "title" in template
            assert "kind" in template
            assert "priority" in template
            assert template["priority"] in ("critical", "high", "normal", "low")
