# Phase 69 — BOOKING_AMENDED Python Pipeline + Backlog Audit

**Status:** Closed
**Prerequisite:** Phase 68 (booking_id Stability)
**Date Closed:** 2026-03-09

## Goal

Wire the Python pipeline so `BOOKING_AMENDED` events flow end-to-end from OTA webhook to `apply_envelope` (which was already ready since Phase 50). The adapters already emit the correct `BOOKING_AMENDED` envelope — the missing piece was the skill + registry registration.

Also performed a full backlog audit: discovered 3 additional items marked `deferred` in `future-improvements.md` that were already fully implemented (External Event Ordering, Signature Validation, BOOKING_AMENDED prerequisites).

## What Was Built

| File | Change |
|------|--------|
| `src/core/skills/booking_amended/__init__.py` | NEW — package marker |
| `src/core/skills/booking_amended/skill.py` | NEW — transforms OTA envelope payload → `BOOKING_AMENDED` emitted event; COALESCE-safe (only includes explicitly-amended fields) |
| `src/core/kind_registry.core.json` | MODIFIED — `"BOOKING_AMENDED": "booking-amended"` added |
| `src/core/skill_exec_registry.core.json` | MODIFIED — `"booking-amended": "core.skills.booking_amended.skill"` added |
| `src/adapters/ota/service.py` | MODIFIED — best-effort financial facts write for `BOOKING_AMENDED` APPLIED events |
| `tests/test_booking_amended_skill_contract.py` | NEW — 20 contract tests |
| `docs/core/improvements/future-improvements.md` | MODIFIED — 3 items marked resolved (Ordering, Signature, BOOKING_AMENDED) |

## End-to-End Flow (Now Live)

```
OTA webhook POST /webhooks/{provider}
  → pipeline.process_ota_event()
  → adapter.normalize() → classify_normalized_event() → BOOKING_AMENDED
  → adapter.to_canonical_envelope() → CanonicalEnvelope(type="BOOKING_AMENDED", payload={booking_id, new_check_in, ...})
  → skill_fn(payload) → booking_amended/skill.py → BOOKING_AMENDED emitted event
  → apply_fn() → apply_envelope() → booking_state updated via COALESCE(new_check_in, check_in)
  → status APPLIED → (best-effort) write_financial_facts("BOOKING_AMENDED")
```

## Invariants

- `apply_envelope` remains the single write authority
- `booking_amended` skill never reads `booking_state`
- Only explicitly-amended fields included in emitted payload → COALESCE in `apply_envelope` preserves existing dates/guests for fields not changed
- ACTIVE-state guard in `apply_envelope` rejects amendments on canceled bookings (enforced at DB level, Phase 50)

## Result

**451 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations.
