"""
core.db

PHASE 8.5 – Internal Database Layer

⚠️  INTERNAL USE ONLY

Application code must NOT access core.db directly.
All external interaction must go through:

    core.api.IngestAPI
    core.api.QueryAPI

This preserves:
- Determinism
- Event-sourcing guarantees
- Projection isolation
- Phase 7 integrity

Direct DB access outside core is considered a boundary violation.
"""
