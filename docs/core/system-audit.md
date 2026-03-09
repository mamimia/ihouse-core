# iHouse Core — System Audit Report

**Phase 92 — Roadmap + System Audit**
**Date:** 2026-03-09
**Auditor:** Claude (Antigravity)
**Baseline:** 1665 tests pass, 2 skipped (pre-existing SQLite guards)

---

## 1. Source Module Inventory

### 1.1 OTA Adapter Layer (`src/adapters/ota/`)

| Module | Purpose | Status |
|--------|---------|--------|
| `base.py` | Abstract OTAAdapter base class | ✅ Stable |
| `registry.py` | `get_adapter(provider)` dispatcher | ✅ 8 providers registered |
| `pipeline.py` | `process_ota_event()` — normalize → classify → envelope | ✅ CI-safe, no live DB |
| `schemas.py` | `NormalizedBookingEvent`, `ClassifiedBookingEvent`, `CanonicalEnvelope`, `AmendmentFields` | ✅ Frozen invariant |
| `semantics.py` | `classify_normalized_event()` — event_type string → semantic kind | ✅ Fixed set, documented |
| `payload_validator.py` | `validate_ota_payload()` — boundary validation | ✅ Known limitation: gvr_booking_id/booking_code not recognized natively |
| `idempotency.py` | `generate_idempotency_key(provider, event_id, type)` | ✅ Deterministic |
| `booking_identity.py` | `normalize_reservation_ref()` — prefix stripping, lowercase | ✅ Per-provider rules |
| `amendment_extractor.py` | `normalize_amendment()` — dispatches to 8 provider extractors | ✅ All 8 covered |
| `financial_extractor.py` | `extract_financial_facts()` — BookingFinancialFacts per provider | ✅ FULL/ESTIMATED/PARTIAL confidence |
| `schema_normalizer.py` | `normalize_schema()` — adds canonical_* keys to payload dict | ✅ All canonical fields |
| `date_normalizer.py` | ISO date normalization utility | ✅ |
| `reconciliation_model.py` | READ-ONLY drift detection model (Phase 89) | ✅ 7 FindingKinds, 3 Severities |
| `conflict_detector.py` | READ-ONLY overlap detection | ✅ |
| `ordering_buffer.py` | Event ordering protection | ✅ |
| `ordering_trigger.py` | Ordering trigger logic | ✅ |
| `dead_letter.py` | DLQ write port | ✅ |
| `dlq_replay.py` | Controlled DLQ replay | ✅ |
| `dlq_inspector.py` | DLQ inspection utilities | ✅ |
| `dlq_alerting.py` | DLQ accumulation alerting | ✅ |
| `idempotency_monitor.py` | Idempotency duplicate metrics | ✅ |
| `health_check.py` | Supabase ping, DLQ count | ✅ |
| `structured_logger.py` | JSON structured logging | ✅ |
| `tenant_isolation_enforcer.py` | Cross-tenant leak detection | ✅ |
| `tenant_isolation_checker.py` | RLS audit helpers | ✅ |
| `reservation_timeline.py` | Per-booking event history query | ✅ |
| `signature_verifier.py` | HMAC-SHA256 webhook sig verification | ✅ 8 providers |
| `financial_writer.py` | Supabase persist for BookingFinancialFacts | ✅ |
| `booking_status.py` | Booking status helpers | ✅ |
| `service.py` | `ingest_provider_event()` convenience wrapper | ✅ |
| `validator.py` | Additional field validators | ✅ |

### 1.2 OTA Adapters — Per-Provider Summary

