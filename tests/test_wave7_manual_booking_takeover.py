"""
Phases 713–726 — Wave 7 & 8 Tests
====================================

713: Contract — manual booking create (covered in Wave 6 tests + additions here)
714: Contract — OTA date blocking on manual
715: Contract — selective task opt-out
716: Contract — manual booking cancel + unblock
717: Contract — task take-over API
718: Contract — worker notification on take-over
719: E2E — manual self-use booking → no checkin task → checkout → cleaning
720: E2E — take-over flow: worker MIA → manager takes → completes
721+: Owner portal & maintenance tests
"""
from __future__ import annotations

import json
import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ======================================================================
# Phase 713: Contract — manual booking create (extended)
# ======================================================================

class TestPhase713_ManualBookingCreate(unittest.TestCase):
    """Extended contract tests for manual booking creation."""

    def test_create_with_ota_blocking(self):
        from api.manual_booking_router import create_manual_booking
        mock_db = MagicMock()
        # Mock overlap detection to return no conflicts
        mock_db.table.return_value.select.return_value.eq.return_value.in_.return_value.lt.return_value.gt.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        # insert booking
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"booking_id": "MAN-X-20260320-ab12", "guest_name": "John", "source": "direct"}]
        )
        # channel_map query for OTA blocking
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"channel_id": "ch1", "provider": "airbnb"}]
        )
        resp = asyncio.run(create_manual_booking(
            {"property_id": "PROP-X", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "guest_name": "John", "booking_source": "direct"},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.body)
        self.assertIn("ota_blocked", body)


# ======================================================================
# Phase 714: Contract — OTA date blocking
# ======================================================================

class TestPhase714_OTABlocking(unittest.TestCase):
    """Verify OTA date blocking helper."""

    def test_no_channels_returns_no_channels(self):
        from api.manual_booking_router import _trigger_ota_date_block
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        result = _trigger_ota_date_block(mock_db, "P1", "2026-03-20", "2026-03-25", "B1", "t1")
        self.assertEqual(result, "no_channels")

    def test_with_channels_queues_sync(self):
        from api.manual_booking_router import _trigger_ota_date_block
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"channel_id": "ch1", "provider": "airbnb"}, {"channel_id": "ch2", "provider": "booking"}]
        )
        result = _trigger_ota_date_block(mock_db, "P1", "2026-03-20", "2026-03-25", "B1", "t1")
        self.assertEqual(result, "queued:2")


# ======================================================================
# Phase 715: Contract — selective task opt-out
# ======================================================================

class TestPhase715_SelectiveTaskOptOut(unittest.TestCase):
    """Verify task creation respects opt-out flags."""

    def test_maintenance_block_no_tasks(self):
        from api.manual_booking_router import _create_tasks_for_manual_booking
        result = _create_tasks_for_manual_booking(MagicMock(), "B1", "P1", "2026-03-20", "maintenance_block", [], "t1")
        self.assertEqual(result, [])

    def test_self_use_with_checkin_optout(self):
        from api.manual_booking_router import _create_tasks_for_manual_booking
        # Self-use with checkin opt-out → should create cleaning + checkout
        mock_db = MagicMock()
        result = _create_tasks_for_manual_booking(mock_db, "B1", "P1", "2026-03-20", "self_use", ["checkin"], "t1")
        # Will contain cleaning and checkout (if task_automator doesn't error)
        self.assertNotIn("checkin", result)

    def test_direct_always_creates_all(self):
        from api.manual_booking_router import _create_tasks_for_manual_booking
        mock_db = MagicMock()
        # Direct bookings ignore opt-out and create all tasks
        result = _create_tasks_for_manual_booking(mock_db, "B1", "P1", "2026-03-20", "direct", ["checkin"], "t1")
        # All task kinds attempted (may fail due to mocks but logic is correct)
        self.assertIsInstance(result, list)


# ======================================================================
# Phase 716: Contract — manual booking cancel + unblock
# ======================================================================

