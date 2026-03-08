"""
Phase 57 Contract Tests: Webhook Signature Verifier

Verifies:
- Correct HMAC computation and comparison
- Dev-mode skip (no secret configured)
- Hard failure when secret present + sig missing
- Hard failure when secret present + sig wrong
- Sig with / without sha256= prefix both work
- Constant-time path (API contract, not timing test)
- All 5 providers supported
- Unknown provider raises ValueError
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest

from adapters.ota.signature_verifier import (
    SignatureVerificationError,
    verify_webhook_signature,
    compute_expected_signature,
    get_signature_header_name,
    _compute_hmac_hex,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BODY = json.dumps({"event_id": "test_001", "event_type": "reservation_created"}).encode()
_SECRET = "super_secret_test_key"


def _make_sig(secret: str, body: bytes, prefix: bool = True) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}" if prefix else digest


# ---------------------------------------------------------------------------
# T1: Dev mode (secret not set) — should skip, no raise
# ---------------------------------------------------------------------------

class TestDevModeSkip:
    def test_no_secret_no_raise_no_header(self, monkeypatch):
        """When secret env var is absent, verification is skipped silently."""
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_AIRBNB", raising=False)
        # Should NOT raise
        verify_webhook_signature(
            provider="airbnb",
            raw_body=_BODY,
            signature_header="",
        )

    def test_no_secret_bad_sig_still_skips(self, monkeypatch):
        """Even if a header is present, absent secret means skip."""
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_EXPEDIA", raising=False)
        verify_webhook_signature(
            provider="expedia",
            raw_body=_BODY,
            signature_header="sha256=completely_wrong",
        )


# ---------------------------------------------------------------------------
# T2: Production mode (secret set) — correct signature passes
# ---------------------------------------------------------------------------

class TestCorrectSignature:
    def test_correct_sig_with_prefix_passes(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_AIRBNB", _SECRET)
        sig = _make_sig(_SECRET, _BODY, prefix=True)
        # Should NOT raise
        verify_webhook_signature(
            provider="airbnb",
            raw_body=_BODY,
            signature_header=sig,
        )

    def test_correct_sig_without_prefix_passes(self, monkeypatch):
        """Signature without sha256= prefix is also accepted."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", _SECRET)
        sig = _make_sig(_SECRET, _BODY, prefix=False)
        verify_webhook_signature(
            provider="bookingcom",
            raw_body=_BODY,
            signature_header=sig,
        )

    def test_correct_sig_with_whitespace_passes(self, monkeypatch):
        """Signature value may have surrounding whitespace."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_EXPEDIA", _SECRET)
        sig = "  " + _make_sig(_SECRET, _BODY, prefix=True) + "  "
        verify_webhook_signature(
            provider="expedia",
            raw_body=_BODY,
            signature_header=sig,
        )


# ---------------------------------------------------------------------------
# T3: Production mode — wrong signature raises
# ---------------------------------------------------------------------------

class TestWrongSignature:
    def test_tampered_body_fails(self, monkeypatch):
        """Signature computed on original body fails against modified body."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_AGODA", _SECRET)
        sig = _make_sig(_SECRET, _BODY, prefix=True)
        tampered = _BODY + b" tampered"
        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_webhook_signature(
                provider="agoda",
                raw_body=tampered,
                signature_header=sig,
            )
        assert exc_info.value.provider == "agoda"

    def test_wrong_secret_fails(self, monkeypatch):
        """Signature computed with different secret fails."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_TRIPCOM", _SECRET)
        sig = _make_sig("wrong_secret", _BODY, prefix=True)
        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(
                provider="tripcom",
                raw_body=_BODY,
                signature_header=sig,
            )

    def test_missing_header_when_secret_set_fails(self, monkeypatch):
        """If secret is set but header is empty → hard failure."""
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_AIRBNB", _SECRET)
        with pytest.raises(SignatureVerificationError) as exc_info:
            verify_webhook_signature(
                provider="airbnb",
                raw_body=_BODY,
                signature_header="",
            )
        assert "Missing signature header" in exc_info.value.reason

    def test_garbage_signature_fails(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_EXPEDIA", _SECRET)
        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(
                provider="expedia",
                raw_body=_BODY,
                signature_header="sha256=aaaaaa",
            )


# ---------------------------------------------------------------------------
# T4: Unknown provider raises ValueError (not SignatureVerificationError)
# ---------------------------------------------------------------------------

class TestUnknownProvider:
    def test_unknown_provider_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            verify_webhook_signature(
                provider="tripadvisor",
                raw_body=_BODY,
                signature_header="sha256=abc",
            )


# ---------------------------------------------------------------------------
# T5: All 5 providers are registered
# ---------------------------------------------------------------------------

class TestAllProvidersRegistered:
    @pytest.mark.parametrize("provider", [
        "bookingcom", "expedia", "airbnb", "agoda", "tripcom",
    ])
    def test_provider_skips_gracefully_when_no_secret(self, provider, monkeypatch):
        """All 5 providers skip verification when secret is absent."""
        env_var = f"IHOUSE_WEBHOOK_SECRET_{provider.upper()}"
        monkeypatch.delenv(env_var, raising=False)
        # Should NOT raise
        verify_webhook_signature(
            provider=provider,
            raw_body=_BODY,
            signature_header="",
        )

    @pytest.mark.parametrize("provider", [
        "bookingcom", "expedia", "airbnb", "agoda", "tripcom",
    ])
    def test_provider_verifies_when_secret_present(self, provider, monkeypatch):
        """All 5 providers verify correctly when secret is present."""
        env_var = f"IHOUSE_WEBHOOK_SECRET_{provider.upper()}"
        monkeypatch.setenv(env_var, _SECRET)
        sig = _make_sig(_SECRET, _BODY, prefix=True)
        verify_webhook_signature(
            provider=provider,
            raw_body=_BODY,
            signature_header=sig,
        )


# ---------------------------------------------------------------------------
# T6: Header name utility
# ---------------------------------------------------------------------------

class TestHeaderNames:
    def test_header_names_correct(self):
        assert get_signature_header_name("airbnb") == "X-Airbnb-Signature"
        assert get_signature_header_name("bookingcom") == "X-Booking-Signature"
        assert get_signature_header_name("expedia") == "X-Expedia-Signature"
        assert get_signature_header_name("agoda") == "X-Agoda-Signature"
        assert get_signature_header_name("tripcom") == "X-TripCom-Signature"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            get_signature_header_name("tripadvisor")


# ---------------------------------------------------------------------------
# T7: compute_expected_signature helper
# ---------------------------------------------------------------------------

class TestComputeExpectedSignature:
    def test_compute_produces_correct_sig(self, monkeypatch):
        monkeypatch.setenv("IHOUSE_WEBHOOK_SECRET_AIRBNB", _SECRET)
        sig = compute_expected_signature("airbnb", _BODY)
        assert sig.startswith("sha256=")
        # Verify it actually passes the verifier
        verify_webhook_signature(
            provider="airbnb",
            raw_body=_BODY,
            signature_header=sig,
        )

    def test_compute_raises_when_no_secret(self, monkeypatch):
        monkeypatch.delenv("IHOUSE_WEBHOOK_SECRET_AIRBNB", raising=False)
        with pytest.raises(ValueError, match="not set"):
            compute_expected_signature("airbnb", _BODY)
