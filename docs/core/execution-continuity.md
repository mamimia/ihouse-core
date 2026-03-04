# iHouse Core — Execution Continuity

## Principle
Continue from the latest closed Phase boundary.
Do not restart architecture discussions.
Proceed in deterministic implementation mode.

## Reload Steps
1. Read docs/core/construction-log.md to identify latest closed Phase.
2. Confirm current state in docs/core/current-snapshot.md.
3. Validate invariants in docs/core/canonical-event-architecture.md.
4. Continue only within the declared open/active scope.

## Hard Rules
Docs must match code and DB semantics.
No semantic drift between queries, indexes, and docs.
All production mutations must flow through Supabase apply_envelope.

## Availability Canon
Active predicate:
status IS DISTINCT FROM 'canceled'

Overlap scope:
tenant_id + property_id

Range semantics:
[check_in, check_out)
