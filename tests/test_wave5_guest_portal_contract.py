"""
Phases 676–684 — Wave 5: Guest Portal & Extras Tests
=====================================================

676: Contract — enhanced portal data (Phase 666 fields)
677: Contract — extras listing for guest
678: Contract — order extra, manager confirm/deliver
679: Contract — guest chat send/receive
680: Contract — WhatsApp link generation
681: Contract — location + map
682: Contract — house info pages
683: E2E — full guest journey: QR → portal → view extras → order → chat
684: Edge — portal after checkout (read-only, no ordering)
"""
from __future__ import annotations

import hashlib
import sys
import os
import unittest
from dataclasses import asdict
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# =======================================================================
# Phase 676: Contract — Enhanced portal data (Phase 666 fields)
# =======================================================================

class TestPhase676_EnhancedPortalData(unittest.TestCase):
    """Verify GuestBookingView contains Phase 666 fields."""

    def test_guest_booking_view_has_extras(self):
        from services.guest_portal import GuestBookingView, ExtraItem
        item = ExtraItem(extra_id="x1", name="Pool", description="Private pool", icon="🏊", price=200.0)
        view = GuestBookingView(
            booking_ref="B1", property_name="P", property_address="A",
            check_in_date="2026-01-01", check_out_date="2026-01-05",
            check_in_time="15:00", check_out_time="11:00",
            status="confirmed", guest_name="G", nights=4,
            extras_available=[item], chat_enabled=True,
        )
        self.assertEqual(len(view.extras_available), 1)
        self.assertEqual(view.extras_available[0].name, "Pool")
        self.assertTrue(view.chat_enabled)

    def test_guest_booking_view_has_gps(self):
        from services.guest_portal import GuestBookingView
        view = GuestBookingView(
            booking_ref="B2", property_name="P", property_address="A",
            check_in_date="2026-01-01", check_out_date="2026-01-05",
            check_in_time="15:00", check_out_time="11:00",
            status="confirmed", guest_name="G", nights=4,
            property_latitude=9.5, property_longitude=100.0,
        )
        self.assertAlmostEqual(view.property_latitude, 9.5)
        self.assertAlmostEqual(view.property_longitude, 100.0)

    def test_guest_booking_view_house_info(self):
        from services.guest_portal import GuestBookingView
        view = GuestBookingView(
            booking_ref="B3", property_name="P", property_address="A",
            check_in_date="2026-01-01", check_out_date="2026-01-05",
            check_in_time="15:00", check_out_time="11:00",
            status="confirmed", guest_name="G", nights=4,
            ac_instructions="Set to 25°C",
            parking_info="Covered spot",
            pool_instructions="No glass near pool",
        )
        self.assertEqual(view.ac_instructions, "Set to 25°C")
        self.assertEqual(view.parking_info, "Covered spot")
        self.assertEqual(view.pool_instructions, "No glass near pool")
        self.assertIsNone(view.hot_water_info)

    def test_extra_item_defaults(self):
        from services.guest_portal import ExtraItem
        item = ExtraItem(extra_id="x1", name="N", description="D", icon="🎉", price=100.0)
        self.assertEqual(item.currency, "THB")
        self.assertEqual(item.category, "other")

    def test_stub_booking_has_phase_666_fields(self):
        from services.guest_portal import stub_lookup
        view = stub_lookup("DEMO-001")
        self.assertIsNotNone(view)
        self.assertTrue(view.chat_enabled)
        self.assertAlmostEqual(view.property_latitude, 9.5120)
        self.assertAlmostEqual(view.property_longitude, 100.0136)
        self.assertEqual(len(view.extras_available), 2)
        self.assertEqual(view.extras_available[0].name, "Motorbike Rental")

    def test_booking_to_dict_includes_phase_666(self):
        from api.guest_portal_router import _booking_to_dict
        from services.guest_portal import stub_lookup
        view = stub_lookup("DEMO-001")
        d = _booking_to_dict(view)
        self.assertTrue(d["chat_enabled"])
        self.assertIn("extras_available", d)
        self.assertEqual(len(d["extras_available"]), 2)


