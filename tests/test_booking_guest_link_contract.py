"""
Phase 194 — Contract tests: Booking → Guest Link

Groups:
  A — POST /bookings/{id}/link-guest: success, missing guest_id → 400,
      booking not found → 404, guest not found for tenant → 404
  B — DELETE /bookings/{id}/link-guest: success, booking not found → 404,
      idempotent (already null)
  C — Tenant isolation: cross-tenant booking → 404
"""
from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.table.return_value = db
    db.select.return_value = db
    db.update.return_value = db
    db.eq.return_value = db
    db.limit.return_value = db
    db.execute.return_value = MagicMock(data=[])
    return db


def _booking(bid=None, tenant="t1", guest_id=None):
    return {
        "booking_id": bid or str(uuid.uuid4()),
        "tenant_id": tenant,
        "status": "active",
        "guest_id": guest_id,
        "property_id": "prop-1",
        "check_in": "2026-04-01",
        "check_out": "2026-04-05",
        "source": "airbnb",
    }


def _guest(gid=None, tenant="t1", full_name="Alice Smith"):
    return {"id": gid or str(uuid.uuid4()), "tenant_id": tenant, "full_name": full_name}


# ---------------------------------------------------------------------------
# Group A — POST link-guest
# ---------------------------------------------------------------------------

class TestGroupA_LinkGuest:

    def test_a1_link_returns_200(self, mock_db):
        bid = str(uuid.uuid4())
        gid = str(uuid.uuid4())
        # First execute = booking fetch, second = guest fetch, third = update
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid)]),
            MagicMock(data=[_guest(gid=gid)]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=bid, body={"guest_id": gid},
            tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 200

    def test_a2_link_response_shape(self, mock_db):
        bid = str(uuid.uuid4())
        gid = str(uuid.uuid4())
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid)]),
            MagicMock(data=[_guest(gid=gid, full_name="Alice")]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=bid, body={"guest_id": gid},
            tenant_id="t1", client=mock_db,
        ))
        data = json.loads(result.body)
        assert data["linked"] is True
        assert data["guest_id"] == gid
        assert data["guest_name"] == "Alice"

    def test_a3_missing_guest_id_returns_400(self, mock_db):
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=str(uuid.uuid4()), body={},
            tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 400

    def test_a4_booking_not_found_returns_404(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=str(uuid.uuid4()), body={"guest_id": str(uuid.uuid4())},
            tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 404

    def test_a5_guest_not_found_returns_404(self, mock_db):
        bid = str(uuid.uuid4())
        # booking found, guest not found
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid)]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=bid, body={"guest_id": str(uuid.uuid4())},
            tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 404


# ---------------------------------------------------------------------------
# Group B — DELETE unlink-guest
# ---------------------------------------------------------------------------

class TestGroupB_UnlinkGuest:

    def test_b1_unlink_returns_200(self, mock_db):
        bid = str(uuid.uuid4())
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid, guest_id=str(uuid.uuid4()))]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import unlink_guest
        result = asyncio.run(unlink_guest(
            booking_id=bid, tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 200

    def test_b2_unlink_response_has_linked_false(self, mock_db):
        bid = str(uuid.uuid4())
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid)]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import unlink_guest
        result = asyncio.run(unlink_guest(
            booking_id=bid, tenant_id="t1", client=mock_db,
        ))
        data = json.loads(result.body)
        assert data["linked"] is False
        assert data["guest_id"] is None

    def test_b3_unlink_booking_not_found_returns_404(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.booking_guest_link_router import unlink_guest
        result = asyncio.run(unlink_guest(
            booking_id=str(uuid.uuid4()), tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 404

    def test_b4_unlink_idempotent_already_null(self, mock_db):
        """Unlinking when guest_id is already null should still return 200."""
        bid = str(uuid.uuid4())
        mock_db.execute.side_effect = [
            MagicMock(data=[_booking(bid=bid, guest_id=None)]),
            MagicMock(data=[]),
        ]
        from api.booking_guest_link_router import unlink_guest
        result = asyncio.run(unlink_guest(
            booking_id=bid, tenant_id="t1", client=mock_db,
        ))
        assert result.status_code == 200


# ---------------------------------------------------------------------------
# Group C — Tenant isolation
# ---------------------------------------------------------------------------

class TestGroupC_TenantIsolation:

    def test_c1_link_cross_tenant_booking_returns_404(self, mock_db):
        """Booking from t1 not visible to t2 — DB returns empty."""
        mock_db.execute.return_value = MagicMock(data=[])
        from api.booking_guest_link_router import link_guest
        result = asyncio.run(link_guest(
            booking_id=str(uuid.uuid4()), body={"guest_id": str(uuid.uuid4())},
            tenant_id="t2", client=mock_db,
        ))
        assert result.status_code == 404

    def test_c2_unlink_cross_tenant_booking_returns_404(self, mock_db):
        mock_db.execute.return_value = MagicMock(data=[])
        from api.booking_guest_link_router import unlink_guest
        result = asyncio.run(unlink_guest(
            booking_id=str(uuid.uuid4()), tenant_id="t2", client=mock_db,
        ))
        assert result.status_code == 404
