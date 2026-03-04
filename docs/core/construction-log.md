# iHouse Core — Construction Log

## Governance Rule — Phase Timeline Synchronization
At the completion of every Phase:
1. Construction Log must be updated.
2. docs/core/phase-timeline/phase-timeline.md must be appended.
3. Phase Timeline is strictly append-only.
4. No historical entry in Phase Timeline may ever be modified or deleted.
5. A Phase is not considered closed until the Phase Timeline has been updated.

---

## Phase 17 — Operational Hardening and Canonical Governance

### Phase 17A — Operational Runner, Secrets, CI, and Smoke Hardening (Closed)
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

### Phase 17B — Canonical Governance Completion (Closed)
Completed:
apply_envelope verified as the single atomic write authority into Supabase
ALREADY_APPLIED replay behavior validated against live duplicate envelope re-apply
STATE_UPSERT formalized as DB-generated internal event
booking_state.last_envelope_id verified and treated as invariant
event_log unique constraint on event_id verified
booking_state primary key uniqueness on booking_id verified
booking_state.last_event_id foreign key integrity to event_log verified
end-to-end determinism revalidated via canonical event_log replay semantics
user self-booking and manual bookings treated as external event sources through canonical apply gate

Outcome:
database is the single source of mutation truth
application layer cannot fabricate state
financial-grade idempotency includes zero duplicate state mutation

### Phase 17C — Overlap Rules, Business Dedup, Read Model Inquiry (Closed)
Completed:
overlap invariant enforced for (tenant_id, property_id) using half-open ranges [check_in, check_out)
business dedup enforced on (tenant_id, source, reservation_ref, property_id)
read-model inquiry enabled for booking lookup and state inspection
cancellation path validated as deterministic state transition

Outcome:
property availability integrity enforced at the canonical DB boundary
stable booking identity prevents duplicate creates
state inspection supported without introducing alternate mutation paths

---

## Phase 18 — Legacy-Tolerant Availability Canon + DB Invariants (Closed)
Completed:
availability canon locked as Option B: active iff status IS DISTINCT FROM 'canceled' (NULL treated as active for legacy)
forward-only writes: BOOKING_CREATED writes status='active', BOOKING_CANCELED sets status='canceled' and bumps version
STATE_UPSERT event_id uniqueness enforced per envelope and event type (no collisions across created/canceled paths)
last_event_id always points to an existing event_log row for applied envelopes
docs synchronized to prevent code-doc drift on availability predicate and overlap semantics

Outcome:
legacy compatibility preserved without backfill
availability semantics are single-source-of-truth and query-stable
event_log and booking_state remain consistent under idempotent replay