# =======================================================================
# Phase 677: Contract — Extras listing for guest
# =======================================================================

class TestPhase677_ExtrasListing(unittest.TestCase):
    """Contract tests for GET /guest/{token}/extras."""

    def test_token_invalid_returns_401(self):
        import asyncio
        from api.guest_extras_router import guest_extras_listing
        resp = asyncio.run(guest_extras_listing("INVALID-token"))
        self.assertEqual(resp.status_code, 401)

    def test_valid_token_queries_property_extras(self):
        import asyncio
        from api.guest_extras_router import guest_extras_listing
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"extra_id": "e1", "name": "Pool", "price": 200},
                {"extra_id": "e2", "name": "Massage", "price": 500},
            ]
        )
        resp = asyncio.run(guest_extras_listing("test-abc12345", client=mock_db))
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        self.assertEqual(body["count"], 2)


# =======================================================================
# Phase 678: Contract — Order extra, manager confirm
# =======================================================================

class TestPhase678_OrderExtra(unittest.TestCase):
    """Contract tests for POST /guest/{token}/extras/order and PATCH /extra-orders/{id}."""

    def test_order_missing_extra_id(self):
        import asyncio
        from api.guest_extras_router import guest_order_extra
        resp = asyncio.run(
            guest_order_extra("test-abc12345", {"quantity": 1})
        )
        self.assertEqual(resp.status_code, 400)

    def test_order_valid(self):
        import asyncio
        from api.guest_extras_router import guest_order_extra
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "ord-1", "extra_id": "e1", "status": "requested"}]
        )
        resp = asyncio.run(
            guest_order_extra("test-abc12345", {"extra_id": "e1", "quantity": 2}, client=mock_db)
        )
        self.assertEqual(resp.status_code, 201)
        import json
        body = json.loads(resp.body)
        self.assertEqual(body["status"], "requested")

    def test_manager_confirm_order(self):
        import asyncio
        from api.guest_extras_router import manager_update_order
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"status": "requested"}]
        )
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "ord-1", "status": "confirmed"}]
        )
        resp = asyncio.run(
            manager_update_order("ord-1", {"status": "confirmed"}, tenant_id="t1", client=mock_db)
        )
        self.assertEqual(resp.status_code, 200)

    def test_invalid_status_transition(self):
        import asyncio
        from api.guest_extras_router import manager_update_order
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"status": "delivered"}]
        )
        resp = asyncio.run(
            manager_update_order("ord-1", {"status": "requested"}, tenant_id="t1", client=mock_db)
        )
        self.assertEqual(resp.status_code, 400)

    def test_order_quantity_must_be_positive(self):
        import asyncio
        from api.guest_extras_router import guest_order_extra
        resp = asyncio.run(
            guest_order_extra("test-abc12345", {"extra_id": "e1", "quantity": 0})
        )
        self.assertEqual(resp.status_code, 400)


# =======================================================================
# Phase 679: Contract — Guest chat send/receive
# =======================================================================

class TestPhase679_GuestChat(unittest.TestCase):
    """Contract tests for POST/GET /guest/{token}/messages."""

    def test_send_message_success(self):
        import asyncio
        from api.guest_portal_router import guest_send_message
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "msg-1", "sender_type": "guest", "content": "Hello!"}]
        )
        resp = asyncio.run(
            guest_send_message("test-abc12345", {"content": "Hello!"}, client=mock_db)
        )
        self.assertEqual(resp.status_code, 201)

    def test_send_empty_message_rejected(self):
        import asyncio
        from api.guest_portal_router import guest_send_message
        resp = asyncio.run(
            guest_send_message("test-abc12345", {"content": ""})
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_messages(self):
        import asyncio
        from api.guest_portal_router import guest_get_messages
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "msg-1"}, {"id": "msg-2"}]
        )
        resp = asyncio.run(
            guest_get_messages("test-abc12345", client=mock_db)
        )
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        self.assertEqual(body["count"], 2)

    def test_invalid_token_rejects(self):
        import asyncio
        from api.guest_portal_router import guest_send_message
        resp = asyncio.run(
            guest_send_message("INVALID-token", {"content": "Hi"})
        )
        self.assertEqual(resp.status_code, 401)


