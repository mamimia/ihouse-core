"""
core.api

PHASE 8 – Core API Surface

This package defines formal application boundaries:
- CoreAPI: unified entry point
- IngestAPI: append immutable events only
- QueryAPI: read-only access to projections via named queries only

Rules:
- No projection logic
- No side effects
- Preserve Phase 7 determinism guarantees
"""

from .factory import CoreAPI
from .ingest import IngestAPI, IngestResult
from .query import QueryAPI, QueryResult

__all__ = [
    "CoreAPI",
    "IngestAPI",
    "IngestResult",
    "QueryAPI",
    "QueryResult",
]
