# iHouse Core — Phase Roadmap (Phases 68–87)

**Document type:** Non-binding directional guide.
**Authority:** `future-improvements.md` is the canonical backlog. This document organizes it into sequenced phases.
**Rule:** Any phase here can be reordered, skipped, or replaced based on product direction. This is a compass, not a contract.

**Last updated:** Phase 67 closed (2026-03-09). Current test count: 396 passed, 2 skipped.

---

## Principle: What Comes Next?

The system has three open threads after Phase 67:

1. **Financial Layer** — Foundations built (65-67). Remaining: Finance API expansion, owner statements, revenue analytics.
2. **Reliability Layer** — DLQ replay, ordering guarantees, idempotency hardening.
3. **Amendment Layer** — BOOKING_AMENDED support (currently 4/10 prerequisites met).

The roadmap below sequences these threads with minimal risk. Each phase is small, reversible, and independently testable.

---

## Phase 68 — DLQ Controlled Replay

**Priority:** High (open backlog item since Phase 38)
**Dependency:** Phase 38 (DLQ infrastructure already exists)

**Goal:** Allow operators to safely replay specific rows from `ota_dead_letter` back through the canonical ingest pipeline (skill → apply_envelope). Never automatic — manually triggered only.

**Key rules:**
- Replay must never bypass `apply_envelope`
- Replay must be idempotent — re-running the same DLQ row must be safe
- Write `replayed_at`, `replay_result`, `replay_trace_id` back to the DLQ row

**Expected deliverables:**
- `src/adapters/ota/dlq_replayer.py`
- Migration: add `replayed_at`, `replay_result`, `replay_trace_id` to `ota_dead_letter`
- `tests/test_dlq_replayer_contract.py`

---

## Phase 69 — DLQ Observability

**Priority:** Medium
**Dependency:** Phase 68

**Goal:** Add operational visibility to the DLQ. Currently queryable but silent.

**Expected deliverables:**
- Daily summary query: rejection counts by `event_type` and `rejection_code`
- `GET /dlq/summary` endpoint (read-only, JWT auth)
- `tests/test_dlq_summary_contract.py`

---

## Phase 70 — Event Time vs System Time Separation

**Priority:** Medium (open backlog since Phase 20 era)

**Goal:** Separate `occurred_at` (business time, from OTA payload) from `recorded_at` (system time, when event entered iHouse). Use `recorded_at` for canonical ordering. Preserve `occurred_at` for business history and auditing.

**Expected deliverables:**
- DDL migration: add `occurred_at` column to `event_log` (nullable, populated from OTA payload)
- Update `apply_envelope` to write `occurred_at`
- Update `CanonicalEnvelope` schema to carry `occurred_at`
- `tests/test_event_time_contract.py`

---

## Phase 71 — booking_id Stability Layer

**Priority:** Medium (open backlog since Phase 36)

**Goal:** Guard against OTA provider changes to `reservation_ref` format that would break the canonical `{source}_{reservation_ref}` identity rule.

**Expected deliverables:**
- `src/adapters/ota/booking_id_normalizer.py` — canonicalizes reservation_ref before constructing booking_id
- Per-provider normalization rules (strip prefix, lowercase, etc.)
- `tests/test_booking_id_normalizer_contract.py`

---

## Phase 72 — Financial Facts: List Endpoint

**Priority:** Medium
**Dependency:** Phase 67

**Goal:** `GET /financial/` (paginated list) — returns all financial_facts for the authenticated tenant. Useful for owner statements and revenue dashboards.

**Expected deliverables:**
- Extend `financial_router.py` with `GET /financial/` (page/limit query params)
- Tenant-scoped, ordered by `recorded_at DESC`
- `tests/test_financial_list_contract.py`

---

## Phase 73 — BOOKING_AMENDED: Prerequisite 5 — Normalized AmendmentPayload

**Priority:** Medium
**Dependency:** Phase 71 (booking_id stability)

**Goal:** Define the canonical `AmendmentPayload` schema (provider-agnostic). This is prerequisite 5/10 for full BOOKING_AMENDED support.

**Key constraint:** Must not change the MODIFY → reject-by-default behavior. This is purely a schema definition phase.

**Expected deliverables:**
- `src/adapters/ota/amendment_schema.py` — `AmendmentPayload` dataclass
- Per-provider amendment field extraction (5 providers)
- `tests/test_amendment_schema_contract.py`

---

## Phase 74 — BOOKING_AMENDED: Prerequisite 6 — DDL + apply_envelope Branch

**Priority:** Medium
**Dependency:** Phase 73

**Goal:** Add `BOOKING_AMENDED` to the `event_kind` enum and implement the `apply_envelope` BOOKING_AMENDED branch with ACTIVE-state guard.

**Key rules:**
- Amendment only allowed when booking is in ACTIVE state
- Idempotency key must be unique per amendment event
- Must not break existing BOOKING_CREATED / BOOKING_CANCELED flows

**Expected deliverables:**
- Supabase migration: update `event_kind` enum
- Updated `apply_envelope` stored procedure
- `tests/test_booking_amended_apply_contract.py`

---

## Phase 75 — BOOKING_AMENDED: Prerequisite 7-10 + Full Pipeline

**Priority:** Medium
**Dependency:** Phase 74

**Goal:** Complete remaining BOOKING_AMENDED prerequisites and wire the full pipeline.

**Remaining prerequisites (7-10):**
- Replay ordering rule for amendments
- Idempotency key structure for amendments
- `MODIFY` re-classification in `semantics.py`
- E2E test: OTA amendment webhook → `apply_envelope` BOOKING_AMENDED APPLIED

**Expected deliverables:**
- Updated `semantics.py`
- `tests/test_booking_amended_e2e.py` (currently skipped, now enabled)
- Full suite green with BOOKING_AMENDED

