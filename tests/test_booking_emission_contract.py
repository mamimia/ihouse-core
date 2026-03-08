"""
Phase 35 — Contract tests for booking_created and booking_canceled skills.

Verifies that:
1. booking_created skill emits a BOOKING_CREATED event with the canonical
   payload shape required by apply_envelope.
2. booking_canceled skill emits a BOOKING_CANCELED event with booking_id.
3. CoreExecutor routes BOOKING_CREATED and BOOKING_CANCELED through the
   new skills (not noop), and the emitted event shape is correct.
"""
from __future__ import annotations

import pytest

from core.skills.booking_created.skill import run as booking_created_run
from core.skills.booking_canceled.skill import run as booking_canceled_run
from core.executor import CoreExecutor, CoreExecutionError
from core.testing.in_memory_event_log import InMemoryEventLogApplier, InMemoryEventLogPort
from core.testing.in_memory_state_store import InMemoryStateStorePort


# ---------------------------------------------------------------------------
# Canonical payload helpers
# ---------------------------------------------------------------------------

def _ota_payload(
    provider: str = "bookingcom",
    reservation_id: str = "res_001",
    property_id: str = "prop_001",
    tenant_id: str = "tenant_001",
    check_in: str = "2026-03-10",
    check_out: str = "2026-03-15",
) -> dict:
    return {
        "provider": provider,
        "reservation_id": reservation_id,
        "property_id": property_id,
        "tenant_id": tenant_id,
        "provider_payload": {"check_in": check_in, "check_out": check_out},
    }


def _expected_booking_id(provider: str, reservation_id: str) -> str:
    return f"{provider}_{reservation_id}"


# ---------------------------------------------------------------------------
# booking_created skill unit tests
# ---------------------------------------------------------------------------

class TestBookingCreatedSkill:

    def test_emits_one_booking_created_event(self) -> None:
        out = booking_created_run(_ota_payload())
        assert len(out.events_to_emit) == 1
        assert out.events_to_emit[0].type == "BOOKING_CREATED"

    def test_emitted_payload_has_all_required_fields(self) -> None:
        """apply_envelope requires: booking_id, tenant_id, source, reservation_ref, property_id."""
        out = booking_created_run(_ota_payload())
        p = out.events_to_emit[0].payload
        assert "booking_id"      in p
        assert "tenant_id"       in p
        assert "source"          in p
        assert "reservation_ref" in p
        assert "property_id"     in p

    def test_emitted_payload_field_values_are_correct(self) -> None:
        out = booking_created_run(_ota_payload())
        p = out.events_to_emit[0].payload
        assert p["source"]          == "bookingcom"
        assert p["reservation_ref"] == "res_001"
        assert p["property_id"]     == "prop_001"
        assert p["tenant_id"]       == "tenant_001"
        assert p["booking_id"]      == _expected_booking_id("bookingcom", "res_001")

    def test_emitted_payload_includes_check_in_check_out(self) -> None:
        out = booking_created_run(_ota_payload())
        p = out.events_to_emit[0].payload
        assert p.get("check_in")  == "2026-03-10"
        assert p.get("check_out") == "2026-03-15"

    def test_apply_result_is_applied(self) -> None:
        out = booking_created_run(_ota_payload())
        assert out.apply_result == "APPLIED"

    def test_no_state_upserts(self) -> None:
        out = booking_created_run(_ota_payload())
        assert out.state_upserts == []

    def test_booking_id_constructed_from_provider_and_reservation_id(self) -> None:
        out = booking_created_run(_ota_payload(provider="expedia", reservation_id="EXP_999"))
        p = out.events_to_emit[0].payload
        assert p["booking_id"] == "expedia_EXP_999"
        assert p["source"] == "expedia"

    def test_check_in_check_out_optional_when_absent(self) -> None:
        payload = {
            "provider": "bookingcom",
            "reservation_id": "res_002",
            "property_id": "prop_001",
            "tenant_id": "tenant_001",
            "provider_payload": {},
        }
        out = booking_created_run(payload)
        p = out.events_to_emit[0].payload
        assert "check_in"  not in p
        assert "check_out" not in p


# ---------------------------------------------------------------------------
# booking_canceled skill unit tests
# ---------------------------------------------------------------------------

