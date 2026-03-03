# iHouse Core – Current Snapshot

## Phase
Current:
Phase 17B – Canonical Governance Completion

Last closed:
Phase 17A – Operational Runner, Secrets, CI, and Smoke Hardening

## System Type
Deterministic Domain Event Execution Kernel.

External contract is business events only.
Internal mechanics are hidden.

## Canonical Business Event Types
BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

## External Event Sources
External producers include:
channel managers
internal admin tools
user self-booking and manual bookings

All sources must emit canonical business events through the same canonical path.

## Execution Flow
Ingest envelope
→ CoreExecutor routes by canonical registry
→ skill executes deterministically
→ apply_envelope RPC performs atomic write into Supabase event_log
→ StateStore commit runs only when apply_status == APPLIED
→ replay_mode forbids commits

## Persistence
Supabase public.event_log is canonical event store.
Supabase public.booking_state is canonical state store.

SQLite is not allowed as a production write path.

## Idempotency
Hard idempotency is enforced at the database boundary:
apply_envelope returns ALREADY_APPLIED if envelope_received already exists for the envelope_id.
This prevents duplicate envelope application.

## Determinism
Rebuild and replay must derive truth from Supabase event_log only.
Given the same ordered event_log, state must be identical.

## Operational Canon
Local API runner:
scripts/run_api.sh

Dev smoke:
scripts/dev/smoke_http.sh
scripts/dev/curl_event.sh

CI governance:
no direct pytest invocation
English-only repo content
boot API then run HTTP smoke

Secrets:
IHOUSE_API_KEY is provided via GitHub Actions secret in CI.
