# iHouse Core — Roadmap (Future Phases)

## Purpose
This document is the canonical forward plan for iHouse Core phases beyond the latest closed phase.
It is not history. History lives in docs/core/phase-timeline.md.
This roadmap is allowed to evolve, but must remain consistent with core invariants.

## Phase 19 — External Event Ingestion Contract
Goal:
Stabilize the external write contract into apply_envelope.

Scope:
1) Canonical ingest envelope for all external sources (OTA, manual admin, user self booking)
2) Required fields per event kind
3) Deterministic rejection rules inside apply_envelope
4) Stable error codes returned by apply_envelope (contract)

Exit criteria:
1) Ingest envelope contract documented
2) apply_envelope returns stable error codes for all rejection cases
3) At least one end to end ingest flow validated per source type

## Phase 20 — Tenant Isolation Hardening
Goal:
Make tenant_id a real security boundary.

Scope:
1) RLS on event_log and booking_state
2) SECURITY DEFINER RPC with internal tenant scoping
3) All read functions scoped by tenant_id

Exit criteria:
1) RLS enabled and validated for tenant isolation
2) No cross tenant reads possible through approved read surfaces
3) apply_envelope enforces tenant scoping

## Phase 21 — Deterministic Replay Tooling
Goal:
Make debugging practical without undefined states.

Scope:
1) Replay by tenant
2) Replay by property
3) Replay by booking
4) Clear safety boundaries and deterministic outputs

Exit criteria:
1) Replay functions exist and are documented
2) Replay outputs are deterministic and verifiable
3) Replay cannot bypass tenant isolation
