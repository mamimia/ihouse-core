# iHouse Core — Current Snapshot

## Phase
Current:
Phase 18 — Legacy-Tolerant Availability Canon + DB Invariants (Closed)

Last closed:
Phase 18 — Legacy-Tolerant Availability Canon + DB Invariants

## System Type
Deterministic Domain Event Execution Kernel.

External contract is business events only.
Internal mechanics are hidden.

## Canonical Persistence
Supabase is canonical:
public.event_log
public.booking_state

SQLite is not an allowed production write path.

## Canonical Apply Gate
apply_envelope RPC is the single atomic write authority into event_log.
It writes envelope_received once per envelope_id and returns ALREADY_APPLIED on replay.

booking_state is materialized by DB-generated internal events (STATE_UPSERT).

## Availability Invariants
Scope:
(tenant_id, property_id)

Range:
[check_in, check_out)

Overlap:
existing.check_in < new.check_out AND new.check_in < existing.check_out

Active predicate (Option B, legacy tolerant):
status IS DISTINCT FROM 'canceled'

## Business Identity
Stable business identity:
tenant_id + source + reservation_ref + property_id

## Operational Canon
Local API runner:
scripts/run_api.sh

Dev smoke:
scripts/dev/smoke_http.sh
scripts/dev/curl_event.sh

CI governance:
no direct pytest usage
English-only repo content
boot API then run HTTP smoke

Secrets:
IHOUSE_API_KEY provided via GitHub Actions secrets.
