from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.api.ingest import IngestAPI
from core.testing.in_memory_event_log import InMemoryEventLogPort


class _FakeExecutor:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, *, envelope, idempotency_key=None):
        self.calls.append(
            {
                "envelope": dict(envelope),
                "idempotency_key": idempotency_key,
            }
        )
        return SimpleNamespace(
            envelope_id="env_001",
            apply_status="APPLIED",
        )


def test_append_event_rejects_missing_executor_wiring() -> None:
    ingest = IngestAPI(db=InMemoryEventLogPort(), executor=None)

    with pytest.raises(RuntimeError, match="INGEST_EXECUTOR_REQUIRED"):
        ingest.append_event(
            {
                "type": "BOOKING_CREATED",
                "payload": {"booking_id": "b_001"},
                "occurred_at": "2026-03-07T00:00:00Z",
            },
            idempotency_key="evt_001",
        )


def test_append_event_delegates_to_executor_only() -> None:
    executor = _FakeExecutor()
    ingest = IngestAPI(db=InMemoryEventLogPort(), executor=executor)

    envelope = {
        "type": "BOOKING_CREATED",
        "payload": {"booking_id": "b_001"},
        "occurred_at": "2026-03-07T00:00:00Z",
    }

    result = ingest.append_event(envelope, idempotency_key="evt_001")

    assert result.event_id == "env_001"
    assert result.apply_status == "APPLIED"
    assert executor.calls == [
        {
            "envelope": envelope,
            "idempotency_key": "evt_001",
        }
    ]