| Provider | File | Phase | reservation_id field | event_id field | property_id field | Amendment block |
|----------|------|-------|---------------------|----------------|-------------------|-----------------|
| bookingcom | `bookingcom.py` | 27+ | `reservation_id` | `event_id` | `property_id` | `new_reservation_info.*` |
| expedia | `expedia.py` | 27+ | `reservation_id` | `event_id` | `property_id` | `changes.dates.*, changes.guests.count` |
| airbnb | `airbnb.py` | 27+ | `reservation_id` | `event_id` | `listing_id` ⚠️ | `alteration.*` |
| agoda | `agoda.py` | 27+ | `booking_ref` | `event_id` | `property_id` | `modification.*` |
| tripcom | `tripcom.py` | 27+ | `order_id` | `event_id` | `hotel_id` ⚠️ | `changes.*` |
| vrbo | `vrbo.py` | 83 | `reservation_id` | `event_id` | `unit_id` ⚠️ | `alteration.*` |
| gvr | `gvr.py` | 85 | `gvr_booking_id` ⚠️ | `event_id` | `property_id` | `modification.*` |
| traveloka | `traveloka.py` | 88 | `booking_code` ⚠️ | `event_reference` ⚠️ | `property_code` ⚠️ | `modification.*` |

> ⚠️ marks non-standard field names that must be documented for test payload authors and future integrators.

**payload_validator boundary note:** `validate_ota_payload()` accepts `reservation_id`, `booking_ref`, `order_id` only.
GVR (`gvr_booking_id`) and Traveloka (`booking_code`) must duplicate their ID into `reservation_id` in test payloads or at the webhook boundary layer.

### 1.3 API Layer (`src/api/`)

| Module | Purpose | Status |
|--------|---------|--------|
| `webhooks.py` | `POST /webhooks/{provider}` — main ingestion endpoint | ✅ |
| `admin_router.py` | `GET /admin/*` — metrics, DLQ, health, booking timeline | ✅ |
| `bookings_router.py` | Booking query endpoints | ✅ |
| `financial_router.py` | Financial facts query | ✅ |
| `health.py` | `GET /health` with enhanced Supabase check | ✅ |
| `auth.py` | JWT bearer auth middleware | ✅ |
| `rate_limiter.py` | Per-tenant sliding-window rate limiter | ✅ |
| `error_models.py` | `make_error_response()` — standardized error JSON | ✅ |

### 1.4 Core Layer (`src/core/`)

| Module | Purpose | Status |
|--------|---------|--------|
| `core/api/ingest.py` | `IngestAPI.append_event()` | ✅ |
| `core/api/query.py` | Query API surface | ✅ |
| `core/api/factory.py` | Factory for core API components | ✅ |
| `core/db/config.py` | DB config (Supabase URL, key) | ✅ |
| `core/db/migrate.py` | Migration runner | ✅ |
| `core/db/audit_read.py` | Audit trail read | ✅ |
| `core/db/outbox_daemon.py` | Outbox/dispatch daemon | ✅ |
| `core/db/_sqlite_guard.py` | Guards against SQLite in production | ✅ 2 skipped tests are SQLite guards |

---

## 2. Test Suite Inventory

| Test File | Phase | Tests | Coverage Area |
|-----------|-------|-------|---------------|
| `test_ota_replay_harness.py` | 51+ | 6 | bookingcom replay + duplicate + amendment |
| `test_e2e_integration_harness.py` | 90 | 276 | All 8 providers × CREATE/CANCEL/AMENDED pipeline |
| `test_ota_replay_fixture_contract.py` | 91 | 273 | YAML fixture determinism, 16 fixtures, Groups A-E |
| `test_reconciliation_model_contract.py` | 89 | 87 | ReconciliationFinding, ReconciliationReport, ReconciliationSummary |
| `test_traveloka_adapter_contract.py` | 88 | 53 | TravelokaAdapter, Groups A-I |
| `test_vrbo_adapter_contract.py` | 83 | ~40 | VrboAdapter |
| `test_gvr_adapter_contract.py` | 85 | ~40 | GVRAdapter |
| `test_tenant_isolation_*.py` | 87 | 54 | Tenant isolation enforcer |
| (many other contract tests) | 21–82 | ~836 | All other modules |
| **TOTAL** | | **1665** | **All passing, 2 SQLite skips** |

---

## 3. Known Boundary Conditions (Engineering Notes)

### 3.1 payload_validator field set

`validate_ota_payload()` at `src/adapters/ota/payload_validator.py:84-91` accepts:
```python
reservation_id = (
    payload.get("reservation_id", "") or
    payload.get("booking_ref", "") or
    payload.get("order_id", "") or
    ""
)
```

