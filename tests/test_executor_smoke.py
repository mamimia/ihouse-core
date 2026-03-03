from __future__ import annotations

import pytest

from core.executor import CoreExecutor, CoreExecutionError
from core.testing.in_memory_event_log import InMemoryEventLogApplier, InMemoryEventLogPort
from core.testing.in_memory_state_store import InMemoryStateStorePort


def test_no_route_raises_core_error():
    event_port = InMemoryEventLogPort()
    applier = InMemoryEventLogApplier()
    state = InMemoryStateStorePort()

    ex = CoreExecutor(
        event_log_port=event_port,
        event_log_applier=applier,
        state_store=state,
        replay_mode=False,
    )

    with pytest.raises(CoreExecutionError):
        ex.execute(
            envelope={
                "type": "SOME_UNKNOWN_EVENT",
                "payload": {"x": 1},
                "occurred_at": "2020-01-01T00:00:00Z",
            },
            idempotency_key="t1",
        )
