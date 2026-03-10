"""
Phase 206 — Pre-Arrival Guest Task Workflow — Contract Tests

Groups:
    A — Pure module: emits exactly GUEST_WELCOME + CHECKIN_PREP (2 tasks)
    B — Pure module: task_ids are deterministic (same input → same IDs)
    C — Pure module: special_requests appear in GUEST_WELCOME description
    D — Pure module: no special_requests → description is None
    E — Endpoint: 404 for unknown booking_id
    F — Endpoint: happy path with guest returns tasks_created list
    G — Endpoint: auth guard → 403
    H — Endpoint: no guest linked → fallback name "Guest" used
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("fastapi")


# ---------------------------------------------------------------------------
# Helpers — pure module
# ---------------------------------------------------------------------------

def _make_pre_arrival_tasks(
    guest_name: str | None = "Maria",
    special_requests: str | None = None,
):
    from tasks.pre_arrival_tasks import tasks_for_pre_arrival
    return tasks_for_pre_arrival(
        tenant_id="t1",
        booking_id="bcom_123",
        property_id="prop-1",
        check_in="2026-04-15",
        guest_name=guest_name,
        special_requests=special_requests,
        created_at="2026-03-10T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Helpers — endpoint
# ---------------------------------------------------------------------------

def _make_app(tenant_id: str = "t1") -> TestClient:
    from fastapi import FastAPI
    from tasks.task_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _stub_auth():
        return tenant_id

    app.dependency_overrides[jwt_auth] = _stub_auth
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _make_reject_app() -> TestClient:
    from fastapi import FastAPI, HTTPException
    from tasks.task_router import router
    from api.auth import jwt_auth

    app = FastAPI()

    async def _reject():
        raise HTTPException(status_code=403, detail="AUTH_FAILED")

    app.dependency_overrides[jwt_auth] = _reject
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def _booking_db(booking_id: str = "bcom_123") -> MagicMock:
    """DB mock that returns a booking row."""
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[{
        "booking_id": booking_id,
        "property_id": "prop-1",
        "check_in": "2026-04-15",
        "tenant_id": "t1",
    }])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain

    link_chain = MagicMock()
    link_chain.execute.return_value = MagicMock(data=[{"guest_id": "g-1"}])
    link_chain.select.return_value = link_chain
    link_chain.eq.return_value = link_chain
    link_chain.limit.return_value = link_chain

    guest_chain = MagicMock()
    guest_chain.execute.return_value = MagicMock(data=[{
        "first_name": "Maria",
        "special_requests": "vegan meals",
    }])
    guest_chain.select.return_value = guest_chain
    guest_chain.eq.return_value = guest_chain
    guest_chain.limit.return_value = guest_chain

    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[{}])
    upsert_chain.upsert.return_value = upsert_chain
    upsert_chain.on_conflict.return_value = upsert_chain

    db = MagicMock()
    call_count = {"n": 0}

    def table_side_effect(name):
        if name == "booking_state":
            return MagicMock(select=lambda *a, **kw: chain)
        if name == "booking_guest_link":
            return MagicMock(select=lambda *a, **kw: link_chain)
        if name == "guests":
            return MagicMock(select=lambda *a, **kw: guest_chain)
        if name == "tasks":
            return upsert_chain
        return MagicMock()

    db.table.side_effect = table_side_effect
    return db


def _booking_not_found_db() -> MagicMock:
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    db = MagicMock()
    db.table.return_value.select.return_value = chain
    return db


def _no_guest_db() -> MagicMock:
    """Booking exists but no guest link."""
    booking_chain = MagicMock()
    booking_chain.execute.return_value = MagicMock(data=[{
        "booking_id": "bcom_999",
        "property_id": "prop-2",
        "check_in": "2026-05-01",
        "tenant_id": "t1",
    }])
    booking_chain.select.return_value = booking_chain
    booking_chain.eq.return_value = booking_chain
    booking_chain.limit.return_value = booking_chain

    link_chain = MagicMock()
    link_chain.execute.return_value = MagicMock(data=[])
    link_chain.select.return_value = link_chain
    link_chain.eq.return_value = link_chain
    link_chain.limit.return_value = link_chain

    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[{}])
    upsert_chain.upsert.return_value = upsert_chain
    upsert_chain.on_conflict.return_value = upsert_chain

    db = MagicMock()
    def table_side_effect(name):
        if name == "booking_state":
            return MagicMock(select=lambda *a, **kw: booking_chain)
        if name == "booking_guest_link":
            return MagicMock(select=lambda *a, **kw: link_chain)
        if name == "tasks":
            return upsert_chain
        return MagicMock()

    db.table.side_effect = table_side_effect
    return db


# ===========================================================================
# Group A — Pure module emits 2 tasks with correct kinds
# ===========================================================================

class TestGroupA_PureModuleKinds:

    def test_a1_emits_two_tasks(self) -> None:
        """A1: tasks_for_pre_arrival emits exactly 2 tasks."""
        tasks = _make_pre_arrival_tasks()
        assert len(tasks) == 2

    def test_a2_first_task_is_guest_welcome(self) -> None:
        """A2: First task kind is GUEST_WELCOME."""
        tasks = _make_pre_arrival_tasks()
        assert tasks[0].kind.value == "GUEST_WELCOME"

    def test_a3_second_task_is_checkin_prep(self) -> None:
        """A3: Second task kind is CHECKIN_PREP."""
        tasks = _make_pre_arrival_tasks()
        assert tasks[1].kind.value == "CHECKIN_PREP"

    def test_a4_both_tasks_high_priority(self) -> None:
        """A4: Both tasks have HIGH priority."""
        tasks = _make_pre_arrival_tasks()
        for t in tasks:
            assert t.priority.value == "HIGH"

    def test_a5_guest_name_in_welcome_title(self) -> None:
        """A5: Guest name appears in GUEST_WELCOME title."""
        tasks = _make_pre_arrival_tasks(guest_name="Priya")
        assert "Priya" in tasks[0].title

    def test_a6_guest_name_in_checkin_prep_title(self) -> None:
        """A6: Guest name appears in CHECKIN_PREP title."""
        tasks = _make_pre_arrival_tasks(guest_name="Priya")
        assert "Priya" in tasks[1].title

    def test_a7_due_date_matches_check_in(self) -> None:
        """A7: Both tasks due on check_in date."""
        tasks = _make_pre_arrival_tasks()
        for t in tasks:
            assert t.due_date == "2026-04-15"


# ===========================================================================
# Group B — task_id determinism
# ===========================================================================

class TestGroupB_TaskIdDeterminism:

    def test_b1_same_inputs_same_task_ids(self) -> None:
        """B1: Same inputs produce the same task_ids."""
        t1 = _make_pre_arrival_tasks()
        t2 = _make_pre_arrival_tasks()
        assert t1[0].task_id == t2[0].task_id
        assert t1[1].task_id == t2[1].task_id

    def test_b2_different_booking_different_ids(self) -> None:
        """B2: Different booking_id → different task_ids."""
        from tasks.pre_arrival_tasks import tasks_for_pre_arrival
        tasks_a = tasks_for_pre_arrival("t1", "bcom_001", "prop-1", "2026-04-15")
        tasks_b = tasks_for_pre_arrival("t1", "bcom_002", "prop-1", "2026-04-15")
        assert tasks_a[0].task_id != tasks_b[0].task_id


# ===========================================================================
# Group C — special_requests in description
# ===========================================================================

class TestGroupC_SpecialRequests:

    def test_c1_special_requests_in_welcome_description(self) -> None:
        """C1: special_requests appear in GUEST_WELCOME description."""
        tasks = _make_pre_arrival_tasks(special_requests="vegan meals")
        assert tasks[0].description is not None
        assert "vegan meals" in tasks[0].description

    def test_c2_checkin_prep_has_no_special_requests_description(self) -> None:
        """C2: CHECKIN_PREP description is None regardless of requests."""
        tasks = _make_pre_arrival_tasks(special_requests="extra pillows")
        assert tasks[1].description is None


# ===========================================================================
# Group D — no special_requests → description None
# ===========================================================================

class TestGroupD_NoSpecialRequests:

    def test_d1_no_requests_welcome_description_is_none(self) -> None:
        """D1: Without special_requests, GUEST_WELCOME description is None."""
        tasks = _make_pre_arrival_tasks(special_requests=None)
        assert tasks[0].description is None

    def test_d2_empty_string_requests_description_is_none(self) -> None:
        """D2: Empty string special_requests treated as absent."""
        tasks = _make_pre_arrival_tasks(special_requests="  ")
        assert tasks[0].description is None


# ===========================================================================
# Group E — Endpoint 404 for unknown booking
# ===========================================================================

class TestGroupE_BookingNotFound:

    def test_e1_unknown_booking_returns_404(self) -> None:
        """E1: POST pre-arrival for unknown booking_id → 404 NOT_FOUND."""
        c = _make_app()
        db = _booking_not_found_db()
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = c.post("/tasks/pre-arrival/unknown-booking")
        assert resp.status_code == 404
        assert resp.json()["code"] == "NOT_FOUND"

    def test_e2_404_message_includes_booking_id(self) -> None:
        """E2: 404 message includes the booking_id."""
        c = _make_app()
        db = _booking_not_found_db()
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            body = c.post("/tasks/pre-arrival/mystery-booking").json()
        assert "mystery-booking" in body["message"]


# ===========================================================================
# Group F — Happy path with guest
# ===========================================================================

class TestGroupF_HappyPath:

    def test_f1_happy_path_returns_200(self) -> None:
        """F1: Known booking + guest → 200."""
        c = _make_app()
        db = _booking_db()
        with patch("tasks.task_router._get_supabase_client", return_value=db):
            resp = c.post("/tasks/pre-arrival/bcom_123")
        assert resp.status_code == 200

    def test_f2_response_has_booking_id(self) -> None:
        """F2: Response includes booking_id."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_booking_db()):
            body = c.post("/tasks/pre-arrival/bcom_123").json()
        assert body["booking_id"] == "bcom_123"

    def test_f3_response_has_guest_name(self) -> None:
        """F3: Response includes resolved guest_name."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_booking_db()):
            body = c.post("/tasks/pre-arrival/bcom_123").json()
        assert body["guest_name"] == "Maria"

    def test_f4_response_has_tasks_created(self) -> None:
        """F4: Response includes tasks_created list."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_booking_db()):
            body = c.post("/tasks/pre-arrival/bcom_123").json()
        assert "tasks_created" in body

    def test_f5_tasks_created_contains_two_entries(self) -> None:
        """F5: tasks_created has 2 items (GUEST_WELCOME + CHECKIN_PREP)."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_booking_db()):
            body = c.post("/tasks/pre-arrival/bcom_123").json()
        assert len(body["tasks_created"]) == 2

    def test_f6_tasks_include_guest_welcome(self) -> None:
        """F6: GUEST_WELCOME kind present in tasks_created."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_booking_db()):
            body = c.post("/tasks/pre-arrival/bcom_123").json()
        kinds = [t["kind"] for t in body["tasks_created"]]
        assert "GUEST_WELCOME" in kinds


