"""
Phase 352 — CI/CD Pipeline Hardening
======================================

Tests for foundational pipeline components that must never break
during CI runs, migrations, or deployments.

Groups:
  A — CoreExecutor contract (6 tests)
  B — InMemoryEventLogPort + InMemoryEventLogApplier (6 tests)
  C — InMemoryStateStorePort (4 tests)
  D — Idempotency: duplicate event handling (4 tests)
  E — CI Guard: environment + env-var contract (4 tests)
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

import pytest

os.environ.setdefault("IHOUSE_ENV", "test")
os.environ.setdefault("SUPABASE_URL", "http://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.executor import CoreExecutor, CoreExecutionError, ExecuteResult  # noqa: E402
from core.testing.in_memory_event_log import (  # noqa: E402
    InMemoryEventLogPort,
    InMemoryEventLogApplier,
    StoredEnvelope,
)
from core.testing.in_memory_state_store import InMemoryStateStorePort  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_envelope(event_type: str = "BOOKING_CREATED") -> Dict[str, Any]:
    return {
        "type": event_type,
        "payload": {"booking_id": "bk-001", "tenant_id": "tenant-test"},
        "occurred_at": "2026-06-01T10:00:00+00:00",
    }


def _make_executor(
    *,
    with_applier: bool = False,
    replay_mode: bool = False,
) -> tuple[CoreExecutor, InMemoryEventLogPort, InMemoryEventLogApplier | None]:
    port = InMemoryEventLogPort()
    applier = InMemoryEventLogApplier() if with_applier else None
    state = InMemoryStateStorePort()
    ex = CoreExecutor(
        event_log_port=port,
        event_log_applier=applier,
        state_store=state,
        replay_mode=replay_mode,
    )
    return ex, port, applier


# ---------------------------------------------------------------------------
# Group A — CoreExecutor Contract
# ---------------------------------------------------------------------------

class TestGroupACoreExecutor:

    def test_a1_no_route_raises_core_execution_error(self):
        """Unknown event type → CoreExecutionError (tested in executor_smoke)."""
        ex, _, _ = _make_executor(with_applier=True)
        with pytest.raises(CoreExecutionError):
            ex.execute(envelope=_minimal_envelope("UNKNOWN_TYPE_XYZ_999"), idempotency_key="k1")

    def test_a2_missing_type_raises(self):
        """Envelope without 'type' → CoreExecutionError."""
        ex, _, _ = _make_executor(with_applier=True)
        with pytest.raises(CoreExecutionError, match="ENVELOPE_TYPE_REQUIRED"):
            ex.execute(
                envelope={"payload": {}, "occurred_at": "2026-01-01T00:00:00Z"},
                idempotency_key="k2",
            )

    def test_a3_missing_payload_raises(self):
        """Envelope without 'payload' dict → CoreExecutionError."""
        ex, _, _ = _make_executor(with_applier=True)
        with pytest.raises(CoreExecutionError, match="ENVELOPE_PAYLOAD_REQUIRED"):
            ex.execute(
                envelope={"type": "BOOKING_CREATED", "payload": "bad", "occurred_at": "2026-01-01T00:00:00Z"},
                idempotency_key="k3",
            )

    def test_a4_missing_occurred_at_raises(self):
        """Envelope without occurred_at → CoreExecutionError."""
        ex, _, _ = _make_executor(with_applier=True)
        with pytest.raises(CoreExecutionError, match="ENVELOPE_OCCURRED_AT_REQUIRED"):
            ex.execute(
                envelope={"type": "BOOKING_CREATED", "payload": {}},
                idempotency_key="k4",
            )

    def test_a5_no_applier_returns_result_with_warning(self):
        """No applier → ExecuteResult with warning, no exception."""
        ex, port, _ = _make_executor(with_applier=False)
        result = ex.execute(
            envelope=_minimal_envelope(), idempotency_key="k5"
        )
        assert isinstance(result, ExecuteResult)
        assert result.envelope_id == "k5"
        assert result.apply_status is None
        assert result.skill_result.get("warning") == "NO_APPLIER"

    def test_a6_event_appended_to_log(self):
        """After execute(), event is appended to the event log port."""
        ex, port, _ = _make_executor(with_applier=False)
        ex.execute(envelope=_minimal_envelope(), idempotency_key="k6")
        envelopes = port.all_envelopes()
        assert len(envelopes) == 1
        assert envelopes[0].envelope_id == "k6"


# ---------------------------------------------------------------------------
# Group B — InMemoryEventLogPort + InMemoryEventLogApplier
# ---------------------------------------------------------------------------

class TestGroupBInMemoryLog:

    def test_b1_append_event_returns_idempotency_key(self):
        """append_event returns the idempotency_key as envelope_id."""
        port = InMemoryEventLogPort()
        eid = port.append_event(envelope={"type": "X"}, idempotency_key="idem-001")
        assert eid == "idem-001"

    def test_b2_all_envelopes_returns_stored(self):
        """all_envelopes returns all appended events in order."""
        port = InMemoryEventLogPort()
        port.append_event(envelope={"type": "A"}, idempotency_key="e1")
        port.append_event(envelope={"type": "B"}, idempotency_key="e2")
        envs = port.all_envelopes()
        assert len(envs) == 2
        assert envs[0].envelope_id == "e1"
        assert envs[1].envelope_id == "e2"

    def test_b3_missing_idempotency_key_raises(self):
        """Empty idempotency_key → ValueError."""
        port = InMemoryEventLogPort()
        with pytest.raises(ValueError):
            port.append_event(envelope={"type": "X"}, idempotency_key="")

    def test_b4_applier_returns_applied(self):
        """append_envelope_result always returns 'APPLIED'."""
        applier = InMemoryEventLogApplier()
        status = applier.append_envelope_result(
            envelope={"type": "X", "envelope_id": "e1"},
            result={"apply_result": "ok"},
        )
        assert status == "APPLIED"

    def test_b5_applier_stores_applied_results(self):
        """InMemoryEventLogApplier.applied() returns all recorded results."""
        applier = InMemoryEventLogApplier()
        applier.append_envelope_result(envelope={"e": "1"}, result={"r": "1"})
        applier.append_envelope_result(envelope={"e": "2"}, result={"r": "2"})
        assert len(applier.applied()) == 2

    def test_b6_applier_projection_set_and_fetch(self):
        """set_projection / fetch_projection round-trips correctly."""
        applier = InMemoryEventLogApplier()
        rows = [{"id": "1", "val": 100}]
        applier.set_projection("bookings_by_tenant", rows)
        result = applier.fetch_projection(
            query_name="bookings_by_tenant", params={}
        )
        assert result == rows


# ---------------------------------------------------------------------------
# Group C — InMemoryStateStorePort
# ---------------------------------------------------------------------------

class TestGroupCStateStore:

    def test_c1_initial_state_is_empty(self):
        """Fresh state store has no keys."""
        store = InMemoryStateStorePort()
        assert store.all_keys() == []

    def test_c2_commit_upserts_stores_state(self):
        """commit_upserts() stores state keyed by booking_id."""
        store = InMemoryStateStorePort()
        store.commit_upserts(
            envelope_id="e1",
            upserts=[{"key": "bk-001", "value": {"status": "ACTIVE"}}],
        )
        assert "bk-001" in store.all_keys()
        row = store.get("bk-001")
        assert row is not None
        assert row["state_json"]["status"] == "ACTIVE"

    def test_c3_multiple_upserts_accumulate_keys(self):
        """Multiple upserts add separate keys."""
        store = InMemoryStateStorePort()
        store.commit_upserts(
            envelope_id="e1",
            upserts=[
                {"key": "bk-001", "value": {"s": "A"}},
                {"key": "bk-002", "value": {"s": "B"}},
            ],
        )
        assert len(store.all_keys()) == 2

    def test_c4_ensure_schema_does_not_raise(self):
        """ensure_schema() is a no-op in memory (no exception)."""
        store = InMemoryStateStorePort()
        store.ensure_schema()  # should not raise


# ---------------------------------------------------------------------------
# Group D — Idempotency: Duplicate Event Handling
# ---------------------------------------------------------------------------

class TestGroupDIdempotency:

    def test_d1_same_key_produces_same_envelope_id(self):
        """Same idempotency_key → same envelope_id each time."""
        port = InMemoryEventLogPort()
        eid1 = port.append_event(envelope={"type": "A"}, idempotency_key="idem-X")
        eid2 = port.append_event(envelope={"type": "A"}, idempotency_key="idem-X")
        assert eid1 == eid2 == "idem-X"

    def test_d2_different_keys_produce_different_ids(self):
        """Different idempotency_keys → different envelope_ids."""
        port = InMemoryEventLogPort()
        eid1 = port.append_event(envelope={"type": "A"}, idempotency_key="idem-1")
        eid2 = port.append_event(envelope={"type": "A"}, idempotency_key="idem-2")
        assert eid1 != eid2

    def test_d3_executor_no_applier_two_calls_two_events(self):
        """Two execute() calls → two events in the log."""
        ex, port, _ = _make_executor(with_applier=False)
        ex.execute(envelope=_minimal_envelope(), idempotency_key="idem-a")
        ex.execute(envelope=_minimal_envelope(), idempotency_key="idem-b")
        assert len(port.all_envelopes()) == 2

    def test_d4_execute_result_is_frozen_dataclass(self):
        """ExecuteResult is frozen for immutability."""
        ex, _, _ = _make_executor(with_applier=False)
        result = ex.execute(envelope=_minimal_envelope(), idempotency_key="frozen-test")
        # frozen dataclass → cannot set attributes
        with pytest.raises((AttributeError, TypeError)):
            result.envelope_id = "new-id"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Group E — CI Guard: Environment + Env-Var Contract
# ---------------------------------------------------------------------------

class TestGroupECiGuard:

    def test_e1_ihouse_env_is_test(self):
        """IHOUSE_ENV is 'test' (CI safety invariant)."""
        assert os.environ.get("IHOUSE_ENV") == "test"

    def test_e2_supabase_url_set(self):
        """SUPABASE_URL is set (prevents accidental blank-config errors)."""
        assert os.environ.get("SUPABASE_URL", "").startswith("http")

    def test_e3_dev_mode_is_recognizable(self):
        """IHOUSE_DEV_MODE is either 'true', 'false', or unset — never 'production'."""
        val = os.environ.get("IHOUSE_DEV_MODE", "false").lower()
        assert val in ("true", "false", "")

    def test_e4_core_executor_module_importable(self):
        """core.executor is importable (smoke-tests import chain)."""
        import importlib
        mod = importlib.import_module("core.executor")
        assert hasattr(mod, "CoreExecutor")
        assert hasattr(mod, "CoreExecutionError")
