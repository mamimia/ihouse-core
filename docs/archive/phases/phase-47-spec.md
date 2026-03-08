# Phase 47 Spec — OTA Payload Boundary Validation

## Objective

Add structured, explicit validation of OTA payloads at the ingestion boundary —
before the normalize step — so malformed payloads produce error codes, not opaque exceptions.

## Rationale

Every production API (Stripe, Twilio) validates inputs at the boundary before canonical processing.
Previously, invalid OTA payloads could fail deep inside the pipeline with opaque stack traces.
Phase 47 makes all rejections explicit and structured at the entry point.

## Deliverables

### New file: `src/adapters/ota/payload_validator.py`

**Dataclass:**
- `PayloadValidationResult(valid, errors, provider, event_type_raw)` — frozen

**Function:** `validate_ota_payload(provider, payload) → PayloadValidationResult`

**6 validation rules (all errors collected, not fail-fast):**
1. `PROVIDER_REQUIRED` — provider must be non-empty
2. `PAYLOAD_MUST_BE_DICT` — payload must be a dict
3. `RESERVATION_ID_REQUIRED` — reservation_id field required
4. `TENANT_ID_REQUIRED` — tenant_id field required
5. `OCCURRED_AT_INVALID` — occurred_at must parse as ISO datetime if present
6. `EVENT_TYPE_REQUIRED` — at least one of: event_type, type, action, event, status

### Modified: `src/adapters/ota/pipeline.py`

Boundary validation added at top of `process_ota_event`, before `normalize()`.
Raises on invalid payload with collected errors.

## Tests

16 contract tests:
- Valid payload → valid=True
- Each of the 6 rules triggered independently
- Multi-error collection
- Frozen dataclass guard
- Alternative event_type field names accepted (type, action, event, status)
- Pipeline raises on invalid

Plus: backward compat fix to `test_ota_pipeline_contract.py`.

## Outcome

119 tests pass (2 pre-existing SQLite failures unrelated).
