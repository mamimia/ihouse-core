from __future__ import annotations

from typing import Optional

from core.event_log import EventLog
from core.executor import CoreExecutor
from core.ports import EventLogPort, StateStorePort

from .ingest import IngestAPI
from .query import QueryAPI


class CoreAPI:
    """
    Phase 14:
    Core owns deterministic execution.
    No adapter-level execution.
    Single commit point lives in CoreExecutor.
    """

    def __init__(
        self,
        *,
        db: EventLogPort,
        event_log_applier: Optional[EventLog] = None,
        state_store: Optional[StateStorePort] = None,
        replay_mode: bool = False,
    ) -> None:

        executor: Optional[CoreExecutor] = None

        if event_log_applier is not None:
            executor = CoreExecutor(
                event_log_port=db,
                event_log_applier=event_log_applier,
                state_store=state_store,
                replay_mode=replay_mode,
            )

        self._ingest = IngestAPI(
            db=db,
            executor=executor,
        )

        self._query = QueryAPI(db=db)

    @property
    def ingest(self) -> IngestAPI:
        return self._ingest

    @property
    def query(self) -> QueryAPI:
        return self._query
