# Phase 19 — External Event Ingestion Contract

## Goal
Define the canonical ingestion contract for all external event sources.

All external writes must enter the system through apply_envelope.

Sources include:
- OTA integrations
- manual admin actions
- user self booking flows

The contract must be deterministic and stable.

---

## Canonical Envelope

Every external event must follow this envelope:

{
  envelope_id: UUID,
  tenant_id: UUID,
  source: TEXT,
  event_kind: TEXT,
  event_version: INTEGER,
  occurred_at: TIMESTAMP,
  payload: JSONB
}

Rules:

1) envelope_id must be globally unique
2) tenant_id must exist
3) source must be a known source
4) event_kind must be a supported external event
5) event_version must match the known schema version
6) payload must match the event schema

---

## Deterministic Rejection

apply_envelope must reject envelopes with stable error codes.

Examples:

INVALID_TENANT  
UNKNOWN_SOURCE  
UNKNOWN_EVENT_KIND  
UNSUPPORTED_EVENT_VERSION  
INVALID_PAYLOAD  
ALREADY_APPLIED  

These codes form the external contract.

---

## Idempotency

If envelope_id already exists in event_log:

apply_envelope returns

ALREADY_APPLIED

and performs no mutation.

---

## Scope Boundaries

This phase does NOT include:

- RLS
- replay tooling
- observability
- public APIs

Those belong to later phases.

---

## Exit Criteria

Phase 19 is complete when:

1) canonical envelope format is documented
2) rejection codes are defined
3) apply_envelope enforces deterministic validation
4) external sources use the envelope contract
