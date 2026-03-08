# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> It is updated every few phases to reflect what we've learned and where we're headed.
> Last updated: Phase 64 closed. [Claude]


## Completed

Phase 21 — External OTA ingestion boundary defined.
Phase 22 — OTA adapter layer introduced with normalization and validation.
Phase 23 — Semantic classification layer introduced for OTA events.
Phase 24 — OTA modification semantic recognition (MODIFY) with deterministic reject-by-default.
Phase 25 — OTA modification resolution rules closed.
Phase 26 — OTA payload contract verification across providers.
Phase 27 — Multi-OTA adapter architecture (shared pipeline, multi-provider registry, Booking.com + Expedia scaffold).
Phase 28–33 — (See phase-timeline.md for full history.)
Phase 34 — OTA canonical emitted event alignment discovery.
Phase 35 — OTA canonical emitted event alignment implementation (BOOKING_CREATED, BOOKING_CANCELED skills).
Phase 36 — Business identity canonicalization (booking_id = {source}_{reservation_ref} verified and locked).
Phase 37 — External event ordering protection discovery.
Phase 38 — Dead Letter Queue implemented (ota_dead_letter table, dead_letter.py).
Phase 39 — DLQ controlled replay (replay_dlq_row, idempotency, outcome persistence).
Phase 40–49 — (See phase-timeline.md for full history.)
Phase 50 — BOOKING_AMENDED event handling: DDL migration, apply_envelope branch, E2E verified.
Phase 51–57 — (See phase-timeline.md for full history.)
Phase 58 — POST /webhooks/{provider} endpoint: signature verify + validate + ingest.
Phase 59 — FastAPI app entrypoint (src/main.py), GET /health, uvicorn runner.
Phase 60 — Request logging middleware: X-Request-ID, duration_ms, structured logging.
Phase 61 — JWT auth middleware: verify_jwt, tenant_id from sub claim, 403 on failure.
Phase 62 — Per-tenant rate limiting: sliding window, IHOUSE_RATE_LIMIT_RPM, 429 + Retry-After.
Phase 63 — OpenAPI docs: BearerAuth scheme, response schemas, /docs + /redoc enriched.
Phase 64 — Enhanced health check: Supabase ping, DLQ count, ok/degraded/unhealthy (503).


---

## Upcoming — Near Term

These are concrete next-phase candidates based on current system state.


### Phase 65 — Financial Data Foundation

Goal:
Begin the financial layer without overloading booking_state.
See `docs/core/improvements/future-improvements.md` → Financial Model Foundation.

Proposed scope:
- Extract and preserve financial fields from all 5 OTA adapter payloads
  (total_price, currency, ota_commission, taxes, fees, net_to_property, etc.)
- Define `BookingFinancialFacts` dataclass — immutable, validated
- Add `source_confidence`: FULL / PARTIAL / ESTIMATED per provider
- No DB write yet — dataclass only in this phase

Constraints:
- booking_state must NEVER contain financial calculations (invariant locked Phase 62+)
- Financial data is provider-specific — no uniform field assumption
- Separate financial data may arrive via Finance APIs (not only webhooks)

---

## Medium Term

These are directions we expect to reach within 10-15 phases from now.


### Operational Observability Layer

Structured logging, ingestion metrics, and DLQ alerting across all OTA adapters.

Will cover:
- Rejection rates by provider and event type
- DLQ accumulation trends
- Replay success/failure rates


### OTA Ingestion Replay Harness

Deterministic replay tools to simulate historical OTA event streams against the canonical pipeline. Used for regression testing and incident recovery.


### External Integration Test Harness

End-to-end verification of OTA ingestion from the provider webhook boundary through to Supabase state, covering rejection scenarios, dedup, and replay safety.


### BOOKING_AMENDED Support (Future)

Full deterministic amendment support. Can only begin after:
- multiple OTA providers are live
- ordering buffer or DLQ retry exists
- out-of-order protections are proven in production
- amendment classification is deterministic

Until then: MODIFY → deterministic reject-by-default.


---

## Future OTA Evolution — Amendment Handling

MODIFY remains deterministic reject-by-default.

This section tracks the formal requirements for BOOKING_AMENDED.
See `improvements/future-improvements.md` for the detailed backlog entry.

Requirements before BOOKING_AMENDED can be introduced:

1. Deterministic amendment classification — adapters must distinguish safe amendments from ambiguous modifications
2. Reservation identity stability — booking_id must be stable across amendment events
3. State-safe amendment application — apply_envelope must safely transition previous_state → amended_state
4. Out-of-order protection — amendments must not corrupt state if events arrive late
5. Projection safety — event log must correctly rebuild amended reservations from history