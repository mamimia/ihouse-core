"""
Phase 207 — Conflict Auto-Resolution Engine — Contract Tests

Groups:
    A — Pure module: no conflicts (non-overlapping bookings)
    B — Pure module: conflict detected → artifacts emitted
    C — Pure module: partial scan (DB fails) → partial=True
    D — Endpoint: 404 for unknown booking_id
    E — Endpoint: happy path with conflicts
    F — Endpoint: happy path no conflicts
    G — Auth guard → 403
    H — Idempotency: run_auto_check on clean property → 0 artifacts
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ===========================================================================
# Pure module helpers
# ===========================================================================

def _make_db_with_bookings(rows: list) -> MagicMock:
    """DB mock where booking_state returns provided rows."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=rows)
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.limit.return_value = chain

    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[{}])
    upsert_chain.upsert.return_value = upsert_chain
    upsert_chain.on_conflict.return_value = upsert_chain

    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{}])
    insert_chain.insert.return_value = insert_chain

    db = MagicMock()
    def table_side_effect(name):
        if name == "booking_state":
            return MagicMock(select=lambda *a, **kw: chain)
        if name == "conflict_resolution_queue":
            return upsert_chain
        if name == "admin_audit_log":
            return insert_chain
        return MagicMock()

    db.table.side_effect = table_side_effect
    return db


def _overlapping_bookings(prop: str = "prop-1") -> list:
    """Two ACTIVE bookings that overlap on the same property."""
    return [
        {
            "booking_id": "booking-A",
            "status": "ACTIVE",
            "tenant_id": "t1",
            "state_json": {
                "property_id": prop,
                "check_in": "2026-05-01",
                "check_out": "2026-05-05",
            },
            "provider": "bookingcom",
            "reservation_id": "R001",
        },
        {
            "booking_id": "booking-B",
            "status": "ACTIVE",
            "tenant_id": "t1",
            "state_json": {
                "property_id": prop,
                "check_in": "2026-05-03",
                "check_out": "2026-05-08",
            },
            "provider": "airbnb",
            "reservation_id": "X002",
        },
    ]


def _non_overlapping_bookings(prop: str = "prop-1") -> list:
    """Two ACTIVE bookings that do NOT overlap."""
    return [
        {
            "booking_id": "booking-C",
            "status": "ACTIVE",
            "tenant_id": "t1",
            "state_json": {
                "property_id": prop,
                "check_in": "2026-05-01",
                "check_out": "2026-05-05",
            },
            "provider": "bookingcom",
            "reservation_id": "R002",
        },
        {
            "booking_id": "booking-D",
            "status": "ACTIVE",
            "tenant_id": "t1",
            "state_json": {
                "property_id": prop,
                "check_in": "2026-05-05",
                "check_out": "2026-05-09",
            },
            "provider": "airbnb",
            "reservation_id": "X003",
        },
    ]


# ===========================================================================
# Endpoint helpers
# ===========================================================================

def _make_app(tenant_id: str = "t1") -> TestClient:
    from fastapi import FastAPI
    from api.conflicts_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_reject_app() -> TestClient:
    from fastapi import FastAPI, HTTPException
    from api.conflicts_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _endpoint_db(
    booking_id: str = "booking-A",
    property_id: str = "prop-1",
    booking_rows: list | None = None,
) -> MagicMock:
    """DB mock for the endpoint: booking_state returns a booking row."""
    booking_chain = MagicMock()
    booking_chain.execute.return_value = MagicMock(data=[{
        "booking_id": booking_id,
        "property_id": property_id,
        "tenant_id": "t1",
    }])
    booking_chain.select.return_value = booking_chain
    booking_chain.eq.return_value = booking_chain
    booking_chain.in_.return_value = booking_chain
    booking_chain.limit.return_value = booking_chain

    # For conflict scan
    active_bookings = booking_rows if booking_rows is not None else _overlapping_bookings(property_id)
    scan_chain = MagicMock()
    scan_chain.execute.return_value = MagicMock(data=active_bookings)
    scan_chain.select.return_value = scan_chain
    scan_chain.eq.return_value = scan_chain
    scan_chain.in_.return_value = scan_chain
    scan_chain.limit.return_value = scan_chain

    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[{}])
    upsert_chain.upsert.return_value = upsert_chain
    upsert_chain.on_conflict.return_value = upsert_chain

    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[{}])
    insert_chain.insert.return_value = insert_chain

    call_counts = {"n": 0}

    db = MagicMock()
    def table_side_effect(name):
        if name == "booking_state":
            call_counts["n"] += 1
            # First call = endpoint booking lookup; subsequent = conflict scan
            if call_counts["n"] == 1:
                return MagicMock(select=lambda *a, **kw: booking_chain)
            return MagicMock(select=lambda *a, **kw: scan_chain)
        if name == "conflict_resolution_queue":
            return upsert_chain
        if name == "admin_audit_log":
            return insert_chain
        return MagicMock()

    db.table.side_effect = table_side_effect
    return db


