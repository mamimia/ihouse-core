# Phase 57 Spec — Webhook Signature Verification

## Objective

Add HMAC-SHA256 signature verification to all OTA webhook ingestion.
Without this, any malicious actor can send fake webhooks to the pipeline.

## Status

In Progress

## Design

### Per-provider signature headers

| Provider | Header | Format |
|----------|--------|--------|
| Booking.com | `X-Booking-Signature` | `sha256=<hex>` |
| Expedia | `X-Expedia-Signature` | `sha256=<hex>` |
| Airbnb | `X-Airbnb-Signature` | `sha256=<hex>` |
| Agoda | `X-Agoda-Signature` | `sha256=<hex>` |
| Trip.com | `X-TripCom-Signature` | `sha256=<hex>` |

### Secret management

Secrets stored in environment variables:
```
IHOUSE_WEBHOOK_SECRET_BOOKINGCOM=<secret>
IHOUSE_WEBHOOK_SECRET_EXPEDIA=<secret>
IHOUSE_WEBHOOK_SECRET_AIRBNB=<secret>
IHOUSE_WEBHOOK_SECRET_AGODA=<secret>
IHOUSE_WEBHOOK_SECRET_TRIPCOM=<secret>
```

### Behaviour

- Secret not configured → **skip verification** (dev/test mode, emit warning)
- Secret configured + signature missing → **raise SignatureVerificationError**
- Secret configured + signature wrong → **raise SignatureVerificationError**
- Secret configured + signature correct → **pass**

### Security

- `hmac.compare_digest()` — constant-time compare (prevents timing attacks)
- Raw body must be used for HMAC (before JSON parse)
- Signature strip prefix `sha256=` before comparison

## Scope

1. `src/adapters/ota/signature_verifier.py` — verifier + error class
2. `tests/test_signature_verifier.py` — unit tests
3. No pipeline changes needed in Phase 57 (verifier is a callable utility)
   — pipeline integration is Phase 58 (HTTP layer)

## Invariants — must not change

- No DB changes
- No canonical changes
- No existing tests broken
