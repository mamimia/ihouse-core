# iHouse Core — Current Snapshot

## Current Phase
Phase 58 — HTTP Ingestion Layer (closed)

## Last Closed Phase
Phase 57 — Webhook Signature Verification

## System Status

**Full OTA ingestion stack: webhook → signature verify → payload validate → canonical pipeline → Supabase.**

apply_envelope is the only authority for canonical state mutations.

Health check: OVERALL OK ✅

## Phase 58 Result

FastAPI HTTP ingestion endpoint now live:

```
POST /webhooks/{provider}
  → verify_webhook_signature   (403 on failure)
  → validate_ota_payload       (400 on failure)
  → ingest_provider_event      (200 + idempotency_key)
  → 500 on unexpected error
```

**286 tests pass** (2 pre-existing SQLite skips, unrelated).

| File | Change |
|------|--------|
| `src/api/__init__.py` | New package init |
| `src/api/webhooks.py` | FastAPI router — `POST /webhooks/{provider}` |
| `tests/test_webhook_endpoint.py` | 16 contract tests (TestClient, no live server) |

## Full OTA Adapter Layer

| Module | Role |
|--------|------|
| `semantics.py` | OTA event → semantic kind (CREATE / CANCEL / BOOKING_AMENDED) |
| `validator.py` | Structural + semantic + canonical validation |
| `bookingcom.py` | Booking.com normalization + envelope construction |
| `expedia.py` | Expedia normalization + envelope construction |
| `airbnb.py` | Airbnb normalization + envelope construction |
| `agoda.py` | Agoda normalization + envelope construction |
| `tripcom.py` | Trip.com normalization + envelope construction |
| `amendment_extractor.py` | Provider-agnostic AmendmentFields normalization |
| `idempotency.py` | Namespaced key: `{provider}:{type}:{event_id}` |
| `payload_validator.py` | Boundary validation (pre-pipeline) |
| `signature_verifier.py` | HMAC-SHA256 webhook signature verification |
| `dead_letter.py` | DLQ write |
| `dlq_replay.py` | Controlled replay → apply_envelope |
| `dlq_inspector.py` | DLQ observability |
| `dlq_alerting.py` | Threshold alerting |
| `booking_status.py` | Read booking lifecycle status |
| `ordering_buffer.py` | Ordering buffer: write, read, mark |
| `ordering_trigger.py` | Auto-trigger replay on BOOKING_CREATED |
| `health_check.py` | Consolidated system readiness check |
| `api/webhooks.py` | FastAPI HTTP ingestion router |

## OTA Adapter Matrix

| Provider    | CREATE | CANCEL | AMENDED | Signature Header |
|-------------|:------:|:------:|:-------:|------------------|
| Booking.com | ✅ | ✅ | ✅ | `X-Booking-Signature` |
| Expedia     | ✅ | ✅ | ✅ | `X-Expedia-Signature` |
| Airbnb      | ✅ | ✅ | ✅ | `X-Airbnb-Signature` |
| Agoda       | ✅ | ✅ | ✅ | `X-Agoda-Signature` |
| Trip.com    | ✅ | ✅ | ✅ | `X-TripCom-Signature` |

## Tests

**286 passing** (2 pre-existing SQLite skips, unrelated)
