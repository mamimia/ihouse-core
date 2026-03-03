# iHouse Core – Construction Log

## Phase 16
Canonical Domain Event Migration and Financial Grade Enforcement.

### Phase 16A – Canonical Schema Lock (Closed)
Completed:
event_log.kind enforced as event_kind enum
indexes and constraints aligned
booking_state concurrency and last_envelope_id semantics enforced

Outcome:
DB layer constrained and deterministic.

### Phase 16B – Deterministic Core Alignment (Closed)
Completed:
canonical routing registry active
unknown event types rejected
Supabase enforced as the operational runtime mode
commit policy aligned:
commit only after apply_status == APPLIED
no commit during replay

Limitation discovered:
idempotency must be enforced before any duplicate application can mutate the canonical log.

### Phase 16C – Hard Idempotency Gate (Closed)
Completed:
atomic gate added at Supabase boundary via apply_envelope RPC
envelope_received is the idempotency marker
apply_envelope returns:
APPLIED on first application
ALREADY_APPLIED on replay of same envelope_id
no SQLite fallback write path in production ingest surface

Outcome:
financial grade idempotency at the canonical event store boundary.

## Phase 17
Operational Hardening and Canonical Governance.

### Phase 17A – Operational Runner, Secrets, CI, and Smoke Hardening (Closed)
Completed:
canonical local API runner scripts/run_api.sh
dev smoke scripts:
scripts/dev/smoke_http.sh
scripts/dev/curl_event.sh
CI enforcement:
no direct pytest usage
English-only repo content
required canonical scripts exist
CI boots API and runs HTTP smoke
GitHub Actions secret used for IHOUSE_API_KEY

Outcome:
operationally repeatable local and CI runtime with enforced governance.

### Phase 17B – Canonical Governance Completion (Open)
Goals:
finish documentation alignment and remove remaining ambiguity
ensure user self-booking is treated as an external event source through canonical Supabase apply gate
tighten operational playbook and invariants
