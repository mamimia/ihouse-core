# iHouse Core — Session Start Protocol

## Purpose
This protocol prevents context drift across sessions.
It defines how a new session loads authority, confirms current phase, and proceeds deterministically.

## Hard Rules
1) Repository files are authoritative. Chat memory is not.
2) Do not modify any file before completing the Reload sequence.
3) Phase Timeline is append-only. Never overwrite it. Only append new entries.
4) If any contradiction exists between docs or DB behavior, stop and resolve drift first.
5) No hidden refactors. Full file overwrites only, except append-only files.

## Session Start Sequence
Step 1: Run Master Reload
Read and execute:
docs/core/master_reload/mastery-load.md

Step 2: Confirm Phase Boundary
From construction-log.md identify the latest closed phase.
From current-snapshot.md confirm the currently open phase.

Step 3: Confirm Canonical Execution Authority
Canonical event source: Supabase public.event_log
Single write gate: apply_envelope RPC
booking_state is a projection materialized by DB logic, not an independent source of truth

Step 4: Confirm Booking Availability Invariants
Overlap scope: (tenant_id, property_id)
Range semantics: [check_in, check_out)
Valid stay: check_out > check_in
Active for availability: status IS DISTINCT FROM 'canceled' (NULL is active for legacy rows)

Step 5: Work Mode
Continue only within the currently open phase scope.
Prefer DB level verification:
event_log rows
booking_state rows
apply_envelope status codes

## Phase Closure Checklist
1) Validation executed and outputs captured
2) construction-log.md updated
3) phase-timeline.md appended (no edits to old sections)
4) current-snapshot.md updated to next open phase
5) Any other core docs updated only if needed to prevent drift

## Future Phases Reference
See docs/core/roadmap.md.
