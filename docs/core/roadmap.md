# iHouse Core – Roadmap

> [!NOTE]
> This document is a living directional guide, not a binding contract.
> It is updated every few phases to reflect what we've learned and where we're headed.
> Last updated: Phase 77 closed. [Claude]


## Completed

Phase 21 — External OTA ingestion boundary defined.
Phase 22–33 — (See phase-timeline.md for full history.)
Phase 34 — OTA canonical emitted event alignment discovery.
Phase 35 — Alignment implementation (BOOKING_CREATED, BOOKING_CANCELED skills).
Phase 36 — Business identity canonicalization (booking_id locked).
Phase 37–49 — (See phase-timeline.md for full history.)
Phase 50 — BOOKING_AMENDED: DDL, apply_envelope branch, E2E verified.
Phase 51–57 — (See phase-timeline.md for full history.)
Phase 58 — POST /webhooks/{provider}: signature verify + validate + ingest.
Phase 59 — FastAPI entrypoint, GET /health, uvicorn.
Phase 60 — Request logging middleware (X-Request-ID, duration_ms).
Phase 61 — JWT auth middleware (tenant_id from sub, 403 on failure).
Phase 62 — Per-tenant rate limiting (sliding window, 429 + Retry-After).
Phase 63 — OpenAPI enrichment (BearerAuth, response schemas).
Phase 64 — Enhanced health check (Supabase ping, DLQ count, ok/degraded/unhealthy).
Phase 65 — Financial data extraction (BookingFinancialFacts, 5 providers, in-memory).
Phase 66 — Financial persistence (booking_financial_facts Supabase table, financial_writer.py).
Phase 67–76 — (See phase-timeline.md for full history.)
Phase 77 — OTA Schema Normalization (canonical_guest_count, canonical_booking_ref, canonical_property_id, 27 tests).


---

## Forward Planning Context (Phase 78+)

Two major forward-planning notes are locked in `docs/core/improvements/future-improvements.md`:

1. **Product and Architecture Bundle** — visibility, auditability, reconciliation, financial clarity, owner surfaces, operational usefulness.
2. **Adapter Expansion Wave** — Vrbo → Google Vacation Rentals → Traveloka → MakeMyTrip → Despegar.

These are not immediate execution orders. They are direction notes that inform future phase decisions.


---

## Phase 78–107 Forward Plan

### Phase 78–82 — Infrastructure Hardening + Schema Completion

**Phase 78 — Schema Normalization (Dates + Price)**
Extend Phase 77: add `canonical_check_in`, `canonical_check_out`, `canonical_currency`, `canonical_total_price` for all 5 providers. Completes the canonical schema layer.

**Phase 79 — Idempotency Monitoring**
`idempotency_monitor.py`: metrics on duplicate envelope detection, retry storms, anomalies. Uses existing DLQ + ordering_buffer + event_log data.

**Phase 80 — Structured Logging Layer**
`structured_logger.py`: JSON output with `request_id`, `tenant_id`, `provider`, `duration_ms`, `result`. Replaces all stderr print statements. Foundation for future dashboards.

**Phase 81 — Integration Health Dashboard (Foundation)**
`integration_health.py`: per-provider last successful ingest, occurred_at vs recorded_at lag, DLQ counts, buffer counts, reject counts, stale alerts. Surfaces data the system already collects.

**Phase 82 — Admin Query API**
`src/api/admin_router.py` endpoints: `GET /admin/metrics`, `GET /admin/dlq`, `GET /admin/health/providers`, `GET /admin/bookings/{id}/timeline`. First queryable surface for operators.

---

### Phase 83–87 — Adapter Wave 1 + Visibility

**Phase 83 — Vrbo Adapter** *(Tier 1)*
First new adapter after the core set. Closes the largest vacation-rental credibility gap. Standard adapter pattern: normalize → validate → classify → to_canonical_envelope.

**Phase 84 — Reservation Timeline / Audit Trail**
Per-booking story API from existing event_log: created, amended, canceled, buffered, replayed, DLQ events, financial updates. Zero DB schema changes — only reads what already exists.

**Phase 85 — Google Vacation Rentals Adapter** *(Tier 1)*
Distribution surface rather than classic OTA. Critical for discoveryability. Adapter pattern may differ slightly — document the difference explicitly.

