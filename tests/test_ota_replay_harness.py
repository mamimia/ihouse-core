from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from adapters.ota.service import ingest_provider_event
from core.executor import CoreExecutor


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_envelope_to_core_dict(envelope: Any) -> Dict[str, Any]:
    raw = asdict(envelope)
    occurred_at = raw.get("occurred_at")
    if isinstance(occurred_at, datetime):
        raw["occurred_at"] = _iso(occurred_at)
    return raw


class FakeEventLogPort:
    def append_event(self, envelope: Dict[str, Any], *, idempotency_key: str) -> str:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        return idempotency_key.strip()


class FakeEventLogApplier:
    def __init__(self) -> None:
        self.seen_envelope_ids: set[str] = set()
        self.calls: list[Dict[str, Any]] = []

    def append_envelope_result(
        self,
        *,
        envelope: Dict[str, Any],
        result: Dict[str, Any],
        emitted_events=None,
    ) -> str:
        envelope_id = str(envelope["envelope_id"])
        self.calls.append(
            {
                "envelope": dict(envelope),
                "result": dict(result),
                "emitted_events": list(emitted_events or []),
            }
        )
        if envelope_id in self.seen_envelope_ids:
            return "ALREADY_APPLIED"
        self.seen_envelope_ids.add(envelope_id)
        return "APPLIED"


def _install_executor_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.executor as executor_module

    def fake_load_json_map(_path):
        name = str(_path)
        if name.endswith("kind_registry.core.json"):
            return {
                "BOOKING_CREATED": "booking_created",
                "BOOKING_CANCELED": "booking_canceled",
            }
        if name.endswith("skill_exec_registry.core.json"):
            return {
                "booking_created": "fake.skills.booking_created",
                "booking_canceled": "fake.skills.booking_canceled",
            }
        raise AssertionError(f"Unexpected registry path: {name}")

    def fake_run_skill(module_path: str, payload: Dict[str, Any]):
        if module_path == "fake.skills.booking_created":
            return {
                "events_to_emit": [],
                "state_upserts": [],
                "apply_result": "APPLIED",
            }
        if module_path == "fake.skills.booking_canceled":
            return {
                "events_to_emit": [],
                "state_upserts": [],
                "apply_result": "APPLIED",
            }
        raise AssertionError(f"Unexpected skill module: {module_path}")

    monkeypatch.setattr(executor_module, "_load_json_map", fake_load_json_map)
    monkeypatch.setattr(executor_module, "_run_skill", fake_run_skill)


def _make_executor(monkeypatch: pytest.MonkeyPatch):
    _install_executor_stubs(monkeypatch)
    applier = FakeEventLogApplier()
    executor = CoreExecutor(
        event_log_port=FakeEventLogPort(),
        event_log_applier=applier,
        state_store=None,
        replay_mode=True,
    )
    return executor, applier


def _bookingcom_payload(*, event_id: str, event_type: str) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "reservation_id": "res_001",
        "property_id": "prop_001",
        "occurred_at": "2026-03-07T00:00:00",
        "event_type": event_type,
    }


def test_replay_harness_booking_created_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    executor, applier = _make_executor(monkeypatch)

    envelope = ingest_provider_event(
        provider="bookingcom",
        payload=_bookingcom_payload(event_id="evt_create_001", event_type="created"),
        tenant_id="tenant_001",
    )

    result = executor.execute(
        envelope=_canonical_envelope_to_core_dict(envelope),
        idempotency_key=envelope.idempotency_key,
    )

    assert envelope.type == "BOOKING_CREATED"
    assert result.envelope_id == "evt_create_001"
    assert result.apply_status == "APPLIED"
    assert len(applier.calls) == 1


def test_replay_harness_booking_canceled_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    executor, applier = _make_executor(monkeypatch)

    envelope = ingest_provider_event(
        provider="bookingcom",
        payload=_bookingcom_payload(event_id="evt_cancel_001", event_type="cancelled"),
        tenant_id="tenant_001",
    )

    result = executor.execute(
        envelope=_canonical_envelope_to_core_dict(envelope),
        idempotency_key=envelope.idempotency_key,
    )

    assert envelope.type == "BOOKING_CANCELED"
    assert result.envelope_id == "evt_cancel_001"
    assert result.apply_status == "APPLIED"
    assert len(applier.calls) == 1


def test_replay_harness_duplicate_replay_is_already_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    executor, applier = _make_executor(monkeypatch)

    envelope = ingest_provider_event(
        provider="bookingcom",
        payload=_bookingcom_payload(event_id="evt_dup_001", event_type="created"),
        tenant_id="tenant_001",
    )
    core_env = _canonical_envelope_to_core_dict(envelope)

    first = executor.execute(
        envelope=core_env,
        idempotency_key=envelope.idempotency_key,
    )
    second = executor.execute(
        envelope=core_env,
        idempotency_key=envelope.idempotency_key,
    )

    assert first.apply_status == "APPLIED"
    assert second.apply_status == "ALREADY_APPLIED"
    assert first.envelope_id == second.envelope_id == "evt_dup_001"
    assert len(applier.calls) == 2


def test_replay_harness_modify_is_rejected_before_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_executor_stubs(monkeypatch)

    with pytest.raises(ValueError, match="MODIFY|not supported|rejected"):
        ingest_provider_event(
            provider="bookingcom",
            payload=_bookingcom_payload(event_id="evt_modify_001", event_type="modified"),
            tenant_id="tenant_001",
        )


def test_replay_harness_invalid_payload_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_executor_stubs(monkeypatch)

    with pytest.raises((KeyError, ValueError)):
        ingest_provider_event(
            provider="bookingcom",
            payload={
                "event_id": "evt_invalid_001",
                "event_type": "created",
            },
            tenant_id="tenant_001",
        )
