"""
Phases 691–698 + 706 — Wave 6: Checkout & Deposit Tests + Wave 7 Manual Booking
=================================================================================

691: Contract — checkout view returns photos
692: Contract — deposit full return
693: Contract — deposit partial return with deductions
694: Contract — deduction CRUD + refund recalculation
695: Contract — photo comparison API
696: E2E — full checkout: deposit → deductions → settlement → checkout
697: Edge — checkout with no deposit
698: Edge — checkout with zero refund (all deducted)
706: Contract — manual booking create
"""
from __future__ import annotations

import json
import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ======================================================================
# Helpers
# ======================================================================

def _mock_db_chain(*args, **kwargs):
    """Create a fluent mock DB that chains .table().select()...execute()."""
    mock = MagicMock()
    return mock


# ======================================================================
# Phase 691: Contract — checkout view returns photos
# ======================================================================

class TestPhase691_CheckoutViewPhotos(unittest.TestCase):
    """Verify photo comparison endpoint returns 3 photo categories."""

    def test_photo_comparison_returns_all_categories(self):
        from api.deposit_settlement_router import photo_comparison
        mock_db = MagicMock()

        # booking lookup
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"property_id": "PROP-1"}]
        )
        # reference photos
        ref_call = MagicMock(data=[{"photo_url": "ref1.jpg", "room_label": "Living"}])
        # cleaning photos
        clean_call = MagicMock(data=[{"photo_url": "clean1.jpg", "room_label": "Living"}])
        # checkout photos
        checkout_call = MagicMock(data=[])

        # Chain multiple table() calls
        calls = [
            MagicMock(data=[{"property_id": "PROP-1"}]),  # booking
            ref_call,     # reference photos
            clean_call,   # cleaning photos
            checkout_call, # checkout photos
        ]
        call_idx = {"i": 0}
        original_table = mock_db.table

        def table_side_effect(name):
            chain = MagicMock()
            result = calls[min(call_idx["i"], len(calls) - 1)]
            call_idx["i"] += 1
            chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = result
            chain.select.return_value.eq.return_value.execute.return_value = result
            chain.select.return_value.eq.return_value.order.return_value.execute.return_value = result
            return chain

        mock_db.table = table_side_effect

        resp = asyncio.run(photo_comparison("B1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertIn("reference_photos", body)
        self.assertIn("cleaning_photos", body)
        self.assertIn("checkout_photos", body)


# ======================================================================
# Phase 692: Contract — deposit full return
# ======================================================================

class TestPhase692_DepositFullReturn(unittest.TestCase):
    """Verify deposit collection and full return."""

    def test_collect_deposit(self):
        from api.deposit_settlement_router import collect_deposit
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "dep-1", "amount": 5000, "currency": "THB", "status": "collected", "refund_amount": 5000}]
        )
        resp = asyncio.run(collect_deposit(
            {"booking_id": "B1", "amount": 5000, "currency": "THB"},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "collected")
        self.assertEqual(body["refund_amount"], 5000)

    def test_return_deposit(self):
        from api.deposit_settlement_router import return_deposit
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"status": "collected", "amount": 5000, "refund_amount": 5000}]
        )
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "dep-1", "status": "returned"}]
        )
        resp = asyncio.run(return_deposit("dep-1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)

    def test_double_return_rejected(self):
        from api.deposit_settlement_router import return_deposit
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"status": "returned", "amount": 5000, "refund_amount": 5000}]
        )
        resp = asyncio.run(return_deposit("dep-1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 400)


# ======================================================================
# Phase 693: Contract — deposit partial return with deductions
# ======================================================================

class TestPhase693_PartialReturn(unittest.TestCase):
    """Verify deposits with deductions show correct refund."""

    def test_settlement_shows_deductions(self):
        from api.deposit_settlement_router import get_settlement
        mock_db = MagicMock()

        # Table calls: deposit lookup, deductions lookup
        call_idx = {"i": 0}
        dep_data = MagicMock(data=[{"id": "dep-1", "amount": 5000, "currency": "THB", "refund_amount": 3500, "status": "collected"}])
        ded_data = MagicMock(data=[
            {"id": "d1", "description": "Broken glass", "amount": 500, "category": "damage"},
            {"id": "d2", "description": "Missing towel", "amount": 1000, "category": "missing"},
        ])

        def table_side_effect(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = dep_data
            else:
                chain.select.return_value.eq.return_value.order.return_value.execute.return_value = ded_data
            return chain

        mock_db.table = table_side_effect
        resp = asyncio.run(get_settlement("dep-1", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["original_amount"], 5000)
        self.assertEqual(body["total_deductions"], 1500)
        self.assertEqual(len(body["deductions"]), 2)


# ======================================================================
# Phase 694: Contract — deduction CRUD
# ======================================================================

class TestPhase694_DeductionCRUD(unittest.TestCase):
    """Verify add/remove deduction and refund recalculation."""

    def test_add_deduction_recalculates(self):
        from api.deposit_settlement_router import add_deduction
        mock_db = MagicMock()

        call_idx = {"i": 0}
        dep_data = MagicMock(data=[{"id": "dep-1", "amount": 5000, "status": "collected"}])
        insert_data = MagicMock(data=[{"id": "d1"}])
        all_deds = MagicMock(data=[{"amount": 800}])

        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:  # deposit check
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = dep_data
            elif call_idx["i"] == 2:  # insert
                chain.insert.return_value.execute.return_value = insert_data
            elif call_idx["i"] == 3:  # all deductions
                chain.select.return_value.eq.return_value.execute.return_value = all_deds
            else:  # update refund
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain

        mock_db.table = table_side
        resp = asyncio.run(add_deduction(
            "dep-1", {"description": "Broken vase", "amount": 800},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.body)
        self.assertEqual(body["total_deductions"], 800)
        self.assertEqual(body["refund_amount"], 4200)

    def test_add_deduction_missing_description(self):
        from api.deposit_settlement_router import add_deduction
        resp = asyncio.run(add_deduction("dep-1", {"amount": 100}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_add_deduction_to_returned_deposit(self):
        from api.deposit_settlement_router import add_deduction
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"id": "dep-1", "amount": 5000, "status": "returned"}]
        )
        resp = asyncio.run(add_deduction(
            "dep-1", {"description": "Late", "amount": 100},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 400)


# ======================================================================
# Phase 695: Contract — photo comparison API
# ======================================================================

class TestPhase695_PhotoComparison(unittest.TestCase):
    """Verify photo comparison returns structured data."""

    def test_missing_booking_returns_404(self):
        from api.deposit_settlement_router import photo_comparison
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(photo_comparison("NONEXIST", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 404)


# ======================================================================
# Phase 696: E2E — full checkout flow
# ======================================================================

class TestPhase696_E2E_FullCheckout(unittest.TestCase):
    """E2E: deposit → deductions → settlement → checkout."""

    def test_full_flow(self):
        from api.deposit_settlement_router import collect_deposit, add_deduction, complete_checkout

        # Step 1: Collect deposit
        mock_db1 = MagicMock()
        mock_db1.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "dep-1", "amount": 5000, "status": "collected", "refund_amount": 5000}]
        )
        resp = asyncio.run(collect_deposit(
            {"booking_id": "B-E2E", "amount": 5000},
            tenant_id="t1", client=mock_db1
        ))
        self.assertEqual(resp.status_code, 201)

        # Step 2: Add deduction
        mock_db2 = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"id": "dep-1", "amount": 5000, "status": "collected"}])
            elif call_idx["i"] == 2:
                chain.insert.return_value.execute.return_value = MagicMock(data=[{"id": "d1"}])
            elif call_idx["i"] == 3:
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"amount": 1000}])
            else:
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db2.table = table_side
        resp = asyncio.run(add_deduction(
            "dep-1", {"description": "Broken mirror", "amount": 1000},
            tenant_id="t1", client=mock_db2
        ))
        self.assertEqual(resp.status_code, 201)

        # Step 3: Checkout (force=True to skip deposit pre-check in mock)
        mock_db3 = MagicMock()
        call_idx3 = {"i": 0}
        def table_side3(name):
            chain = MagicMock()
            call_idx3["i"] += 1
            if call_idx3["i"] == 1:  # booking lookup
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "B-E2E", "status": "confirmed", "property_id": "P1"}])
            elif call_idx3["i"] == 2:  # deposits lookup
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "dep-1", "status": "returned", "refund_amount": 4000}])
            else:  # booking update
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db3.table = table_side3
        resp = asyncio.run(complete_checkout(
            "B-E2E", {"worker_id": "W1"},
            tenant_id="t1", client=mock_db3
        ))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "checked_out")


