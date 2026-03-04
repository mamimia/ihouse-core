# iHouse — AI Governance Layer

## Purpose
Prevent drift between code, DB, and docs across sessions and assistants.
Define what an assistant may do, when to stop, and how to verify.

## Authority Model
1) Repository docs are authoritative.
2) Supabase tables and RPC behavior are authoritative runtime truth.
3) Chat output is never authoritative.

## Session Start Contract
An assistant must:
1) Load Master Reload document and follow its order.
2) Confirm current phase from current-snapshot.md and construction-log.md.
3) State the exact open scope before making changes.

## Change Policy
1) Prefer minimal, explicit changes.
2) Overwrite full files only.
3) Append-only files must never be rewritten:
   - docs/core/phase-timeline/phase-timeline.md

## Hard Stop Conditions
Stop and resolve before editing anything if:
1) Docs contradict DB behavior.
2) Code contradicts docs.
3) A canonical predicate is ambiguous.

## Canonical Invariants To Enforce
1) Canonical event source: Supabase public.event_log
2) Single write gate: apply_envelope RPC, idempotent, ALREADY_APPLIED on replay
3) booking_state is a projection derived from event_log and the canonical real-time read model
4) Availability scope: (tenant_id, property_id)
5) Range semantics: [check_in, check_out)
6) Active predicate: status IS DISTINCT FROM 'canceled' (NULL is active for legacy rows)
7) Valid stay: check_out > check_in

## Verification Requirements
Before declaring any phase closed:
1) Deterministic checks pass (DB queries or test harness outputs recorded).
2) current-snapshot.md updated.
3) construction-log.md updated.
4) phase-timeline.md appended with a new section only.
5) No unresolved drift remains.

## Output Format Rules
1) Provide overwrite commands separately per file.
2) Never propose rewriting an append-only file.
3) When unsure, request the exact current file content before modifying.