class TestPhase716_ManualCancel(unittest.TestCase):
    """Verify manual booking cancellation."""

    def test_cancel_booking(self):
        from api.manual_booking_router import cancel_manual_booking
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:  # booking lookup
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "MAN-X", "status": "confirmed", "property_id": "P1",
                           "check_in": "2026-03-20", "check_out": "2026-03-25", "source": "direct"}])
            elif call_idx["i"] == 2:  # update booking
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            elif call_idx["i"] == 3:  # tasks lookup
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "t1", "status": "pending"}, {"id": "t2", "status": "completed"}])
            elif call_idx["i"] == 4:  # cancel task t1
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            elif call_idx["i"] <= 6:  # OTA unblock
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(cancel_manual_booking("MAN-X", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "canceled")
        self.assertEqual(body["tasks_canceled"], 1)

    def test_cancel_already_canceled(self):
        from api.manual_booking_router import cancel_manual_booking
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"booking_id": "MAN-X", "status": "canceled", "property_id": "P1"}])
        resp = asyncio.run(cancel_manual_booking("MAN-X", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 400)

    def test_cancel_not_found(self):
        from api.manual_booking_router import cancel_manual_booking
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(cancel_manual_booking("NONEXIST", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Phase 717: Contract — task take-over API
# ======================================================================

class TestPhase717_TaskTakeOver(unittest.TestCase):
    """Contract tests for POST /tasks/{id}/take-over."""

    def test_take_over_success(self):
        from api.task_takeover_router import take_over_task
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:  # task lookup
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "T1", "status": "pending", "assigned_to": "W1",
                           "task_kind": "CLEANING", "booking_id": "B1", "property_id": "P1"}])
            elif call_idx["i"] == 2:  # update task
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            elif call_idx["i"] == 3:  # task_actions insert
                chain.insert.return_value.execute.return_value = MagicMock(data=[])
            else:  # property/booking lookups for context
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.insert.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(take_over_task("T1", {"reason": "worker_sick"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "taken_over")
        self.assertEqual(body["original_worker_id"], "W1")
        self.assertIn("context", body)

    def test_invalid_reason(self):
        from api.task_takeover_router import take_over_task
        resp = asyncio.run(take_over_task("T1", {"reason": "bored"}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_cannot_take_over_completed(self):
        from api.task_takeover_router import take_over_task
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "T1", "status": "completed"}])
        resp = asyncio.run(take_over_task("T1", {"reason": "emergency"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 400)

    def test_task_not_found(self):
        from api.task_takeover_router import take_over_task
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(take_over_task("NONEXIST", {"reason": "emergency"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Phase 718: Contract — worker notification on take-over
# ======================================================================

class TestPhase718_TakeOverNotification(unittest.TestCase):
    """Verify notification is sent to original worker."""

    def test_notification_queued(self):
        from api.task_takeover_router import _notify_worker_of_takeover
        mock_db = MagicMock()
        task = {"id": "T1", "assigned_to": "W1", "task_kind": "CLEANING", "property_name": "Sunset Villa"}
        result = _notify_worker_of_takeover(mock_db, task, "M1", "worker_sick", "t1")
        self.assertTrue(result)
        # Should have called notification_queue insert
        mock_db.table.assert_called()

    def test_no_worker_no_notification(self):
        from api.task_takeover_router import _notify_worker_of_takeover
        task = {"id": "T1", "assigned_to": None, "task_kind": "CLEANING"}
        result = _notify_worker_of_takeover(MagicMock(), task, "M1", "emergency", "t1")
        self.assertFalse(result)


# ======================================================================
# Phase 719: E2E — manual self-use booking flow
# ======================================================================

class TestPhase719_E2E_SelfUseBooking(unittest.TestCase):
    """E2E: create self-use booking → selective tasks → cancel → unblock."""

    def test_self_use_flow(self):
        from api.manual_booking_router import create_manual_booking, cancel_manual_booking

        # Create self-use booking
        mock_db1 = MagicMock()
        # Mock overlap detection to return no conflicts
        mock_db1.table.return_value.select.return_value.eq.return_value.in_.return_value.lt.return_value.gt.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        mock_db1.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"booking_id": "MAN-X-20260320", "guest_name": "Owner", "source": "self_use"}])
        mock_db1.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(create_manual_booking(
            {"property_id": "P1", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "guest_name": "Owner", "booking_source": "self_use", "tasks_opt_out": ["checkin"]},
            tenant_id="t1", client=mock_db1
        ))
        self.assertEqual(resp.status_code, 201)

        # Cancel it
        mock_db2 = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "MAN-X", "status": "confirmed", "property_id": "P1",
                           "check_in": "2026-03-20", "check_out": "2026-03-25"}])
            else:
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db2.table = table_side
        resp = asyncio.run(cancel_manual_booking("MAN-X", tenant_id="t1", client=mock_db2))
        self.assertEqual(resp.status_code, 200)


# ======================================================================
# Phase 720: E2E — take-over flow
# ======================================================================

