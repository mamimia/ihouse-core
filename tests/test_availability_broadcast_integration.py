"""
Phase 327 — Availability Broadcaster Integration Tests
=======================================================

Tests the broadcast_availability() orchestration pathway.

Group A: PROPERTY_ONBOARDED Mode
  ✓  Single booking, single channel → bookings_ok=1
  ✓  No active bookings → bookings_found=0, never raises
  ✓  No enabled channels → report is empty, never raises

Group B: CHANNEL_ADDED Mode
  ✓  Only the newly added channel is targeted
  ✓  Source provider excluded from outbound targets

Group C: Failure Isolation
  ✓  Executor error on one booking → bookings_failed=1, others unaffected
  ✓  DB error during bootstrap → report returned, never raises

Group D: BroadcastReport Shape
  ✓  serialise_broadcast_report produces JSON-safe dict
  ✓  results list contains per-booking outcomes
  ✓  bookings_found = len(active booking IDs)

CI-safe: all adapters injected, DB mocked, no network.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.outbound_availability_broadcaster import (
    broadcast_availability,
    BroadcastMode,
    BroadcastReport,
    serialise_broadcast_report,
)
from services.outbound_executor import ExecutionReport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_api_adapter(booking_id, property_id, provider, action):
    """Always succeeds."""
    return {"ok": True, "booking_id": booking_id, "provider": provider}


def _stub_ical_adapter(booking_id, property_id, provider, action):
    """Always succeeds."""
    return {"ok": True, "booking_id": booking_id, "provider": provider}


def _make_db(
    channels=None,
    registry=None,
    booking_ids=None,
):
    db = MagicMock()

    # property_channel_map query chain (eq x3 or eq x4 with target_provider)
    chans = channels or []
    db.table.return_value.select.return_value.eq.return_value\
        .eq.return_value.eq.return_value.execute.return_value.data = chans
    db.table.return_value.select.return_value.eq.return_value\
        .eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = chans

    # provider_capability_registry
    reg = registry or []
    db.table.return_value.select.return_value.execute.return_value.data = reg

    # booking_state — neq chain
    bids = [{"booking_id": bid} for bid in (booking_ids or [])]
    db.table.return_value.select.return_value.eq.return_value\
        .eq.return_value.neq.return_value.execute.return_value.data = bids

    return db


_AIRBNB_CHANNEL = {
    "provider": "airbnb",
    "external_id": "ext-001",
    "sync_mode": "api",
    "enabled": True,
}

_AIRBNB_REGISTRY = {
    "provider": "airbnb",
    "tier": "tier1",
    "supports_api_write": True,
    "supports_ical_push": False,
    "supports_ical_pull": False,
    "rate_limit_per_min": 60,
}


# ---------------------------------------------------------------------------
# Group A — PROPERTY_ONBOARDED Mode
# ---------------------------------------------------------------------------

class TestPropertyOnboardedMode:

    def test_single_booking_single_channel_ok(self):
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = [{"action": "sync", "provider": "airbnb"}]
            m_exec.return_value = ExecutionReport(
                booking_id="B-001", property_id="P-001", tenant_id="t-1",
                total_actions=1, ok_count=1, failed_count=0, skip_count=0, dry_run=False,
            )

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.PROPERTY_ONBOARDED,
                api_adapter=_stub_api_adapter,
            )

        assert report.bookings_found == 1
        assert report.bookings_ok == 1
        assert report.bookings_failed == 0

    def test_no_active_bookings_graceful(self):
        db = _make_db(channels=[_AIRBNB_CHANNEL], registry=[_AIRBNB_REGISTRY], booking_ids=[])
        report = broadcast_availability(
            db, tenant_id="t-1", property_id="P-001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert report.bookings_found == 0
        assert isinstance(report, BroadcastReport)

    def test_no_channels_graceful(self):
        db = _make_db(channels=[], booking_ids=["B-001"])
        report = broadcast_availability(
            db, tenant_id="t-1", property_id="P-001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert report.bookings_found == 0
        assert report.results == []


# ---------------------------------------------------------------------------
# Group B — CHANNEL_ADDED Mode
# ---------------------------------------------------------------------------

class TestChannelAddedMode:

    def test_channel_added_targets_new_provider(self):
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = [{"action": "sync", "provider": "airbnb"}]
            m_exec.return_value = ExecutionReport(
                booking_id="B-001", property_id="P-001", tenant_id="t-1",
                total_actions=1, ok_count=1, failed_count=0, skip_count=0, dry_run=False,
            )

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.CHANNEL_ADDED,
                target_provider="airbnb",
            )

        assert report.mode == BroadcastMode.CHANNEL_ADDED
        assert report.bookings_ok == 1

    def test_source_provider_excluded(self):
        """When source_provider == the only enabled channel → all channels excluded → no bookings synced."""
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001"],
        )
        report = broadcast_availability(
            db, tenant_id="t-1", property_id="P-001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
            source_provider="airbnb",  # same as the only channel → excluded
        )
        # After exclusion, channels is empty → early return
        assert report.bookings_found == 0
        assert report.results == []


# ---------------------------------------------------------------------------
# Group C — Failure Isolation
# ---------------------------------------------------------------------------

class TestFailureIsolation:

    def test_executor_error_counts_as_failed(self):
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = [{"action": "sync", "provider": "airbnb"}]
            m_exec.side_effect = Exception("executor crash")

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.PROPERTY_ONBOARDED,
            )

        assert report.bookings_failed == 1
        assert report.results[0].error is not None

    def test_db_bootstrap_error_never_raises(self):
        db = MagicMock()
        db.table.side_effect = Exception("DB down")
        report = broadcast_availability(
            db, tenant_id="t-1", property_id="P-001",
            mode=BroadcastMode.PROPERTY_ONBOARDED,
        )
        assert isinstance(report, BroadcastReport)
        assert report.bookings_found == 0


# ---------------------------------------------------------------------------
# Group D — BroadcastReport Shape
# ---------------------------------------------------------------------------

class TestBroadcastReportShape:

    def test_serialise_produces_json_safe_dict(self):
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = []
            m_exec.return_value = ExecutionReport(
                booking_id="B-001", property_id="P-001", tenant_id="t-1",
                total_actions=0, ok_count=0, failed_count=0, skip_count=1, dry_run=False,
            )

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.PROPERTY_ONBOARDED,
            )

        serialised = serialise_broadcast_report(report)
        for key in ("property_id", "mode", "bookings_found", "bookings_ok",
                    "bookings_failed", "bookings_skipped", "results"):
            assert key in serialised

    def test_results_has_per_booking_entries(self):
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001", "B-002"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = []
            m_exec.return_value = ExecutionReport(
                booking_id="B-001", property_id="P-001", tenant_id="t-1",
                total_actions=1, ok_count=1, failed_count=0, skip_count=0, dry_run=False,
            )

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.PROPERTY_ONBOARDED,
            )

        assert report.bookings_found == 2
        assert len(report.results) == 2

    def test_bookings_found_matches_active_ids(self):
        """bookings_found is always len(active_booking_ids) regardless of outcome."""
        db = _make_db(
            channels=[_AIRBNB_CHANNEL],
            registry=[_AIRBNB_REGISTRY],
            booking_ids=["B-001", "B-002", "B-003"],
        )
        with patch("services.outbound_availability_broadcaster.build_sync_plan") as m_plan, \
             patch("services.outbound_availability_broadcaster.execute_sync_plan") as m_exec:
            m_plan.return_value = []
            m_exec.return_value = ExecutionReport(
                booking_id="B-001", property_id="P-001", tenant_id="t-1",
                total_actions=1, ok_count=1, failed_count=0, skip_count=0, dry_run=False,
            )

            report = broadcast_availability(
                db, tenant_id="t-1", property_id="P-001",
                mode=BroadcastMode.PROPERTY_ONBOARDED,
            )

        assert report.bookings_found == 3
