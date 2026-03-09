# Handoff to New Chat — Phase 78

## System State

**Last closed phase:** Phase 77 — OTA Schema Normalization  
**Active test count:** 572 passed, 2 skipped (pre-existing SQLite, unrelated)  
**Repo branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Last commit:** `38ffd70` — Phase 77: OTA Schema Normalization

---

## What Phase 77 Delivered

Created `src/adapters/ota/schema_normalizer.py` with `normalize_schema(provider, payload) → dict`.

All 5 OTA adapters now enrich `NormalizedBookingEvent.payload` with three canonical keys:

| Canonical Key | bookingcom | airbnb | expedia | agoda | tripcom |
|--------------|-----------|--------|---------|-------|---------|
| `canonical_guest_count` | `number_of_guests` | `guest_count` | `guests.count` | `num_guests` | `guests` |
| `canonical_booking_ref` | `reservation_id` | `reservation_id` | `reservation_id` | `booking_ref` | `order_id` |
| `canonical_property_id` | `property_id` | `listing_id` | `property_id` | `property_id` | `hotel_id` |

Rules:
- Original raw fields are **preserved** — canonical keys are **additive only**
- Missing fields → `None` (never `KeyError`)
- `normalize_schema()` returns a **copy** — caller dict is never mutated

27 contract tests added (`tests/test_schema_normalizer_contract.py`, Groups A–E).  
4 existing payload preservation tests updated (superset check).

---

## Mandatory Session Start Protocol

Before doing anything else, read in order:

1. `docs/core/BOOT.md` — session start protocol and authority rules
2. `docs/core/system-identity.md` — what this system is
3. `docs/core/governance.md` — collaboration rules
4. `docs/core/current-snapshot.md` — current state (Phase 77 closed, 572 tests)
5. `docs/core/work-context.md` — active context (Phase 78 TBD)
6. `docs/core/phase-timeline.md` (last 50 lines) — recent history

---

## Locked Invariants — Do Not Touch

These are permanent and frozen:

- `apply_envelope` is the **only** write authority for `event_log` and `booking_state`
- `event_log` is **strictly append-only**
- `booking_id` = `{source}_{reservation_ref}` — deterministic, never changes
- `reservation_ref` always normalized via `normalize_reservation_ref()`
- `tenant_id` always derived from JWT `sub` claim
- `booking_state` is a read model only — never contains financial calculations
- `recorded_at` is server-generated (UTC) — never from OTA payload
- `occurred_at` is OTA-provided — untrusted for ordering

---

## Key Files (Phase 77 additions)

| File | Role |
|------|------|
| `src/adapters/ota/schema_normalizer.py` | NEW — canonical field mapping for all providers |
| `tests/test_schema_normalizer_contract.py` | NEW — 27 contract tests |
| `docs/archive/phases/phase-77-spec.md` | NEW — phase spec |
| `releases/phase-77-ota-schema-normalization.zip` | NEW — release artifact |

---

## Next Phase — Phase 78

**TBD.** Consult `docs/core/improvements/future-improvements.md` → Active Backlog for candidates.

Suggested candidates (from roadmap):
- Webhook Signature Verification hardening / rotation
- Rate limiting per tenant
- Observability / structured logging layer
- Any item promoted by the user

---

## Lint Warning (Not a Bug)

Pyre2 reports `Could not find import of ...` for all `adapters.ota.*` imports in test files.  
This is a **false-positive** — Pyre2 doesn't see `PYTHONPATH=src`.  
All 572 tests pass cleanly with `PYTHONPATH=src python -m pytest tests/`.