**Phase 86 — Conflict Detection Layer**
`conflict_detector.py`: overlap on same property, missing mapping, incomplete canonical coverage, potential overbooking, provider mapping gaps. Visibility only — no writes to booking_state.

**Phase 87 — Tenant Isolation Hardening**
RLS policy audit across all Supabase tables. Verify per-tenant isolation in event_log, booking_state, booking_financial_facts. Add contract tests for cross-tenant data leakage prevention.

---

### Phase 88–92 — Recovery + Southeast Asia + Test Infrastructure

**Phase 88 — Traveloka Adapter** *(Tier 1.5 — Southeast Asia)*
Dominant platform in Thailand and regional SE Asia context. Increases market fit for local operators.

**Phase 89 — OTA Reconciliation Discovery**
Discovery phase only. Map what comparison is possible between iHouse Core state and OTA state without a live API. Define the reconciliation model: what to detect, how to flag, what to correct.

**Phase 90 — External Integration Test Harness**
End-to-end deterministic harness for all current providers (5 core + Vrbo + GVR + Traveloka): webhook → signature → pipeline → Supabase state. Covers rejection, dedup, replay.

**Phase 91 — Replay Harness**
Historical OTA event stream deterministic replay against the canonical pipeline. For incident recovery and regression testing. Builds on DLQ replay infrastructure (Phase 39+).

**Phase 92 — Roadmap + System Audit**
Update all docs: `roadmap.md`, `future-improvements.md`, `current-snapshot.md`. Close gaps between code and documentation. Evaluate next 10-phase direction based on what's been learned.

---

### Phase 93–97 — Financial Layer + Latin America + India

**Phase 93 — Payment Lifecycle / Revenue State Projection**
`payment_lifecycle.py`: financial status states — `guest_paid`, `ota_collecting`, `payout_pending`, `payout_released`, `reconciliation_pending`, `owner_net_pending`. Builds on BookingFinancialFacts without touching booking_state.

**Phase 94 — MakeMyTrip Adapter** *(Tier 2 — India)*
Expands into the Indian travel market. Follows established adapter pattern.

**Phase 95 — Owner Statements Foundation**
`owner_statement.py`: per-property monthly summary, net revenue, payout summary. Read-only layer over financial_facts. First owner-facing surface.

**Phase 96 — Despegar Adapter** *(Tier 2 — Latin America)*
Strongest Latin American travel brand. Completes the Tier 2 adapter wave.

**Phase 97 — OTA Reconciliation Implementation**
Implement the reconciliation model defined in Phase 89. Detection and correction-support layer — never bypasses apply_envelope. Flags drift via admin API.

---

### Phase 98–107 — Product Layer (Operational Completeness)

**Phase 98 — Guest Pre-Arrival / Check-In Intake**
Lightweight intake flow per reservation: contact info, arrival time, agreement, special notes, readiness status.

**Phase 99 — Task Automation for Operations**
Rule-based task layer driven by booking events: BOOKING_CREATED → prep task, checkout tomorrow → cleaning task, amendment → reschedule, cancellation → cancel pending.

**Phase 100 — Owner Statements Full View**
Expand Phase 95 into a complete owner-facing surface: monthly statement, property revenue, net vs gross, payout history, scoped role visibility.

**Phase 101–107 — TBD based on product learning**
Candidates: Tier 3 adapters (Rakuten, Hotelbeds, Hostelworld), advanced financial reporting, outbound channel sync discovery, multi-projection read models, revenue analytics, advanced conflict resolution.


---

## Where We Land After Phase 107

**Adapter coverage:** Booking.com, Airbnb, Expedia, Agoda, Trip.com, Vrbo, Google Vacation Rentals, Traveloka, MakeMyTrip, Despegar. 10 channels. Global + SE Asia + India + LATAM coverage.

**Operational surfaces:** Reservation timeline, integration health dashboard, admin API, conflict detection, reconciliation layer.

**Financial surfaces:** Booking financial facts (persisted), payment lifecycle states, owner statements.

**Product surfaces:** Guest intake, task automation, owner views.

**Architecture:** Canonical core unchanged — `apply_envelope` still the only write authority. All product layers read from or wrap the canonical spine without mutating it.


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