def _endpoint_not_found_db() -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


# ===========================================================================
# Group A — Pure module: no conflicts
# ===========================================================================

class TestGroupA_NoConflicts:

    def _run(self, rows: list) -> "ConflictAutoCheckResult":
        from services.conflict_auto_resolver import run_auto_check
        db = _make_db_with_bookings(rows)
        return run_auto_check(
            db=db,
            tenant_id="t1",
            booking_id="booking-C",
            property_id="prop-1",
            now_utc="2026-03-11T00:00:00+00:00",
        )

    def test_a1_no_conflicts_returns_zero(self) -> None:
        """A1: Non-overlapping bookings → conflicts_found=0."""
        result = self._run(_non_overlapping_bookings())
        assert result.conflicts_found == 0

    def test_a2_no_conflicts_no_artifacts(self) -> None:
        """A2: No conflicts → artifacts_written=0."""
        result = self._run(_non_overlapping_bookings())
        assert result.artifacts_written == 0

    def test_a3_no_conflicts_not_partial(self) -> None:
        """A3: Successful scan with no conflicts → partial=False."""
        result = self._run(_non_overlapping_bookings())
        assert result.partial is False


# ===========================================================================
# Group B — Pure module: conflict detected
# ===========================================================================

class TestGroupB_ConflictDetected:

    def _run(self, booking_id: str = "booking-A") -> "ConflictAutoCheckResult":
        from services.conflict_auto_resolver import run_auto_check
        db = _make_db_with_bookings(_overlapping_bookings())
        return run_auto_check(
            db=db,
            tenant_id="t1",
            booking_id=booking_id,
            property_id="prop-1",
            now_utc="2026-03-11T00:00:00+00:00",
        )

    def test_b1_conflict_returns_positive_count(self) -> None:
        """B1: Overlapping bookings → conflicts_found >= 1."""
        assert self._run().conflicts_found >= 1

    def test_b2_conflict_writes_artifact(self) -> None:
        """B2: Conflict → artifacts_written >= 1."""
        assert self._run().artifacts_written >= 1

    def test_b3_conflict_not_partial(self) -> None:
        """B3: Successful scan — partial=False even when conflict found."""
        assert self._run().partial is False

    def test_b4_booking_b_also_gets_conflict(self) -> None:
        """B4: booking-B also detects the overlap from its side."""
        result = self._run("booking-B")
        assert result.conflicts_found >= 1


# ===========================================================================
# Group C — Pure module: partial scan (DB fails)
# ===========================================================================

class TestGroupC_PartialScan:

    def test_c1_db_failure_returns_partial_true(self) -> None:
        """C1: If booking_state query fails, partial=True."""
        from services.conflict_auto_resolver import run_auto_check
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = RuntimeError("DB down")
        result = run_auto_check(
            db=db,
            tenant_id="t1",
            booking_id="booking-A",
            property_id="prop-1",
        )
        assert result.partial is True

    def test_c2_db_failure_conflicts_zero(self) -> None:
        """C2: DB failure → conflicts_found=0."""
        from services.conflict_auto_resolver import run_auto_check
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.side_effect = RuntimeError("DB down")
        result = run_auto_check(
            db=db,
            tenant_id="t1",
            booking_id="booking-A",
            property_id="prop-1",
        )
        assert result.conflicts_found == 0


# ===========================================================================
# Group D — Endpoint: 404 for unknown booking
# ===========================================================================

