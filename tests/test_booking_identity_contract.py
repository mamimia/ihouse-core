"""
Phase 68 — Contract tests for booking_identity.py

Verifies:
1. Base normalization: strip + lowercase
2. Per-provider prefix stripping (bookingcom BK-, agoda AG-/AGD-, tripcom TC-)
3. Providers with no extra rules pass through after base normalization
4. build_booking_id applies normalization and uses the locked formula
5. Determinism: same input → same output
6. Empty / None-safe: empty string passes through
7. Unknown provider falls back to base normalization only
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# normalize_reservation_ref — base behaviour
# ---------------------------------------------------------------------------

class TestBaseNormalization:

    def test_strips_leading_whitespace(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "  RES001") == "res001"

    def test_strips_trailing_whitespace(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "RES001  ") == "res001"

    def test_strips_both_sides_whitespace(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("airbnb", "  RES001  ") == "res001"

    def test_lowercases_uppercase_ref(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("expedia", "RES12345") == "res12345"

    def test_empty_string_passthrough(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "") == ""

    def test_already_lowercase_no_change(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("airbnb", "res12345") == "res12345"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — Booking.com (BK- prefix)
# ---------------------------------------------------------------------------

class TestBookingComNormalization:

    def test_strips_uppercase_bk_prefix(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "BK-RES12345") == "res12345"

    def test_strips_lowercase_bk_prefix(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "bk-res12345") == "res12345"

    def test_strips_mixed_case_bk_prefix(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "BK-Res12345") == "res12345"

    def test_no_prefix_passthrough(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "RES12345") == "res12345"

    def test_with_surrounding_whitespace_and_prefix(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("bookingcom", "  BK-RES12345  ") == "res12345"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — Expedia (no extra rules)
# ---------------------------------------------------------------------------

class TestExpediaNormalization:

    def test_lowercases_and_strips(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("expedia", "  EXP0099  ") == "exp0099"

    def test_numeric_id_passthrough(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("expedia", "123456789") == "123456789"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — Airbnb (no extra rules)
# ---------------------------------------------------------------------------

class TestAirbnbNormalization:

    def test_lowercases_and_strips(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("airbnb", "  HMXXXXXXXXX  ") == "hmxxxxxxxxx"

    def test_numeric_id_passthrough(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("airbnb", "123456789") == "123456789"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — Agoda (AG- / AGD- prefix)
# ---------------------------------------------------------------------------

class TestAgodaNormalization:

    def test_strips_agd_prefix_uppercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("agoda", "AGD-98765") == "98765"

    def test_strips_ag_prefix_uppercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("agoda", "AG-98765") == "98765"

    def test_strips_agd_prefix_lowercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("agoda", "agd-98765") == "98765"

    def test_strips_ag_prefix_lowercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("agoda", "ag-98765") == "98765"

    def test_no_prefix_passthrough(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("agoda", "98765") == "98765"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — Trip.com (TC- prefix)
# ---------------------------------------------------------------------------

class TestTripComNormalization:

    def test_strips_tc_prefix_uppercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("tripcom", "TC-ORDER999") == "order999"

    def test_strips_tc_prefix_lowercase(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("tripcom", "tc-order999") == "order999"

    def test_numeric_order_id_no_prefix(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("tripcom", "ORDER999") == "order999"


# ---------------------------------------------------------------------------
# normalize_reservation_ref — unknown provider
# ---------------------------------------------------------------------------

class TestUnknownProvider:

    def test_unknown_provider_applies_base_only(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        assert normalize_reservation_ref("newprovider", "  BK-TEST  ") == "bk-test"

    def test_unknown_provider_no_prefix_stripped(self) -> None:
        """Unknown providers do NOT get prefix stripping — base only."""
        from adapters.ota.booking_identity import normalize_reservation_ref
        result = normalize_reservation_ref("newprovider", "BK-MYREF")
        # BK- should NOT be stripped for unknown providers
        assert result == "bk-myref"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_input_same_output_repeated(self) -> None:
        from adapters.ota.booking_identity import normalize_reservation_ref
        results = [normalize_reservation_ref("bookingcom", "  BK-RES001  ") for _ in range(10)]
        assert all(r == "res001" for r in results)

    def test_idempotent_double_call(self) -> None:
        """Calling normalize twice on already-normalized ref is a no-op."""
        from adapters.ota.booking_identity import normalize_reservation_ref
        once = normalize_reservation_ref("bookingcom", "BK-RES001")
        twice = normalize_reservation_ref("bookingcom", once)
        assert once == twice


# ---------------------------------------------------------------------------
# build_booking_id
# ---------------------------------------------------------------------------

class TestBuildBookingId:

    def test_applies_normalization_and_builds_id(self) -> None:
        from adapters.ota.booking_identity import build_booking_id
        assert build_booking_id("bookingcom", "BK-RES12345") == "bookingcom_res12345"

    def test_locked_formula_source_underscore_ref(self) -> None:
        from adapters.ota.booking_identity import build_booking_id
        result = build_booking_id("airbnb", "HM123456789")
        assert result == "airbnb_hm123456789"

    def test_all_providers_produce_stable_id(self) -> None:
        from adapters.ota.booking_identity import build_booking_id
        cases = [
            ("bookingcom", "  BK-RES001  ", "bookingcom_res001"),
            ("expedia",    "  EXP0099  ",   "expedia_exp0099"),
            ("airbnb",     "HM123",          "airbnb_hm123"),
            ("agoda",      "AGD-9876",       "agoda_9876"),
            ("tripcom",    "TC-ORDER1",      "tripcom_order1"),
        ]
        for provider, raw, expected in cases:
            assert build_booking_id(provider, raw) == expected, (
                f"Failed for {provider}: {raw!r} → expected {expected!r}"
            )
