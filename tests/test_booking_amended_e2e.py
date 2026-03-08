"""
Phase 50 — E2E Live Test: BOOKING_AMENDED

Tests against live Supabase to verify:
1. BOOKING_CREATED → APPLIED
2. BOOKING_AMENDED → APPLIED + check_in / check_out updated
3. BOOKING_AMENDED (partial) → only supplied dates updated
4. BOOKING_AMENDED on CANCELED booking → AMENDMENT_ON_CANCELED_BOOKING
5. BOOKING_AMENDED on non-existent booking → BOOKING_NOT_FOUND

Run:
    cd /Users/clawadmin/Antigravity\\ Proj/ihouse-core
    source .venv/bin/activate
    PYTHONPATH=src python3 -m pytest tests/test_booking_amended_e2e.py -v -s
"""

import os
import uuid
import pytest
from supabase import create_client

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://reykggmlcehswrxjviup.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJleWtnZ21sY2Voc3dyeGp2aXVwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjI5Njc2NiwiZXhwIjoyMDg3ODcyNzY2fQ.L2oIbuAZ_Q-RWtQHoo9kPs9QPrtsary8aVYb1OdzeC8",
)

TENANT = "tenant_e2e_amended"


@pytest.fixture(scope="module")
def client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def new_ids():
    """Return a fresh (booking_id, property_id, request_id) triple, all unique per call."""
    uid = uuid.uuid4().hex
    booking_id = f"bookingcom_{uid[:12]}"
    # property_id derived from booking_id — guarantees no overlap between test runs
    property_id = f"prop_{uid}"
    request_id = f"req-{uuid.uuid4().hex}"
    return booking_id, property_id, request_id


def new_request_id():
    return f"req-{uuid.uuid4().hex}"


def call_apply(client, envelope, emit):
    """Call apply_envelope RPC and return parsed result."""
    result = client.rpc("apply_envelope", {"p_envelope": envelope, "p_emit": emit}).execute()
    return result.data


def create_booking(client, booking_id, property_id, check_in, check_out):
    """Helper: create a booking and assert APPLIED."""
    req = new_request_id()
    envelope = {
        "type": "BOOKING_CREATED",
        "tenant_id": TENANT,
        "idempotency": {"request_id": req},
        "payload": {"provider": "bookingcom"},
    }
    emit = [
        {
            "type": "BOOKING_CREATED",
            "payload": {
                "booking_id": booking_id,
                "source": "bookingcom",
                "reservation_id": booking_id.split("_", 1)[1],
                "property_id": property_id,
                "check_in": check_in,
                "check_out": check_out,
                "tenant_id": TENANT,
            },
        }
    ]
    result = call_apply(client, envelope, emit)
    assert result["status"] == "APPLIED", f"Expected APPLIED, got: {result}"
    return result


def cancel_booking(client, booking_id):
    """Helper: cancel a booking and assert APPLIED."""
    req = new_request_id()
    envelope = {
        "type": "BOOKING_CANCELED",
        "tenant_id": TENANT,
        "idempotency": {"request_id": req},
        "payload": {"provider": "bookingcom"},
    }
    emit = [{"type": "BOOKING_CANCELED", "payload": {"booking_id": booking_id}}]
    result = call_apply(client, envelope, emit)
    assert result["status"] == "APPLIED", f"Expected APPLIED, got: {result}"
    return result


def amend_booking(client, booking_id, new_check_in=None, new_check_out=None, reason=None):
    """Helper: amend a booking — returns raw result (may raise)."""
    req = new_request_id()
    payload = {"booking_id": booking_id}
    if new_check_in:
        payload["new_check_in"] = new_check_in
    if new_check_out:
        payload["new_check_out"] = new_check_out
    if reason:
        payload["amendment_reason"] = reason

    envelope = {
        "type": "BOOKING_AMENDED",
        "tenant_id": TENANT,
        "idempotency": {"request_id": req},
        "payload": {"provider": "bookingcom"},
    }
    emit = [{"type": "BOOKING_AMENDED", "payload": payload}]
    return call_apply(client, envelope, emit)


# ---------------------------------------------------------------------------
# Test 1: BOOKING_CREATED → APPLIED (smoke)
# ---------------------------------------------------------------------------
class TestBookingCreated:
    def test_created_returns_applied(self, client):
        booking_id, property_id, _ = new_ids()
        result = create_booking(client, booking_id, property_id, "2026-06-01", "2026-06-07")
        assert result["status"] == "APPLIED"
        assert result.get("state_upsert_found") is True
        print(f"\n✅ BOOKING_CREATED → APPLIED  (booking_id={booking_id})")


