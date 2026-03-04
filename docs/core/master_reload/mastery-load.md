# iHouse Core — Master Reload (Mastery Load)

## Purpose
Single deterministic reload entrypoint for every new session.
Loads authority, current phase, and invariants before any edits.

## Hard Rules
1) Repository docs are authoritative. Chat memory is not.
2) Read full files. Do not partially edit.
3) Overwrite full files only, except append-only files.
4) phase-timeline.md is append-only. Never rewrite prior sections.
5) If docs and DB behavior conflict, stop and resolve drift first.

## Reload Order
1) docs/core/session_protocol/session-start-protocol.md
2) docs/core/behavioral-calibration.md
3) docs/core/system-identity.md
4) docs/core/vision.md
5) docs/core/canonical-event-architecture.md
6) docs/core/live-system.md
7) docs/core/current-snapshot.md
8) docs/core/construction-log.md
9) docs/core/operating-constitution.md
10) docs/core/project-spine-protocol.md
11) docs/core/phase-timeline/phase-timeline.md

## What To Confirm During Reload
1) Canonical event source is Supabase public.event_log
2) Single atomic write gate is apply_envelope RPC with idempotency and ALREADY_APPLIED on replay
3) booking_state is a projection derived from event_log, and the canonical real-time read model
4) Availability overlap scope is (tenant_id, property_id)
5) Range semantics are half-open: [check_in, check_out)
6) Active for availability: status IS DISTINCT FROM 'canceled' (NULL is active for legacy rows)
7) Valid stay rule: check_out > check_in

## After Reload
1) Identify latest closed phase in construction-log.md
2) Confirm current open phase in current-snapshot.md
3) Continue work only inside that open phase scope
