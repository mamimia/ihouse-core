"""
Phase 303 — Contract tests for seed_owner_portal.py
=====================================================

Tests the deterministic data generation (no live DB required).
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")


class TestGenerateBookings:
    def test_returns_20_bookings(self):
        from scripts.seed_owner_portal import _generate_bookings
        bookings = _generate_bookings(count=20, seed=42)
        assert len(bookings) == 20

    def test_deterministic_same_seed(self):
        from scripts.seed_owner_portal import _generate_bookings
        b1 = _generate_bookings(count=10, seed=99)
        b2 = _generate_bookings(count=10, seed=99)
        assert b1 == b2

    def test_different_seeds_differ(self):
        from scripts.seed_owner_portal import _generate_bookings
        b1 = _generate_bookings(count=10, seed=1)
        b2 = _generate_bookings(count=10, seed=2)
        assert b1 != b2

    def test_booking_fields_present(self):
        from scripts.seed_owner_portal import _generate_bookings
        bookings = _generate_bookings(count=1)
        b = bookings[0]
        for key in ("booking_id", "tenant_id", "property_id", "booking_ref",
                     "check_in_date", "check_out_date", "status", "source",
                     "guest_name", "total_price", "currency"):
            assert key in b, f"Missing key: {key}"

    def test_statuses_are_valid(self):
        from scripts.seed_owner_portal import _generate_bookings
        valid = {"confirmed", "checked_in", "checked_out", "cancelled"}
        for b in _generate_bookings(count=20):
            assert b["status"] in valid

    def test_checkout_after_checkin(self):
        from scripts.seed_owner_portal import _generate_bookings
        for b in _generate_bookings(count=20):
            assert b["check_out_date"] > b["check_in_date"]

    def test_tenant_id_fixed(self):
        from scripts.seed_owner_portal import _generate_bookings, TENANT_ID
        for b in _generate_bookings(count=5):
            assert b["tenant_id"] == TENANT_ID


class TestGenerateFinancialFacts:
    def test_excludes_cancelled(self):
        from scripts.seed_owner_portal import _generate_bookings, _generate_financial_facts
        bookings = _generate_bookings(count=20)
        facts = _generate_financial_facts(bookings)
        cancelled = [b for b in bookings if b["status"] == "cancelled"]
        assert len(facts) == len(bookings) - len(cancelled)

    def test_fact_fields_present(self):
        from scripts.seed_owner_portal import _generate_bookings, _generate_financial_facts
        bookings = _generate_bookings(count=5)
        facts = _generate_financial_facts(bookings)
        if facts:
            f = facts[0]
            for key in ("booking_id", "tenant_id", "gross_revenue",
                         "net_to_property", "management_fee", "ota_commission"):
                assert key in f

    def test_net_less_than_gross(self):
        from scripts.seed_owner_portal import _generate_bookings, _generate_financial_facts
        bookings = _generate_bookings(count=20)
        for f in _generate_financial_facts(bookings):
            assert f["net_to_property"] <= f["gross_revenue"]

    def test_management_fee_positive(self):
        from scripts.seed_owner_portal import _generate_bookings, _generate_financial_facts
        bookings = _generate_bookings(count=20)
        for f in _generate_financial_facts(bookings):
            assert f["management_fee"] >= 0


class TestGenerateOwnerPortalAccess:
    def test_generates_3_rows(self):
        from scripts.seed_owner_portal import _generate_owner_portal_access
        rows = _generate_owner_portal_access()
        assert len(rows) == 3

    def test_all_roles_owner(self):
        from scripts.seed_owner_portal import _generate_owner_portal_access
        for r in _generate_owner_portal_access():
            assert r["role"] == "owner"


class TestSeedDryRun:
    def test_dry_run_returns_summary(self):
        from scripts.seed_owner_portal import seed_to_supabase
        result = seed_to_supabase(dry_run=True)
        assert result["dry_run"] is True
        assert result["bookings_generated"] == 20
        assert result["facts_generated"] > 0
        assert result["access_rows_generated"] == 3
