# iHouse Core — Phase Summary (English)

---

**Phase 1** — Immutable append-only event table established. All system state is derived from events, never written directly.

**Phase 2** — Deterministic projection and rebuild introduced. Full system state can be reconstructed from event history at any time.

**Phase 3** — Database-level idempotency enforced. Events sent twice do not produce duplicate rows.

**Phase 4** — Fingerprint validation added to rebuild; event table declared immutable during replay.

**Phase 5** — Version inflation during replay prevented; forward/backward compatibility discipline locked.

**Phase 6** — Outbox pattern introduced with multi-worker support; claim + lease semantics prevent double execution.

**Phase 7** — Infrastructure hardened: WAL, foreign_keys, busy_timeout; deterministic rebuild validated twice.

**Phase 8** — FastAPI introduced; POST /events ingest endpoint and query surface formalized.

**Phase 9** — HTTP hardening: API key enforcement, structured logging, no stack trace leakage.

**Phase 10** — Skill Runner hardened: timeout, subprocess isolation, externalized kind_registry.

**Phase 11** — Kind→Skill routing moved to Core; Python default mapping removed.

**Phase 12** — Domain audit completed; inward migration plan prepared.

**Phase 13A** — Append-only event_log formalized; atomic canonical envelope transaction defined.

**Phase 13B** — Commit only when apply_status == APPLIED; booking_state.last_envelope_id introduced.

**Phase 13C** — Supabase introduced as cloud persistence: event_log and booking_state created and validated on Cloud.

**Phase 14** — Single deterministic commit path enforced; replay never commits; hidden state writes eliminated.

**Phase 15** — FastAPI declared sole execution entrypoint; parallel execution removed.

**Phase 16** — Canonical domain migration: schema locked, core deterministic alignment, financial-grade atomic idempotency gate.

**Phase 17A** — Canonical run_api.sh; dev smoke scripts; CI enforcement; secret-based API key.

**Phase 17B** — apply_envelope validated as the single atomic write authority; zero-mutation replay confirmed E2E.

**Phase 17C** — Overlap gate introduced (half-open range [check_in, check_out)); business dedup key on (tenant_id, source, reservation_ref, property_id).

**Phase 18** — BOOKING_CANCELED introduced; status='canceled' removes bookings from overlap checks without deleting event history.

**Phase 19** — event_version validation gate at DB level; deterministic rejection codes locked: UNKNOWN_EVENT_KIND, ALREADY_APPLIED, etc.

**Phase 20** — apply_envelope confirmed as single write gate; duplicate envelope replay confirmed zero-mutation E2E.

**Phase 21** — External ingestion boundary defined: external systems never write directly to event_log. Supported: BOOKING_CREATED, BOOKING_CANCELED.

**Phase 22** — OTA adapter layer introduced; normalize → validate → apply_envelope pipeline established.

**Phase 23** — semantics.py: deterministic semantic classification for OTA events before canonical envelope creation.

**Phase 24** — MODIFY introduced as explicit OTA semantic kind; modification events no longer silently classified as CREATE/CANCEL.

**Phase 25** — Rule locked: MODIFY → deterministic reject by default. Ambiguous OTA modification events never enter the canonical model.

**Phase 26** — All 5 OTA providers inspected (Booking.com, Expedia, Airbnb, Agoda, Trip.com): no payload-only deterministic modification subtype found. Rule confirmed.

**Phase 27** — Multi-OTA adapter architecture introduced; shared pipeline.py; Expedia scaffold added.

**Phase 28** — External canonical surface formalized: BOOKING_SYNC_INGEST replaced by explicit BOOKING_CREATED / BOOKING_CANCELED events.

**Phase 29** — OTA replay harness added; replay coverage for CREATED/CANCELED/MODIFY/duplicate/invalid payloads.

**Phase 30** — Runtime OTA handoff locked: ingest_provider_event → process_ota_event → apply_envelope.

**Phase 31** — Docs synchronized to live runtime contract; future-improvements.md backlog introduced.

**Phase 32** — OTA ingest contract test verification loop closed; all runtime paths covered by tests.

**Phase 33** — Discovery: OTA transport idempotency vs. canonical business idempotency separated; routing gap identified.

**Phase 34** — Proved: BOOKING_CREATED routed to noop skill; BOOKING_CANCELED had no active route. Payload alignment gap confirmed.

**Phase 35** — Implementation: booking_created + booking_canceled skills built; registry updated; both events now reach apply_envelope. E2E ✅.

