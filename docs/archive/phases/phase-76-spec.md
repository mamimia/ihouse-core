# Phase 76 — occurred_at vs recorded_at Separation

**Status:** Closed
**Prerequisite:** Phase 75 (API Error Standards)
**Date Closed:** 2026-03-09

## Problem Solved

Before this phase, all timestamps in the system were called `occurred_at` — but that term was overloaded:
- The OTA-provided business event time (when the booking was made)
- The server ingestion time (when WE received and processed it)

These are fundamentally different and should be tracked separately for:
- SLA monitoring (how fast are we processing incoming events?)
- Chronological ordering (OTA timestamps can be stale or out of order)
- Audit trails (when did we first see this event?)

## Solution

| Field | Meaning | Source |
|-------|---------|--------|
| `occurred_at` | Business event time from OTA provider | OTA payload — untrusted |
| `recorded_at` | Server ingestion timestamp | Set by OUR server, always UTC now |

`recorded_at` is **always** set by the server at ingestion time in `service.py`. It is **never** overridable by the OTA provider payload.

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/schemas.py` | MODIFIED — `CanonicalEnvelope.recorded_at: Optional[str] = None` |
| `src/adapters/ota/service.py` | MODIFIED — stamps `recorded_at = utcnow()` on every envelope_dict |
| `tests/test_recorded_at_separation_contract.py` | NEW — 12 contract tests |

## Invariants

- `recorded_at` is always server UTC clock — never from OTA payload
- `recorded_at` always ends with `Z` (UTC marker)
- `occurred_at` is unchanged — still from OTA provider
- No schema migration needed (Supabase `apply_envelope` accepts extra fields gracefully)

## Result

**545 tests pass, 2 skipped.**
