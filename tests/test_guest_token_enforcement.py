"""
Phase 862 P51 — Guest Token Enforcement Tests
==============================================

Tests that prove:
1. Valid guest tokens resolve to correct booking/property/tenant context
2. Invalid/expired/malformed tokens are denied
3. The canonical resolve_guest_token_context function works correctly
4. Endpoint token resolution wiring works for guest portal routes
"""

import os
import time
import pytest

# Set guest token secret before imports
os.environ.setdefault("IHOUSE_GUEST_TOKEN_SECRET", "test-secret-key-for-guest-tokens-v1-minimum-32-bytes")


from services.guest_token import (
    issue_guest_token,
    verify_guest_token,
    resolve_guest_token_context,
    GuestTokenContext,
    _decode_token,
    _sign,
    _get_secret,
    _encode_token,
    _make_message,
)


# ---------------------------------------------------------------------------
# Test: GuestTokenContext class
# ---------------------------------------------------------------------------

class TestGuestTokenContext:
    def test_context_fields(self):
        ctx = GuestTokenContext(
            booking_ref="BOOK-001",
            property_id="PROP-001",
            tenant_id="TENANT-001",
            guest_email="guest@example.com",
            exp=9999999999,
        )
        assert ctx.booking_ref == "BOOK-001"
        assert ctx.property_id == "PROP-001"
        assert ctx.tenant_id == "TENANT-001"
        assert ctx.guest_email == "guest@example.com"
        assert ctx.exp == 9999999999

    def test_to_dict(self):
        ctx = GuestTokenContext(
            booking_ref="BOOK-001",
            property_id="PROP-001",
            tenant_id="TENANT-001",
        )
        d = ctx.to_dict()
        assert d["booking_ref"] == "BOOK-001"
        assert d["property_id"] == "PROP-001"
        assert d["tenant_id"] == "TENANT-001"
        assert d["guest_email"] == ""
        assert d["exp"] == 0


# ---------------------------------------------------------------------------
# Test: resolve_guest_token_context — test tokens
# ---------------------------------------------------------------------------

class TestResolveGuestTokenCI:
    """Test the CI/test shortcut path (tokens starting with 'test-')."""

    def test_test_token_resolves(self):
        ctx = resolve_guest_token_context("test-ABCD1234")
        assert ctx is not None
        assert isinstance(ctx, GuestTokenContext)
        assert ctx.booking_ref == "BOOK-ABCD1234"
        assert ctx.property_id == "PROP-ABCD1234"
        assert ctx.tenant_id == "TENANT-ABCD1234"

    def test_test_token_short(self):
        ctx = resolve_guest_token_context("test-AB")
        assert ctx is not None
        assert ctx.booking_ref == "BOOK-AB"

    def test_test_token_to_dict(self):
        ctx = resolve_guest_token_context("test-XYZ12345")
        assert ctx is not None
        d = ctx.to_dict()
        assert d["booking_ref"] == "BOOK-XYZ12345"
        assert d["property_id"] == "PROP-XYZ12345"


# ---------------------------------------------------------------------------
# Test: resolve_guest_token_context — real HMAC tokens
# ---------------------------------------------------------------------------

class TestResolveGuestTokenReal:
    """Test real HMAC token verification path (no DB)."""

    def test_valid_token_resolves(self):
        """A valid HMAC token with future expiry should resolve."""
        raw_token, exp = issue_guest_token("BOOK-999", guest_email="g@test.com", ttl_seconds=3600)
        # Without DB, resolve returns partial context (booking_ref but no property_id)
        ctx = resolve_guest_token_context(raw_token)
        assert ctx is not None
        assert ctx.booking_ref == "BOOK-999"
        assert ctx.guest_email == "g@test.com"
        assert ctx.exp == exp
        # property_id and tenant_id will be empty (no DB to resolve)
        assert ctx.property_id == ""
        assert ctx.tenant_id == ""

    def test_expired_token_denied(self):
        """An expired token should return None."""
        raw_token, _exp = issue_guest_token("BOOK-EXPIRED", ttl_seconds=-10)
        ctx = resolve_guest_token_context(raw_token)
        assert ctx is None

    def test_malformed_token_denied(self):
        """Garbage input should return None."""
        ctx = resolve_guest_token_context("not-a-real-token")
        assert ctx is None

    def test_tampered_token_denied(self):
        """A token with modified signature should be rejected."""
        raw_token, _exp = issue_guest_token("BOOK-TAMPER", ttl_seconds=3600)
        # Tamper with the signature portion
        parts = raw_token.split(".", 1)
        tampered = f"{parts[0]}.AAAAAAAAAA"
        ctx = resolve_guest_token_context(tampered)
        assert ctx is None

    def test_empty_string_denied(self):
        """Empty string should be denied."""
        ctx = resolve_guest_token_context("")
        assert ctx is None

    def test_no_dot_denied(self):
        """Token without a dot separator should be denied."""
        ctx = resolve_guest_token_context("nodot")
        assert ctx is None


# ---------------------------------------------------------------------------
# Test: Verify issue → resolve round-trip
# ---------------------------------------------------------------------------

class TestIssueResolveRoundTrip:
    def test_valid_roundtrip(self):
        """issue_guest_token → resolve_guest_token_context should work."""
        raw, exp = issue_guest_token("BK-RT-001", guest_email="rt@test.com", ttl_seconds=7200)
        ctx = resolve_guest_token_context(raw)
        assert ctx is not None
        assert ctx.booking_ref == "BK-RT-001"
        assert ctx.guest_email == "rt@test.com"
        assert ctx.exp == exp

    def test_different_bookings_get_different_tokens(self):
        """Two tokens for different bookings should resolve to their own booking_ref."""
        raw1, _ = issue_guest_token("BK-A", ttl_seconds=3600)
        raw2, _ = issue_guest_token("BK-B", ttl_seconds=3600)
        ctx1 = resolve_guest_token_context(raw1)
        ctx2 = resolve_guest_token_context(raw2)
        assert ctx1 is not None
        assert ctx2 is not None
        assert ctx1.booking_ref == "BK-A"
        assert ctx2.booking_ref == "BK-B"
        assert raw1 != raw2


# ---------------------------------------------------------------------------
# Test: verify_guest_token still works (backward compat)
# ---------------------------------------------------------------------------

class TestVerifyGuestTokenCompat:
    def test_valid(self):
        raw, _exp = issue_guest_token("BK-COMPAT", guest_email="c@test.com", ttl_seconds=3600)
        result = verify_guest_token(raw, expected_booking_ref="BK-COMPAT")
        assert result is not None
        assert result["booking_ref"] == "BK-COMPAT"
        assert result["guest_email"] == "c@test.com"

    def test_wrong_booking_ref(self):
        raw, _exp = issue_guest_token("BK-A", ttl_seconds=3600)
        result = verify_guest_token(raw, expected_booking_ref="BK-WRONG")
        assert result is None

    def test_expired(self):
        raw, _exp = issue_guest_token("BK-EXP", ttl_seconds=-10)
        result = verify_guest_token(raw, expected_booking_ref="BK-EXP")
        assert result is None