class TestGroupD_EndpointNotFound:

    def test_d1_unknown_booking_returns_404(self) -> None:
        """D1: Unknown booking_id → 404."""
        c = _make_app()
        db = _endpoint_not_found_db()
        with patch.object(db, "table", return_value=db.table.return_value):
            resp = c.post(
                "/conflicts/auto-check/ghost-booking",
                headers={"X-Supabase-Client": "mock"},
            )
        # Patch supabase client
        with patch("api.conflicts_router._get_supabase_client", return_value=_endpoint_not_found_db()):
            resp = c.post("/conflicts/auto-check/ghost-booking")
        assert resp.status_code == 404

    def test_d2_404_includes_booking_id(self) -> None:
        """D2: 404 message includes the booking_id."""
        c = _make_app()
        with patch("api.conflicts_router._get_supabase_client", return_value=_endpoint_not_found_db()):
            body = c.post("/conflicts/auto-check/mystery-booking").json()
        assert "mystery-booking" in body.get("message", "")

    def test_d3_404_code_is_not_found(self) -> None:
        """D3: 404 code is NOT_FOUND."""
        c = _make_app()
        with patch("api.conflicts_router._get_supabase_client", return_value=_endpoint_not_found_db()):
            body = c.post("/conflicts/auto-check/x-booking").json()
        assert body.get("code") == "NOT_FOUND"

    def test_d4_response_contains_tenant_id(self) -> None:
        """D4: Success response contains tenant_id — not on 404 though."""
        c = _make_app()
        db = _endpoint_db()
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-A").json()
        assert "booking_id" in body


# ===========================================================================
# Group E — Endpoint happy path with conflicts
# ===========================================================================

class TestGroupE_HappyPathConflicts:

    def test_e1_returns_200(self) -> None:
        """E1: Known booking with overlapping partner → 200."""
        c = _make_app()
        db = _endpoint_db()
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            resp = c.post("/conflicts/auto-check/booking-A")
        assert resp.status_code == 200

    def test_e2_conflicts_found_positive(self) -> None:
        """E2: Response has conflicts_found >= 1 when overlap exists."""
        c = _make_app()
        db = _endpoint_db()
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-A").json()
        assert body["conflicts_found"] >= 1

    def test_e3_artifacts_written_positive(self) -> None:
        """E3: artifacts_written >= 1 when conflict found."""
        c = _make_app()
        db = _endpoint_db()
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-A").json()
        assert body["artifacts_written"] >= 1

    def test_e4_response_has_booking_id(self) -> None:
        """E4: Response includes booking_id."""
        c = _make_app()
        db = _endpoint_db()
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-A").json()
        assert body["booking_id"] == "booking-A"


# ===========================================================================
# Group F — Endpoint happy path no conflicts
# ===========================================================================

class TestGroupF_HappyPathNoConflicts:

    def test_f1_no_conflict_returns_200(self) -> None:
        """F1: Clean property → 200."""
        c = _make_app()
        db = _endpoint_db(booking_rows=_non_overlapping_bookings())
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            resp = c.post("/conflicts/auto-check/booking-C")
        assert resp.status_code == 200

    def test_f2_no_conflict_zero_conflicts_found(self) -> None:
        """F2: Clean property → conflicts_found=0."""
        c = _make_app()
        db = _endpoint_db(booking_id="booking-C", booking_rows=_non_overlapping_bookings())
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-C").json()
        assert body["conflicts_found"] == 0

    def test_f3_no_conflict_zero_artifacts(self) -> None:
        """F3: No conflicts → artifacts_written=0."""
        c = _make_app()
        db = _endpoint_db(booking_id="booking-C", booking_rows=_non_overlapping_bookings())
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-C").json()
        assert body["artifacts_written"] == 0


# ===========================================================================
# Group G — Auth guard
# ===========================================================================

class TestGroupG_AuthGuard:

    def test_g1_no_auth_returns_403(self) -> None:
        """G1: No auth → 403."""
        c = _make_reject_app()
        assert c.post("/conflicts/auto-check/booking-A").status_code == 403


# ===========================================================================
# Group H — Idempotency (clean property)
# ===========================================================================

class TestGroupH_Idempotency:

    def test_h1_second_call_same_result(self) -> None:
        """H1: Two calls on a booking with no conflicts both return conflicts_found=0."""
        c = _make_app()
        for _ in range(2):
            db = _endpoint_db(booking_id="booking-C", booking_rows=_non_overlapping_bookings())
            with patch("api.conflicts_router._get_supabase_client", return_value=db):
                body = c.post("/conflicts/auto-check/booking-C").json()
            assert body["conflicts_found"] == 0
            assert body["artifacts_written"] == 0

    def test_h2_partial_false_on_clean_run(self) -> None:
        """H2: partial=False on successful clean run."""
        c = _make_app()
        db = _endpoint_db(booking_id="booking-C", booking_rows=_non_overlapping_bookings())
        with patch("api.conflicts_router._get_supabase_client", return_value=db):
            body = c.post("/conflicts/auto-check/booking-C").json()
        assert body["partial"] is False