**Phase 36** — booking_id rule locked: {source}_{reservation_ref} — deterministic, consistent; double dedup in apply_envelope verified.

**Phase 37** — Discovery: CANCELED before CREATED → deterministic BOOKING_NOT_FOUND rejection. No silent data loss. Known open gap.

**Phase 38** — Dead Letter Queue: ota_dead_letter table; failed OTA events are preserved rather than lost. E2E ✅.

**Phase 39** — DLQ Controlled Replay: replay_dlq_row() — manual, idempotent, always routes through apply_envelope.

**Phase 40** — DLQ Observability: ota_dlq_summary view; read-only inspection functions for operators.

**Phase 41** — DLQ Alerting: configurable pending threshold; WARNING log when pending ≥ threshold.

**Phase 42** — Discovery: BOOKING_AMENDED prerequisites audit — 3/10 satisfied, 7 gaps identified.

**Phase 43** — booking_state.status verified as already existing (Phase 42 mis-reported); get_booking_status() read-only utility added. 4/10 ✅.

**Phase 44** — Ordering buffer: ota_ordering_buffer table; events blocked by ordering are stored by booking_id, not lost.

**Phase 45** — Auto-trigger after BOOKING_CREATED: buffered ordering-blocked events are automatically replayed.

**Phase 46** — System Health Check: 5 components; never raises; OVERALL OK confirmed E2E ✅.

**Phase 47** — OTA Payload Boundary Validation: PayloadValidationResult; 6 rules; all error codes returned together.

**Phase 48** — Idempotency Key Standardization: format provider:event_type:event_id; collision-safe across providers and event types.

**Phase 49** — AmendmentFields dataclass + amendment_extractor.py for Booking.com and Expedia. 7/10 BOOKING_AMENDED prerequisites ✅.

**Phase 50** — BOOKING_AMENDED DDL + apply_envelope branch: enum extended, migration deployed, ACTIVE-state guard, COALESCE for dates. E2E on live Supabase ✅. 10/10 prerequisites ✅.

**Phase 51** — Python pipeline integration: semantics.py + service.py wired for BOOKING_AMENDED routing through the full canonical pipeline.

**Phase 52** — GitHub Actions CI hardening: automated build + test on every push.

**Phase 53** — Expedia Adapter: full normalize() + extract_financial_facts(); covers CREATED/CANCELED.

**Phase 54** — Airbnb Adapter: normalize() + extract_financial_facts(); payout_amount + booking_subtotal.

**Phase 55** — Agoda Adapter: normalize() + extract_financial_facts(); selling_rate + net_rate.

**Phase 56** — Trip.com Adapter: normalize() + extract_financial_facts(); order_amount + channel_fee.

**Phase 57** — Webhook Signature Verification: HMAC-SHA256 for all 5 providers; production rejects tampered or unauthorized payloads.

**Phase 58** — HTTP Ingestion Layer: POST /webhooks/{provider} FastAPI endpoint; HTTP status codes locked (200/400/403/500).

**Phase 59** — FastAPI App Entrypoint: src/main.py unified; GET /health; lifespan; local dev runner.

**Phase 60** — Structured Request Logging Middleware: UUID request_id per request; → ← log lines; X-Request-ID response header.

**Phase 61** — JWT Auth: tenant_id from JWT Bearer sub claim; api/auth.py; Depends(jwt_auth); dev bypass when secret not set.

**Phase 62** — Per-Tenant Rate Limiting: sliding window; 60 req/min/tenant; 429 + Retry-After header on excess.

**Phase 63** — OpenAPI Docs enriched to production quality: /docs + /redoc; BearerAuth security scheme; full response schemas for all HTTP status codes.

**Phase 64** — Enhanced Health Check: real Supabase ping + DLQ count; ok / degraded / unhealthy (503) semantics.

**Phase 65** — Financial Data Foundation: BookingFinancialFacts frozen dataclass; all 5 OTA adapters extract financial fields (total_price, currency, ota_commission, taxes, fees, net_to_property). No DB writes. Invariant locked: booking_state must never contain financial data.

**Phase 66** — booking_financial_facts Supabase Projection: append-only table with RLS; financial_writer.py persists facts after BOOKING_CREATED APPLIED (best-effort, non-blocking). E2E verified ✅.

**Phase 67** — Financial Facts Query API: GET /financial/{booking_id}; JWT auth; tenant isolation enforced at DB query level; 404 for unknown; reads booking_financial_facts only, never booking_state.

---

**Total:** 396 tests passing, 2 skipped (pre-existing SQLite limitations, unrelated).
