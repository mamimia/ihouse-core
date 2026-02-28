---
name: booking-sync-ingest
description: Ingests booking sync payloads deterministically into core event envelopes. Use when receiving booking sync inputs from external systems and converting them into append-only events.
---

# Booking Sync Ingest

## When to use this skill
1. Caller provides explicit booking sync payload data
2. Need deterministic conversion into event envelope(s)
3. No hidden IO and no implicit reads

## Contract
### Inputs
1. actor
   • actor_id
   • role
2. context
   • run_id
3. payload
   • source (e.g. airbnb, booking)
   • raw (object)
4. idempotency
   • request_id
5. time
   • now_utc (explicit)

### Outputs
1. events_to_emit
   • list of EventEnvelope
2. side_effects
   • none

## Determinism constraints
1. No storage reads
2. No network calls
3. No randomness
4. Output depends only on explicit input

## Resources
1. scripts/booking_sync_ingest.py