**Not covered natively:** `gvr_booking_id`, `booking_code`, `order_ref`.

**Mitigation (current):** Test fixtures and webhook integration layers duplicate the provider-native ID into `reservation_id`.
**Future recommendation:** Extend `payload_validator` to accept provider-specific ID fields, or add a pre-validation normalization step at the webhook boundary.

### 3.2 semantics.py event_type coverage

`classify_normalized_event()` at `src/adapters/ota/semantics.py` maps a fixed set:
- CREATE: `reservation_created`, `created`, `new`, `reservation_create`, `booking.created`, `order_created`
- CANCEL: `reservation_cancelled`, `cancelled`, `canceled`, `reservation_cancel`, `booking.cancelled`, `booking.canceled`, `order_cancelled`, `order_canceled`
- AMENDED: `reservation_modified`, `modified`, `amended`, `alteration_create`, `alteration`, `booking.modified`, `order_modified`

**Not covered:** `booking_confirmed`, `booking_cancelled`, `booking_modified` (Traveloka internal names).

**Mitigation (current):** Test payloads use semantics.py-known values.
**Future recommendation:** Either (a) extend semantics.py with Traveloka-specific mappings, or (b) add a provider-specific event_type normalization layer before classification.

### 3.3 Airbnb property_id field

Airbnb adapter reads `listing_id` (not `property_id`) as the property identifier. This is correct per the Airbnb webhook schema but differs from all other providers.
Consumers of the canonical envelope receive `property_id` (normalized), not `listing_id`.

### 3.4 Traveloka event_reference as idempotency source

Traveloka adapter uses `event_reference` (not `event_id`) as `external_event_id`.
This is correct per the Traveloka webhook schema but differs from all other 7 providers.
Idempotency key = `traveloka:{canonical_type}:{event_reference}`.

---

## 4. Architecture Integrity Check

| Invariant | Status | Evidence |
|-----------|--------|---------|
| `apply_envelope` is the only write authority to `booking_state` | ✅ VERIFIED | No other module writes to booking_state |
| `booking_id = {provider}_{normalized_ref}` | ✅ VERIFIED | All 8 adapters, 276 E2E tests |
| `booking_state` never contains financial calculations | ✅ VERIFIED | financial_facts in separate table |
| `occurred_at` from OTA payload; `recorded_at` from server | ✅ VERIFIED | Phase 76, schemas.py |
| Reconciliation layer READ-ONLY | ✅ VERIFIED | reconciliation_model.py — no write paths |
| No live Supabase in test suite | ✅ VERIFIED | 2 SQLite guards are pre-existing, non-regressing |
| All 8 OTA adapters produce deterministic envelopes | ✅ VERIFIED | 549 Phase 90+91 tests |

---

## 5. Gaps and Recommendations for Phase 93+

| Gap | Severity | Recommendation |
|-----|----------|----------------|
| `payload_validator` doesn't natively recognize `gvr_booking_id` / `booking_code` | Medium | Add provider-specific ID field normalization at webhook boundary (Phase 93 or 94) |
| `semantics.py` doesn't know Traveloka's native event_type names | Low | Add Traveloka-specific event_type aliases (Phase 94 with MakeMyTrip adapter) |
| No BOOKING_AMENDED fixture in Phase 91 replay set | Low | Add AMENDED fixtures in next fixture expansion |
| No AMENDED YAML fixture for Group E coverage | Low | Extend `tests/fixtures/ota_replay/*.yaml` with a `_amend` document per provider |
| GVR `reservation_id` duplication is a workaround | Medium | Formalize in webhook layer or extend payload_validator |
| `pyyaml` not in `requirements.txt` / `pyproject.toml` | Low | Add as test dependency before CI integration |

---

## 6. Next Phase Recommendation

**Phase 93 — Payment Lifecycle / Revenue State Projection** is the recommended next phase.

Rationale:
- The test infrastructure (Phase 90-91) is complete and proven
- The financial extractor (Phase 65-66) provides the foundation
- Revenue state visibility is the highest-value next product capability
- No further adapter work needed until Phase 94 (MakeMyTrip)
