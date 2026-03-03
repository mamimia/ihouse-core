from __future__ import annotations

from typing import Any

from core.api.factory import CoreAPI
from core.executor import CoreExecutor
from core.testing.in_memory_event_log import InMemoryEventLogApplier, InMemoryEventLogPort
from core.testing.in_memory_state_store import InMemoryStateStorePort


def build_test_core() -> CoreAPI:
    db_port: Any = InMemoryEventLogPort()
    applier = InMemoryEventLogApplier()
    state = InMemoryStateStorePort()

    executor = CoreExecutor(
        event_log_port=db_port,
        event_log_applier=applier,
        state_store=state,
        replay_mode=False,
    )

    return CoreAPI(
        db=db_port,
        event_log_applier=applier,
        state_store=state,
        replay_mode=False,
    )