# =======================================================================
# Phase 680: Contract — WhatsApp link generation
# =======================================================================

class TestPhase680_WhatsAppLink(unittest.TestCase):
    """Contract tests for GET /guest/{token}/contact."""

    def test_contact_returns_whatsapp_link(self):
        import asyncio
        from api.guest_portal_router import guest_contact
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"name": "Villa Sunset", "manager_phone": "+66800001234", "manager_email": "m@test.com", "manager_whatsapp": "+66800001234"}]
        )
        resp = asyncio.run(
            guest_contact("test-abc12345", client=mock_db)
        )
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        self.assertIn("wa.me", body["whatsapp_link"])
        self.assertIn("66800001234", body["whatsapp_link"])

    def test_contact_no_phone(self):
        import asyncio
        from api.guest_portal_router import guest_contact
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"name": "X", "manager_phone": None, "manager_email": "m@t.com", "manager_whatsapp": None}]
        )
        resp = asyncio.run(
            guest_contact("test-abc12345", client=mock_db)
        )
        import json
        body = json.loads(resp.body)
        self.assertIsNone(body["whatsapp_link"])


# =======================================================================
# Phase 681: Contract — Location + map
# =======================================================================

class TestPhase681_Location(unittest.TestCase):
    """Contract tests for GET /guest/{token}/location."""

    def test_location_returns_map_urls(self):
        import asyncio
        from api.guest_portal_router import guest_location
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"name": "V", "address": "123 Road", "latitude": 9.51, "longitude": 100.01}]
        )
        resp = asyncio.run(
            guest_location("test-abc12345", client=mock_db)
        )
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        self.assertIn("google.com/maps", body["map_url"])
        self.assertIn("google.com/maps/dir", body["directions_url"])
        self.assertAlmostEqual(body["latitude"], 9.51)

    def test_location_no_gps(self):
        import asyncio
        from api.guest_portal_router import guest_location
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"name": "V", "address": "X", "latitude": None, "longitude": None}]
        )
        resp = asyncio.run(
            guest_location("test-abc12345", client=mock_db)
        )
        import json
        body = json.loads(resp.body)
        self.assertIsNone(body["map_url"])


# =======================================================================
# Phase 682: Contract — House info pages
# =======================================================================

class TestPhase682_HouseInfo(unittest.TestCase):
    """Contract tests for GET /guest/{token}/house-info."""

    def test_house_info_filters_null(self):
        import asyncio
        from api.guest_portal_router import guest_house_info
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"ac_instructions": "Remote on table", "hot_water_info": None, "pool_instructions": "No glass", "parking_info": None,
                   "stove_instructions": None, "laundry_info": None, "tv_info": None, "emergency_contact": "+66 80", "extra_notes": None}]
        )
        resp = asyncio.run(
            guest_house_info("test-abc12345", client=mock_db)
        )
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        info = body["info"]
        self.assertEqual(info["ac_instructions"], "Remote on table")
        self.assertEqual(info["pool_instructions"], "No glass")
        self.assertNotIn("hot_water_info", info)
        self.assertNotIn("parking_info", info)

    def test_house_info_empty_property(self):
        import asyncio
        from api.guest_portal_router import guest_house_info
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        resp = asyncio.run(
            guest_house_info("test-abc12345", client=mock_db)
        )
        import json
        body = json.loads(resp.body)
        self.assertEqual(body["info"], {})


# =======================================================================
# Phase 683: E2E — Full guest journey
# =======================================================================

