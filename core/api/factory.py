from __future__ import annotations

from typing import Any

from .ingest import IngestAPI
from .query import QueryAPI


class CoreAPI:
    """
    PHASE 8.8 – Unified Core API (Safe Wiring)

    - Accepts a core-managed DB handle from the caller (composition root)
    - Does NOT create DB internally
    - Keeps determinism/initialization decisions outside the API surface
    """

    def __init__(self, *, db: Any) -> None:
        self._ingest = IngestAPI(db=db)
        self._query = QueryAPI(db=db)

    @property
    def ingest(self) -> IngestAPI:
        return self._ingest

    @property
    def query(self) -> QueryAPI:
        return self._query