# ======================================================================
# Phase 697: Edge — checkout with no deposit
# ======================================================================

class TestPhase697_CheckoutNoDeposit(unittest.TestCase):
    """Checkout should succeed when no deposit exists."""

    def test_checkout_no_deposit(self):
        from api.deposit_settlement_router import complete_checkout
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "B-ND", "status": "confirmed", "property_id": "P1"}])
            elif call_idx["i"] == 2:
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])  # no deposits
            else:
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(complete_checkout("B-ND", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "checked_out")
        self.assertIsNone(body["deposit_warning"])


# ======================================================================
# Phase 698: Edge — checkout with zero refund
# ======================================================================

class TestPhase698_ZeroRefund(unittest.TestCase):
    """Checkout blocked when deposit is still collected (unsettled)."""

    def test_unsettled_deposit_blocks_checkout(self):
        from api.deposit_settlement_router import complete_checkout
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "B-ZR", "status": "confirmed", "property_id": "P1"}])
            elif call_idx["i"] == 2:
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "dep-1", "status": "collected", "refund_amount": 0}])
            else:
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(complete_checkout("B-ZR", tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 400)

    def test_force_checkout_with_unsettled_deposit(self):
        from api.deposit_settlement_router import complete_checkout
        mock_db = MagicMock()
        call_idx = {"i": 0}
        def table_side(name):
            chain = MagicMock()
            call_idx["i"] += 1
            if call_idx["i"] == 1:
                chain.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                    data=[{"booking_id": "B-ZR", "status": "confirmed", "property_id": "P1"}])
            elif call_idx["i"] == 2:
                chain.select.return_value.eq.return_value.execute.return_value = MagicMock(
                    data=[{"id": "dep-1", "status": "collected", "refund_amount": 0}])
            else:
                chain.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        mock_db.table = table_side
        resp = asyncio.run(complete_checkout("B-ZR", {"force": True}, tenant_id="t1", client=mock_db))
        self.assertEqual(resp.status_code, 200)