# ===========================================================================
# Group G — Auth guard
# ===========================================================================

class TestGroupG_AuthGuard:

    def test_g1_no_auth_returns_403(self) -> None:
        """G1: POST pre-arrival without auth → 403."""
        assert _make_reject_app().post("/tasks/pre-arrival/bcom_123").status_code == 403


# ===========================================================================
# Group H — No guest linked → fallback to "Guest"
# ===========================================================================

class TestGroupH_NoGuestFallback:

    def test_h1_no_guest_returns_200(self) -> None:
        """H1: Booking with no guest link still returns 200."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_no_guest_db()):
            resp = c.post("/tasks/pre-arrival/bcom_999")
        assert resp.status_code == 200

    def test_h2_no_guest_uses_fallback_name(self) -> None:
        """H2: guest_name in response is 'Guest' when no guest linked."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_no_guest_db()):
            body = c.post("/tasks/pre-arrival/bcom_999").json()
        assert body["guest_name"] == "Guest"

    def test_h3_no_guest_still_creates_tasks(self) -> None:
        """H3: Tasks are still created even without guest profile."""
        c = _make_app()
        with patch("tasks.task_router._get_supabase_client", return_value=_no_guest_db()):
            body = c.post("/tasks/pre-arrival/bcom_999").json()
        assert len(body["tasks_created"]) == 2