class TestPhase683_E2E_GuestJourney(unittest.TestCase):
    """E2E: QR → portal → view extras → order extra → chat."""

    def test_full_journey(self):
        import asyncio
        import json
        from api.guest_portal_router import (
            guest_send_message,
            guest_get_messages,
            guest_contact,
            guest_location,
            guest_house_info,
            guest_portal_i18n,
        )
        from api.guest_extras_router import guest_extras_listing, guest_order_extra

        token = "test-journey1"

        # Step 1: View extras
        mock_db_extras = MagicMock()
        mock_db_extras.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"extra_id": "e1", "name": "Massage", "price": 500}]
        )
        resp = asyncio.run(guest_extras_listing(token, client=mock_db_extras))
        self.assertEqual(resp.status_code, 200)

        # Step 2: Order the extra
        mock_db_order = MagicMock()
        mock_db_order.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "ord-1", "extra_id": "e1", "status": "requested"}]
        )
        resp = asyncio.run(
            guest_order_extra(token, {"extra_id": "e1", "quantity": 1}, client=mock_db_order)
        )
        self.assertEqual(resp.status_code, 201)

        # Step 3: Send chat message
        mock_db_chat = MagicMock()
        mock_db_chat.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "msg-1", "content": "I ordered a massage!", "sender_type": "guest"}]
        )
        resp = asyncio.run(
            guest_send_message(token, {"content": "I ordered a massage!"}, client=mock_db_chat)
        )
        self.assertEqual(resp.status_code, 201)

        # Step 4: Get messages
        mock_db_msgs = MagicMock()
        mock_db_msgs.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "msg-1"}]
        )
        resp = asyncio.run(guest_get_messages(token, client=mock_db_msgs))
        body = json.loads(resp.body)
        self.assertEqual(body["count"], 1)

        # Step 5: Check i18n
        resp = asyncio.run(guest_portal_i18n(token, lang="th"))
        body = json.loads(resp.body)
        self.assertEqual(body["lang"], "th")
        self.assertEqual(body["labels"]["welcome"], "ยินดีต้อนรับ")


# =======================================================================
# Phase 684: Edge — Portal after checkout (read-only)
# =======================================================================

class TestPhase684_PortalAfterCheckout(unittest.TestCase):
    """Edge case: portal access should still work after checkout."""

    def test_portal_i18n_works_with_any_status(self):
        import asyncio
        from api.guest_portal_router import guest_portal_i18n
        resp = asyncio.run(guest_portal_i18n("test-checkout1", lang="he"))
        self.assertEqual(resp.status_code, 200)
        import json
        body = json.loads(resp.body)
        self.assertEqual(body["labels"]["welcome"], "ברוכים הבאים")

    def test_order_state_transitions_enforce_terminal(self):
        """Delivered and canceled orders cannot transition further."""
        from api.guest_extras_router import _VALID_ORDER_TRANSITIONS
        self.assertEqual(len(_VALID_ORDER_TRANSITIONS["delivered"]), 0)
        self.assertEqual(len(_VALID_ORDER_TRANSITIONS["canceled"]), 0)

    def test_extras_listing_invalid_token(self):
        import asyncio
        from api.guest_extras_router import guest_extras_listing
        resp = asyncio.run(guest_extras_listing("INVALID"))
        self.assertEqual(resp.status_code, 401)


# =======================================================================
# Bonus: I18n label completeness
# =======================================================================

class TestPortalI18nLabels(unittest.TestCase):
    """Verify all languages have the same keys."""

    def test_all_languages_have_same_keys(self):
        from api.guest_portal_router import _get_portal_labels
        en_keys = set(_get_portal_labels("en").keys())
        th_keys = set(_get_portal_labels("th").keys())
        he_keys = set(_get_portal_labels("he").keys())
        self.assertEqual(en_keys, th_keys)
        self.assertEqual(en_keys, he_keys)

    def test_unsupported_lang_falls_back_to_english(self):
        from api.guest_portal_router import _get_portal_labels
        labels = _get_portal_labels("xx")
        self.assertEqual(labels["welcome"], "Welcome")

    def test_12_portal_labels(self):
        from api.guest_portal_router import _get_portal_labels
        self.assertEqual(len(_get_portal_labels("en")), 12)


if __name__ == "__main__":
    unittest.main()