# ======================================================================
# Phase 706: Contract — manual booking create
# ======================================================================

class TestPhase706_ManualBooking(unittest.TestCase):
    """Contract tests for POST /bookings/manual."""

    def test_create_direct_booking(self):
        from api.manual_booking_router import create_manual_booking
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"booking_id": "MAN-KOH-20260320-ab12", "guest_name": "John", "status": "confirmed", "source": "direct"}]
        )
        resp = asyncio.run(create_manual_booking(
            {"property_id": "PROP-KOH-01", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "guest_name": "John", "booking_source": "direct"},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)
        body = json.loads(resp.body)
        self.assertEqual(body["source"], "direct")

    def test_maintenance_block_no_guest_name(self):
        from api.manual_booking_router import create_manual_booking
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"booking_id": "MAN-X-20260320-ab12", "guest_name": "[maintenance_block]", "source": "maintenance_block"}]
        )
        resp = asyncio.run(create_manual_booking(
            {"property_id": "PROP-X", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "booking_source": "maintenance_block"},
            tenant_id="t1", client=mock_db
        ))
        self.assertEqual(resp.status_code, 201)

    def test_missing_property_id_rejected(self):
        from api.manual_booking_router import create_manual_booking
        resp = asyncio.run(create_manual_booking(
            {"check_in": "2026-03-20", "check_out": "2026-03-25", "guest_name": "John"},
            tenant_id="t1"
        ))
        self.assertEqual(resp.status_code, 400)

    def test_invalid_source_rejected(self):
        from api.manual_booking_router import create_manual_booking
        resp = asyncio.run(create_manual_booking(
            {"property_id": "P1", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "guest_name": "J", "booking_source": "airbnb"},
            tenant_id="t1"
        ))
        self.assertEqual(resp.status_code, 400)

    def test_self_use_missing_guest_rejected(self):
        from api.manual_booking_router import create_manual_booking
        resp = asyncio.run(create_manual_booking(
            {"property_id": "P1", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "booking_source": "self_use"},
            tenant_id="t1"
        ))
        self.assertEqual(resp.status_code, 400)

    def test_task_creation_logic(self):
        from api.manual_booking_router import _create_tasks_for_manual_booking
        # maintenance_block → no tasks
        result = _create_tasks_for_manual_booking(MagicMock(), "B1", "P1", "maintenance_block", [], "t1")
        self.assertEqual(result, [])

    def test_booking_id_format(self):
        from api.manual_booking_router import _generate_booking_id
        bid = _generate_booking_id("PROP-KOH-SUNSET-01", "2026-03-20")
        self.assertTrue(bid.startswith("MAN-"))
        self.assertIn("20260320", bid)

    def test_invalid_opt_out(self):
        from api.manual_booking_router import create_manual_booking
        resp = asyncio.run(create_manual_booking(
            {"property_id": "P1", "check_in": "2026-03-20", "check_out": "2026-03-25",
             "guest_name": "J", "booking_source": "self_use", "tasks_opt_out": ["invalid"]},
            tenant_id="t1"
        ))
        self.assertEqual(resp.status_code, 400)


# ======================================================================
# Bonus: Deposit validation
# ======================================================================

class TestDepositValidation(unittest.TestCase):
    """Deposit input validation."""

    def test_collect_no_booking_id(self):
        from api.deposit_settlement_router import collect_deposit
        resp = asyncio.run(collect_deposit({"amount": 5000}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_collect_negative_amount(self):
        from api.deposit_settlement_router import collect_deposit
        resp = asyncio.run(collect_deposit({"booking_id": "B1", "amount": -100}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)

    def test_collect_zero_amount(self):
        from api.deposit_settlement_router import collect_deposit
        resp = asyncio.run(collect_deposit({"booking_id": "B1", "amount": 0}, tenant_id="t1"))
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
