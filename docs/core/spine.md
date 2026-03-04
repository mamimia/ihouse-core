# iHouse Core — Spine

## Status
Authoritative.
Current Phase: Phase 17C — Overlap Rules, Business Dedup, Read Model Inquiry
Last closed: Phase 17B — Canonical Governance Completion

## Purpose
This document is the single entrypoint for reloading context and continuing deterministic execution.
It defines authority, reload order, and non-negotiable invariants.
It does not replace core docs. It tells you exactly which docs to read and in what order.

## Authority
1. Repository state is canonical.
2. Database state is canonical for runtime truth.
3. Chat memory is not authoritative.
4. Do not infer architecture without reading the canonical docs listed below.

## Reload Order
Read in this exact order, every time:
1. docs/core/construction-log.md
2. docs/core/current-snapshot.md
3. docs/core/system-identity.md
4. docs/core/canonical-event-architecture.md
5. docs/core/vision.md

Optional, only when needed:
1. docs/core/live-system.md
2. docs/core/operating-constitution.md
3. docs/core/behavioral-calibration.md
4. docs/core/phase-timeline.md

## Deterministic Continuation Rule
Continue from the latest closed Phase boundary.
Do not restart architecture discussions.
Proceed in deterministic implementation mode within the current open Phase scope only.

## Canonical Execution Contract
1. Supabase public.event_log is the single canonical event store.
2. apply_envelope RPC is the single atomic write gate.
3. booking_state is a projection derived from event_log, and the canonical read model for queries.
4. The application layer must not fabricate state mutations outside apply_envelope.

## Availability Canon
Scope:
tenant_id + property_id

Range semantics:
[check_in, check_out)

Valid stay rule:
check_out > check_in

Overlap predicate:
existing.check_in < new.check_out AND new.check_in < existing.check_out

Active booking predicate for availability:
status IS DISTINCT FROM 'canceled'

Interpretation:
1. A booking that starts on the previous booking's check_out date is allowed.
2. status NULL is treated as active for legacy tolerance.
3. New rows should write status = 'active' by default.

## Hard Rules
1. Docs must match code and DB semantics.
2. No semantic drift between queries, indexes, constraints, and docs.
3. All production mutations must flow through Supabase apply_envelope.
4. Prefer terminal execution and pasted terminal output for verification.
5. Read full files before modifying them.
6. Overwrite full files only, never partial edits.

## Standard Reload Commands
sed -n '1,260p' docs/core/construction-log.md
sed -n '1,260p' docs/core/current-snapshot.md
sed -n '1,260p' docs/core/system-identity.md
sed -n '1,260p' docs/core/canonical-event-architecture.md
sed -n '1,260p' docs/core/vision.md

## Phase Closure Protocol
1. Ensure deterministic validation completed.
2. Update docs/core/construction-log.md
3. Append a new section to docs/core/phase-timeline.md
4. git status is clean except intended changes
5. git add
6. git commit with Phase label
7. git push

## Scope Guard
If Phase 17C is active:
Only overlap rules, business dedup, and read model inquiry work is allowed.
All other lifecycle expansions are out of scope unless a new Phase is opened and recorded.
