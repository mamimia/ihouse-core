"""
Phase 1062 — Payout Service Unit Tests

Tests the canonical payout service in isolation using an in-memory mock DB.
No real Supabase connection required.
"""
import pytest
from unittest.mock import MagicMock


def _make_db(facts=None, payout_row=None):
    """Build a mock Supabase client that returns canned data."""
    db = MagicMock()

    # Chain pattern: db.table().select().eq()...execute()
    def _chain(*args, **kwargs):
        m = MagicMock()
        m.select = _chain
        m.eq = _chain
        m.gte = _chain
        m.lt = _chain
        m.order = _chain
        m.limit = _chain
        m.insert = _chain
        m.update = _chain
        m.upsert = _chain
        result = MagicMock()
        result.data = facts if facts is not None else []
        m.execute = MagicMock(return_value=result)
        return m

    db.table = _chain
    return db


# ---------------------------------------------------------------------------
# create_payout
# ---------------------------------------------------------------------------

class TestCreatePayout:
    def test_empty_period_creates_zero_payout(self):
        """No facts → zero payout still persists (valid edge case)."""
        from services.payout_service import create_payout

        db = MagicMock()
        # facts query returns []
        facts_result = MagicMock(); facts_result.data = []
        # insert returns the row
        saved_row = {
            "id": "test-uuid", "status": "draft", "gross_total": 0.0,
            "net_payout": 0.0, "bookings_count": 0,
        }
        insert_result = MagicMock(); insert_result.data = [saved_row]

        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.gte.return_value = select_chain
        select_chain.lt.return_value = select_chain
        select_chain.execute.return_value = facts_result

        insert_chain = MagicMock()
        insert_chain.execute.return_value = insert_result

        event_insert_chain = MagicMock()
        event_insert_chain.execute.return_value = MagicMock()

        call_count = [0]
        def _table(name):
            call_count[0] += 1
            mock = MagicMock()
            if name == "booking_financial_facts":
                mock.select.return_value = select_chain
            elif name == "owner_payouts":
                mock.insert.return_value = insert_chain
            elif name == "payout_events":
                mock.insert.return_value = event_insert_chain
            return mock

        db.table = _table

        result = create_payout(
            db,
            tenant_id="tenant1",
            property_id="prop1",
            period_start="2026-01-01",
            period_end="2026-02-01",
            mgmt_fee_pct=15.0,
            actor_id="user_abc",
        )

        assert "error" not in result
        assert result["status"] == "draft"
        assert result["net_payout"] == 0.0

    def test_invalid_initial_status_returns_error(self):
        from services.payout_service import create_payout
        result = create_payout(
            MagicMock(),
            tenant_id="t", property_id="p",
            period_start="2026-01-01", period_end="2026-02-01",
            mgmt_fee_pct=0.0, actor_id="u",
            initial_status="approved",  # not allowed as initial
        )
        assert "error" in result
        assert "initial_status" in result["error"]


# ---------------------------------------------------------------------------
# transition_status
# ---------------------------------------------------------------------------

class TestTransitionStatus:
    def _db_with_payout(self, current_status: str):
        db = MagicMock()
        payout = {"id": "uuid1", "status": current_status, "tenant_id": "t1"}

        select_chain = MagicMock()
        select_chain.eq.return_value = select_chain
        select_chain.limit.return_value = select_chain
        select_chain.execute.return_value = MagicMock(data=[payout])

        update_chain = MagicMock()
        update_chain.eq.return_value = update_chain
        updated = {**payout, "status": "WILL_BE_OVERRIDDEN"}
        update_chain.execute.return_value = MagicMock(data=[updated])

        event_insert = MagicMock()
        event_insert.execute.return_value = MagicMock()

        def _table(name):
            m = MagicMock()
            if name == "owner_payouts":
                m.select.return_value = select_chain
                m.update.return_value = update_chain
            elif name == "payout_events":
                m.insert.return_value = event_insert
            return m

        db.table = _table
        return db

    def test_valid_transition_draft_to_pending(self):
        from services.payout_service import transition_status
        db = self._db_with_payout("draft")
        result = transition_status(db, payout_id="uuid1", tenant_id="t1",
                                   to_status="pending", actor_id="user1")
        assert "error" not in result

    def test_invalid_transition_paid_to_pending(self):
        from services.payout_service import transition_status
        db = self._db_with_payout("paid")
        result = transition_status(db, payout_id="uuid1", tenant_id="t1",
                                   to_status="pending", actor_id="user1")
        assert "error" in result
        assert "Invalid transition" in result["error"]

    def test_void_from_approved(self):
        from services.payout_service import transition_status
        db = self._db_with_payout("approved")
        result = transition_status(db, payout_id="uuid1", tenant_id="t1",
                                   to_status="voided", actor_id="user1")
        assert "error" not in result

    def test_not_found(self):
        from services.payout_service import transition_status
        db = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=[])
        db.table.return_value = chain

        result = transition_status(db, payout_id="nope", tenant_id="t1",
                                   to_status="pending", actor_id="u")
        assert "not_found" in str(result.get("error", ""))


# ---------------------------------------------------------------------------
# State machine completeness
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_all_draft_transitions(self):
        from services.payout_service import _TRANSITIONS
        assert set(_TRANSITIONS["draft"]) == {"pending", "voided"}

    def test_paid_is_terminal(self):
        from services.payout_service import _TRANSITIONS
        assert _TRANSITIONS["paid"] == []

    def test_voided_is_terminal(self):
        from services.payout_service import _TRANSITIONS
        assert _TRANSITIONS["voided"] == []

    def test_full_happy_path_exists(self):
        """Verify draft→pending→approved→paid is a reachable path."""
        from services.payout_service import _TRANSITIONS
        path = ["draft", "pending", "approved", "paid"]
        for i in range(len(path) - 1):
            assert path[i + 1] in _TRANSITIONS[path[i]], \
                f"Missing transition {path[i]}→{path[i+1]}"
