"""
Phase 238 — Ctrip / Trip.com Enhanced Adapter — Contract Tests

Coverage (15 tests):

Helper functions:
  1. romanize_guest_name — ASCII name used directly
  2. romanize_guest_name — Chinese-only → "Guest (汉字)"
  3. romanize_guest_name — both present → ASCII wins
  4. romanize_guest_name — both empty → fallback
  5. default_cny_currency — CNY returned when empty
  6. default_cny_currency — THB preserved
  7. resolve_ctrip_cancel_reason — NC → no_charge
  8. resolve_ctrip_cancel_reason — FC → full_charge
  9. resolve_ctrip_cancel_reason — PC → partial_charge
  10. resolve_ctrip_cancel_reason — unknown code → ctrip_code_XX

Booking identity:
  11. CTRIP- prefix stripped
  12. TC- prefix stripped (legacy)

Registry:
  13. "ctrip" alias resolves to TripComAdapter

Adapter integration:
  14. normalize() uses booking_ref (not order_id) when both present
  15. normalize() falls back to order_id when booking_ref absent
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestRomanizeGuestName:
    def test_ascii_name_used_directly(self):
        from adapters.ota.tripcom import romanize_guest_name
        assert romanize_guest_name(guest_name="John Doe") == "John Doe"

    def test_chinese_only_wrapped(self):
        from adapters.ota.tripcom import romanize_guest_name
        result = romanize_guest_name(guest_name_cn="张三")
        assert result == "Guest (张三)"

    def test_both_present_ascii_wins(self):
        from adapters.ota.tripcom import romanize_guest_name
        result = romanize_guest_name(guest_name="John Doe", guest_name_cn="张三")
        assert result == "John Doe"

    def test_both_empty_fallback(self):
        from adapters.ota.tripcom import romanize_guest_name
        assert romanize_guest_name() == "Guest"

    def test_chinese_ascii_used_directly(self):
        """If guest_name_cn contains ASCII, it's treated as romanized."""
        from adapters.ota.tripcom import romanize_guest_name
        result = romanize_guest_name(guest_name_cn="Zhang San")
        assert result == "Zhang San"


class TestDefaultCnyCurrency:
    def test_empty_returns_cny(self):
        from adapters.ota.tripcom import default_cny_currency
        assert default_cny_currency(None) == "CNY"
        assert default_cny_currency("") == "CNY"

    def test_thb_preserved(self):
        from adapters.ota.tripcom import default_cny_currency
        assert default_cny_currency("THB") == "THB"


class TestResolveCtripCancelReason:
    def test_nc_no_charge(self):
        from adapters.ota.tripcom import resolve_ctrip_cancel_reason
        assert resolve_ctrip_cancel_reason("NC") == "no_charge"

    def test_fc_full_charge(self):
        from adapters.ota.tripcom import resolve_ctrip_cancel_reason
        assert resolve_ctrip_cancel_reason("FC") == "full_charge"

    def test_pc_partial_charge(self):
        from adapters.ota.tripcom import resolve_ctrip_cancel_reason
        assert resolve_ctrip_cancel_reason("PC") == "partial_charge"

    def test_unknown_code(self):
        from adapters.ota.tripcom import resolve_ctrip_cancel_reason
        assert resolve_ctrip_cancel_reason("XX") == "ctrip_code_XX"


# ---------------------------------------------------------------------------
# Booking identity — prefix stripping
# ---------------------------------------------------------------------------

class TestBookingIdentityPrefixes:
    def test_ctrip_prefix_stripped(self):
        from adapters.ota.booking_identity import normalize_reservation_ref
        result = normalize_reservation_ref("tripcom", "CTRIP-CN-20260301-001")
        assert result == "cn-20260301-001"

    def test_tc_prefix_stripped(self):
        from adapters.ota.booking_identity import normalize_reservation_ref
        result = normalize_reservation_ref("tripcom", "TC-12345")
        assert result == "12345"


# ---------------------------------------------------------------------------
# Registry — ctrip alias
# ---------------------------------------------------------------------------

class TestRegistryCtripAlias:
    def test_ctrip_alias_in_registry(self):
        from adapters.ota.registry import get_adapter
        from adapters.ota.tripcom import TripComAdapter
        adapter = get_adapter("ctrip")
        assert isinstance(adapter, TripComAdapter)


# ---------------------------------------------------------------------------
# Adapter integration — normalize() field resolution
# ---------------------------------------------------------------------------

class TestAdapterNormalize:
    def _make_payload(self, **overrides) -> dict:
        base = {
            "event_id": "evt-001",
            "hotel_id": "hotel-001",
            "occurred_at": "2026-03-11T12:00:00",
            "event_type": "BOOKING_CREATED",
            "tenant_id": "tenant-test",
            "order_id": "TC-LEGACY-001",
            "booking_ref": "CTRIP-CN-20260301-001",
        }
        base.update(overrides)
        return base

    def test_booking_ref_preferred_over_order_id(self):
        from adapters.ota.tripcom import TripComAdapter
        adapter = TripComAdapter()
        payload = self._make_payload()
        result = adapter.normalize(payload)
        # booking_ref "CTRIP-CN-20260301-001" stripped → "cn-20260301-001"
        assert result.reservation_id == "cn-20260301-001"

    def test_order_id_fallback_when_no_booking_ref(self):
        from adapters.ota.tripcom import TripComAdapter
        adapter = TripComAdapter()
        payload = self._make_payload()
        del payload["booking_ref"]
        result = adapter.normalize(payload)
        # order_id "TC-LEGACY-001" stripped → "legacy-001"
        assert result.reservation_id == "legacy-001"