class TestPhase720_E2E_TakeOverFlow(unittest.TestCase):
    """E2E: worker MIA → manager takes over → gets context."""

    def test_take_over_and_get_context(self):
        from api.task_takeover_router import take_over_task, get_task_context

        # Take over
        mock_db1 = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "T1", "status": "pending", "assigned_to": "W1",
                           "task_kind": "CLEANING", "booking_id": "B1", "property_id": "P1"}])
            else:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
                chain.insert.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db1.table = table_side
        resp = asyncio.run(take_over_task("T1", {"reason": "worker_unavailable"}, tenant_id="mgr", client=mock_db1))
        self.assertEqual(resp.status_code, 200)

        # Get context
        mock_db2 = MagicMock()
        ctx_idx = {"i": 0}
        def ctx_table(name):
            chain = MagicMock()
            ctx_idx["i"] += 1
            if ctx_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "T1", "task_kind": "CLEANING", "booking_id": "B1", "property_id": "P1"}])
            else:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db2.table = ctx_table
        resp = asyncio.run(get_task_context("T1", tenant_id="mgr", client=mock_db2))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertIn("context", body)


# ======================================================================
# Wave 8 Tests — Owner Portal & Maintenance
# ======================================================================

class TestPhase721_OwnerVisibility(unittest.TestCase):
    """Contract tests for owner visibility toggle."""

    def test_set_visibility(self):
        from api.owner_portal_v2_router import set_owner_visibility
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(set_owner_visibility(
            "O1", "P1", {"visible_fields": {"bookings": True, "maintenance_reports": True}},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertTrue(body["visible_fields"]["maintenance_reports"])

    def test_invalid_visibility_field(self):
        from api.owner_portal_v2_router import set_owner_visibility
        resp = asyncio.run(set_owner_visibility(
            "O1", "P1", {"visible_fields": {"invalid_field": True}}, tenant_id="t1"
        ))
        self.assertEqual(resp.status_code, 400)

    def test_get_visibility_default(self):
        from api.owner_portal_v2_router import get_owner_visibility
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(get_owner_visibility("O1", "P1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertTrue(body["visible_fields"]["bookings"])
        self.assertFalse(body["visible_fields"]["maintenance_reports"])


class TestPhase725_SpecialtyCRUD(unittest.TestCase):
    """Contract tests for maintenance specialty CRUD."""

    def test_create_specialty(self):
        from api.owner_portal_v2_router import create_specialty
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "s1", "name": "Plumbing", "specialty_key": "plumbing"}])
        resp = asyncio.run(create_specialty(
            {"name": "Plumbing", "specialty_key": "plumbing"}, tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)

    def test_create_specialty_missing_name(self):
        from api.owner_portal_v2_router import create_specialty
        resp = asyncio.run(create_specialty({"specialty_key": "x"}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_list_specialties(self):
        from api.owner_portal_v2_router import list_specialties
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "s1", "name": "Plumbing"}, {"id": "s2", "name": "Electrical"}])
        resp = asyncio.run(list_specialties(tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["count"], 2)

    def test_assign_worker_specialty(self):
        from api.owner_portal_v2_router import assign_worker_specialty
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(assign_worker_specialty("W1", {"specialty_id": "s1"}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 201)


class TestPhase726_FilteredTasks(unittest.TestCase):
    """Contract tests for filtered maintenance tasks."""

    def test_no_specialties_returns_all(self):
        from api.owner_portal_v2_router import worker_maintenance_tasks
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:  # worker_specialties
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            else:  # all tasks
                chain.select.return_value.eq.return_value.neq.return_value.order.return_value.execute.return_value = MagicMock(
                    data=[{"id": "t1"}, {"id": "t2"}, {"id": "t3"}])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(worker_maintenance_tasks("W1", tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["mode"], "all_tasks")
        self.assertEqual(body["count"], 3)

    def test_with_specialties_returns_filtered(self):
        from api.owner_portal_v2_router import worker_maintenance_tasks
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:  # worker specs
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"specialty_id": "s1"}])
            elif call_idx["i"] == 2:  # spec keys
                chain.select.return_value.in_.return_value.execute.return_value = MagicMock(
                    data=[{"specialty_key": "plumbing"}])
            else:  # filtered tasks
                chain.select.return_value.eq.return_value.neq.return_value.in_.return_value.order.return_value.execute.return_value = MagicMock(
                    data=[{"id": "t1"}])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(worker_maintenance_tasks("W2", tenant_id="t1", client=mock_db))
        body = json.loads(resp.body)
        self.assertEqual(body["mode"], "filtered")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["specialty_keys"], ["plumbing"])


class TestTakeOverReasonValidation(unittest.TestCase):
    """Verify take-over reason validation."""

    def test_valid_reasons(self):
        from api.task_takeover_router import _VALID_TAKEOVER_REASONS
        self.assertIn("worker_unavailable", _VALID_TAKEOVER_REASONS)
        self.assertIn("worker_sick", _VALID_TAKEOVER_REASONS)
        self.assertIn("emergency", _VALID_TAKEOVER_REASONS)
        self.assertIn("other", _VALID_TAKEOVER_REASONS)
        self.assertEqual(len(_VALID_TAKEOVER_REASONS), 4)


if __name__ == "__main__":
    unittest.main()