class TestBookingCanceledSkill:

    def test_emits_one_booking_canceled_event(self) -> None:
        out = booking_canceled_run({"provider": "bookingcom", "reservation_id": "res_001"})
        assert len(out.events_to_emit) == 1
        assert out.events_to_emit[0].type == "BOOKING_CANCELED"

    def test_emitted_payload_has_booking_id(self) -> None:
        """apply_envelope requires: booking_id."""
        out = booking_canceled_run({"provider": "bookingcom", "reservation_id": "res_001"})
        p = out.events_to_emit[0].payload
        assert "booking_id" in p

    def test_booking_id_value_is_correct(self) -> None:
        out = booking_canceled_run({"provider": "bookingcom", "reservation_id": "res_001"})
        p = out.events_to_emit[0].payload
        assert p["booking_id"] == _expected_booking_id("bookingcom", "res_001")

    def test_apply_result_is_applied(self) -> None:
        out = booking_canceled_run({"provider": "bookingcom", "reservation_id": "res_001"})
        assert out.apply_result == "APPLIED"

    def test_no_state_upserts(self) -> None:
        out = booking_canceled_run({"provider": "bookingcom", "reservation_id": "res_001"})
        assert out.state_upserts == []


# ---------------------------------------------------------------------------
# CoreExecutor routing tests — verifying BOOKING_CREATED and BOOKING_CANCELED
# now route to the real skills (not noop) and produce canonical emitted events
# ---------------------------------------------------------------------------

def _make_executor() -> CoreExecutor:
    return CoreExecutor(
        event_log_port=InMemoryEventLogPort(),
        event_log_applier=InMemoryEventLogApplier(),
        state_store=InMemoryStateStorePort(),
        replay_mode=False,
    )


class TestExecutorRoutingAlignment:

    def test_booking_created_route_produces_emitted_event(self) -> None:
        ex = _make_executor()
        result = ex.execute(
            envelope={
                "type": "BOOKING_CREATED",
                "payload": _ota_payload(),
                "occurred_at": "2026-03-08T00:00:00Z",
            },
            idempotency_key="evt_created_001",
        )
        assert len(result.emitted_events) == 1
        e = result.emitted_events[0]
        assert e["type"] == "BOOKING_CREATED"
        assert e["payload"]["booking_id"] == "bookingcom_res_001"
        assert e["payload"]["source"] == "bookingcom"
        assert e["payload"]["reservation_ref"] == "res_001"

    def test_booking_canceled_route_produces_emitted_event(self) -> None:
        ex = _make_executor()
        result = ex.execute(
            envelope={
                "type": "BOOKING_CANCELED",
                "payload": {"provider": "bookingcom", "reservation_id": "res_001"},
                "occurred_at": "2026-03-08T00:00:00Z",
            },
            idempotency_key="evt_canceled_001",
        )
        assert len(result.emitted_events) == 1
        e = result.emitted_events[0]
        assert e["type"] == "BOOKING_CANCELED"
        assert e["payload"]["booking_id"] == "bookingcom_res_001"

    def test_booking_created_no_longer_routes_to_noop(self) -> None:
        """Guard: the executor must no longer return empty emitted_events for BOOKING_CREATED."""
        ex = _make_executor()
        result = ex.execute(
            envelope={
                "type": "BOOKING_CREATED",
                "payload": _ota_payload(),
                "occurred_at": "2026-03-08T00:00:00Z",
            },
            idempotency_key="evt_created_noop_guard",
        )
        # Pre-Phase-35, this would have been 0 (noop). Now it must be 1.
        assert len(result.emitted_events) != 0, (
            "BOOKING_CREATED must no longer route to noop — emitted_events should not be empty"
        )

    def test_booking_canceled_no_longer_raises_no_route(self) -> None:
        """Guard: the executor must no longer raise NO_ROUTE for BOOKING_CANCELED."""
        ex = _make_executor()
        # Should NOT raise CoreExecutionError with NO_ROUTE
        result = ex.execute(
            envelope={
                "type": "BOOKING_CANCELED",
                "payload": {"provider": "bookingcom", "reservation_id": "res_001"},
                "occurred_at": "2026-03-08T00:00:00Z",
            },
            idempotency_key="evt_canceled_route_guard",
        )
        assert result is not None