---

## Phase 76 — OTA Schema Normalization: Timezone

**Priority:** Medium (open backlog since Phase 21)

**Goal:** Normalize `occurred_at` timestamps to UTC across all 5 OTA providers. Currently each provider may send different timezone formats.

**Expected deliverables:**
- `src/adapters/ota/time_normalizer.py`
- Per-provider timezone rules
- `tests/test_time_normalizer_contract.py`

---

## Phase 77 — OTA Schema Normalization: Currency + Guest Counts

**Priority:** Medium
**Dependency:** Phase 76

**Goal:** Normalize currency codes (ISO 4217 validation) and guest count semantics across providers.

---

## Phase 78 — Financial Facts: Owner Statement Projection

**Priority:** High (product direction)
**Dependency:** Phase 72

**Goal:** Introduce `owner_statement` Supabase table — monthly aggregation of financial facts per property per owner. This is the product foundation for the owner statement feature.

**Expected deliverables:**
- `owner_statement` table (append-only, RLS)
- `src/adapters/financial/statement_projector.py`
- `GET /statements/{property_id}` endpoint
- `tests/test_statement_projector_contract.py`

---

## Phase 79 — Rate Limiting: Per-Provider Limits

**Priority:** Medium

**Goal:** Current rate limiting is per-tenant (Phase 62). Add per-provider limits: some OTA providers send burst traffic. Apply independent sliding window per `(tenant_id, provider)` pair.

---

## Phase 80 — Idempotency Monitoring

**Priority:** Medium (open backlog since Phase 20 era)

**Goal:** Add metrics for duplicate envelope detection. Expose counts via health endpoint or new `/metrics` endpoint.

**Expected deliverables:**
- Counter for `ALREADY_EXISTS` and `ALREADY_EXISTS_BUSINESS` results
- Surface in `GET /health` or new `GET /metrics`
- `tests/test_idempotency_metrics_contract.py`

---

## Phase 81 — Multi-Projection Support: Availability Read Model

**Priority:** Low (open backlog)

**Goal:** Introduce an `availability_state` projection table driven from the canonical event stream. First step: track which booking periods a property has active bookings.

---

## Phase 82 — Replay Snapshot Optimization

**Priority:** Low (open backlog)

**Goal:** When `event_log` grows large, introduce periodic replay snapshots to reduce full rebuild cost. Snapshots are read-only artifacts; the event log remains the canonical authority.

---

## Phase 83 — Webhook Replay Protection

**Priority:** Medium

**Goal:** Detect and reject replayed OTA webhooks (same event sent twice from OTA side, with different request_id). Complement to existing business idempotency.

**Expected deliverables:**
- `webhook_replay_log` table (event_id, provider, received_at)
- Replay check before ingest
- `tests/test_webhook_replay_protection_contract.py`

---

## Phase 84 — Finance API: Provider Finance API Ingestion

**Priority:** High (product direction)

**Goal:** Some OTA providers expose separate Finance APIs that deliver more complete financial data than reservation webhooks. This phase adds an ingestion path for Booking.com Finance API responses.

**Key constraint:** Financial data from Finance APIs must still flow through the canonical event stream — never written directly to `booking_financial_facts`.

---

## Phase 85 — Tenant Management API

**Priority:** Medium

**Goal:** Add tenant provisioning endpoints. Currently `tenant_id` comes from JWT sub with no lifecycle management. This phase adds `POST /tenants`, `GET /tenants/{id}`, and a `tenants` Supabase table.

---

## Phase 86 — API Versioning

**Priority:** Medium

**Goal:** Introduce `/v1/` prefix to all endpoints. Maintain backward compatibility via redirect or alias for existing unversioned paths.

---

## Phase 87 — Full Integration Test Suite

**Priority:** High

**Goal:** Replace all remaining `skip`-marked E2E tests with fully automated integration tests that run against a test Supabase project. Achieve 0 skipped tests across the full suite.

---

## Summary Table

| Phase | Title | Thread | Priority |
|-------|-------|--------|----------|
| 68 | DLQ Controlled Replay | Reliability | High |
| 69 | DLQ Observability | Reliability | Medium |
| 70 | Event Time vs System Time | Reliability | Medium |
| 71 | booking_id Stability Layer | Reliability | Medium |
| 72 | Financial Facts: List Endpoint | Financial | Medium |
| 73 | BOOKING_AMENDED: AmendmentPayload | Amendment | Medium |
| 74 | BOOKING_AMENDED: DDL + apply branch | Amendment | Medium |
| 75 | BOOKING_AMENDED: Full Pipeline | Amendment | Medium |
| 76 | OTA Normalization: Timezone | Normalization | Medium |
| 77 | OTA Normalization: Currency + Guests | Normalization | Medium |
| 78 | Owner Statement Projection | Financial | High |
| 79 | Rate Limiting: Per-Provider | Reliability | Medium |
| 80 | Idempotency Monitoring | Reliability | Medium |
| 81 | Availability Read Model | Projection | Low |
| 82 | Replay Snapshot Optimization | Reliability | Low |
| 83 | Webhook Replay Protection | Reliability | Medium |
| 84 | Finance API Ingestion | Financial | High |
| 85 | Tenant Management API | Product | Medium |
| 86 | API Versioning | Product | Medium |
| 87 | Full Integration Test Suite | Quality | High |

---

## Notes

- **High priority threads:** Financial Layer (78, 84), Reliability (68, 87)
- **BOOKING_AMENDED** (73-75) is gated on booking_id stability (71) — do not attempt before Phase 71
- **Owner Statement** (78) is the first product-visible feature beyond the ingestion pipeline
- All phases are independent unless explicitly noted — any can be skipped or deferred without breaking the system