# ---------------------------------------------------------------------------
# Test 2: BOOKING_AMENDED → APPLIED + both dates updated
# ---------------------------------------------------------------------------
class TestBookingAmended:
    def test_amended_both_dates(self, client):
        booking_id, property_id, _ = new_ids()
        create_booking(client, booking_id, property_id, "2026-07-01", "2026-07-07")

        result = amend_booking(
            client, booking_id,
            new_check_in="2026-07-05",
            new_check_out="2026-07-12",
            reason="guest_request",
        )
        assert result["status"] == "APPLIED", f"Got: {result}"
        print(f"\n✅ BOOKING_AMENDED → APPLIED  (booking_id={booking_id})")

        row = (
            client.table("booking_state")
            .select("check_in, check_out, status, version")
            .eq("booking_id", booking_id)
            .execute()
            .data[0]
        )
        assert row["check_in"] == "2026-07-05", f"check_in mismatch: {row['check_in']}"
        assert row["check_out"] == "2026-07-12", f"check_out mismatch: {row['check_out']}"
        assert row["status"] == "active", f"status must stay 'active', got: {row['status']}"
        assert row["version"] == 2, f"version should be 2, got: {row['version']}"
        print(f"   check_in  → {row['check_in']} ✅")
        print(f"   check_out → {row['check_out']} ✅")
        print(f"   status    → {row['status']} (stays active) ✅")
        print(f"   version   → {row['version']} ✅")

    def test_amended_partial_only_check_in(self, client):
        """Amend with only new_check_in — check_out must be preserved via COALESCE."""
        booking_id, property_id, _ = new_ids()
        create_booking(client, booking_id, property_id, "2026-08-01", "2026-08-10")

        result = amend_booking(client, booking_id, new_check_in="2026-08-03")
        assert result["status"] == "APPLIED"

        row = (
            client.table("booking_state")
            .select("check_in, check_out, status")
            .eq("booking_id", booking_id)
            .execute()
            .data[0]
        )
        assert row["check_in"] == "2026-08-03", f"check_in not updated: {row['check_in']}"
        assert row["check_out"] == "2026-08-10", f"check_out should be preserved: {row['check_out']}"
        print(f"\n✅ Partial BOOKING_AMENDED (check_in only) → APPLIED")
        print(f"   check_in  → {row['check_in']} (updated) ✅")
        print(f"   check_out → {row['check_out']} (preserved via COALESCE) ✅")


# ---------------------------------------------------------------------------
# Test 3: BOOKING_AMENDED on CANCELED → AMENDMENT_ON_CANCELED_BOOKING
# ---------------------------------------------------------------------------
class TestBookingAmendedOnCanceled:
    def test_amended_on_canceled_raises(self, client):
        booking_id, property_id, _ = new_ids()
        create_booking(client, booking_id, property_id, "2026-09-01", "2026-09-07")
        cancel_booking(client, booking_id)

        with pytest.raises(Exception) as exc_info:
            amend_booking(client, booking_id, new_check_in="2026-09-10", new_check_out="2026-09-15")

        error_text = str(exc_info.value)
        assert "AMENDMENT_ON_CANCELED_BOOKING" in error_text, (
            f"Expected AMENDMENT_ON_CANCELED_BOOKING, got: {error_text}"
        )
        print(f"\n✅ BOOKING_AMENDED on CANCELED → AMENDMENT_ON_CANCELED_BOOKING ✅")

    def test_amended_nonexistent_booking_raises(self, client):
        """Amending a booking_id that doesn't exist → BOOKING_NOT_FOUND."""
        ghost_id = f"bookingcom_nonexistent_{uuid.uuid4().hex[:8]}"

        with pytest.raises(Exception) as exc_info:
            amend_booking(client, ghost_id, new_check_in="2026-10-01", new_check_out="2026-10-07")

        error_text = str(exc_info.value)
        assert "BOOKING_NOT_FOUND" in error_text, (
            f"Expected BOOKING_NOT_FOUND, got: {error_text}"
        )
        print(f"\n✅ BOOKING_AMENDED on non-existent booking → BOOKING_NOT_FOUND ✅")
