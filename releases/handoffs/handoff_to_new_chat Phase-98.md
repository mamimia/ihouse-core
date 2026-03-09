# Handoff to New Chat — Phase 98

**Context at ~80% — handoff initiated per BOOT.md protocol.**
**Date:** 2026-03-09
**Time:** 16:27 ICT (UTC+7)
**Git branch:** `checkpoint/supabase-single-write-20260305-1747`
**Last commit:** `607e519` — Phase 98 — Despegar Adapter (closed)

---

## Current Status

| | |
|--|--|
| **Last Closed Phase** | Phase 98 — Despegar Adapter (Tier 2 — Latin America) |
| **Total Tests** | **2038 passed, 2 skipped** (pre-existing SQLite skips, unrelated) |
| **OTA Adapters** | **11 total**: bookingcom, expedia, airbnb, agoda, tripcom, vrbo, gvr, traveloka, makemytrip, klook, despegar |
| **GitHub** | ✅ Pushed `607e519` |
| **Next Phase** | Phase 99 — Despegar Replay Fixture Contract |

---

## What Phase 98 Did

- **NEW:** `src/adapters/ota/despegar.py` — DespegarAdapter
  - `reservation_code` → `reservation_id` (strips `DSP-` prefix)
  - `hotel_id` → `property_id`
  - `passenger_count` → `canonical_guest_count` (LATAM travel term)
  - `total_fare` → `canonical_total_price`
  - Events: `BOOKING_CONFIRMED`→CREATE, `BOOKING_CANCELLED`→CANCEL, `BOOKING_MODIFIED`→AMENDED
- **NEW:** `tests/test_despegar_adapter_contract.py` — 61 tests (Groups A–H)
- **MODIFIED:** `src/adapters/ota/registry.py`
- **MODIFIED:** `src/adapters/ota/booking_identity.py` — `_strip_despegar_prefix` (DSP-)
- **MODIFIED:** `src/adapters/ota/schema_normalizer.py` — 6 helper branches
- **MODIFIED:** `src/adapters/ota/amendment_extractor.py` — `extract_amendment_despegar`
- **MODIFIED:** `src/adapters/ota/financial_extractor.py` — `_extract_despegar` (total_fare/despegar_fee/net_amount, multi-currency LATAM)
- **PATCHED:** `src/adapters/ota/payload_validator.py` — Rule 3 now accepts `reservation_code` and `booking_code` as valid booking identity alternatives (was a latent gap)

---

## What Phase 97 Did (also in this session)

- **NEW:** `tests/fixtures/ota_replay/klook.yaml` — 2 fixtures (CREATE + CANCEL, SGD, KL-ACTBK-REPLAY-001)
- **MODIFIED:** `tests/test_ota_replay_fixture_contract.py` — EXPECTED_PROVIDERS 9→10, count invariant 18→20
- Result: **341 replay tests covering 10 providers × 2**

---

## Financial UI Product Direction (also documented in this session)

A forward-looking financial UI vision was added to `docs/core/improvements/future-improvements.md` (lines ~316–700+). Key points for the new chat to know:

1. **Epistemic model — three tiers** (Refined Phase 97):
   - **Tier A ✅** Provider-Attested Facts (`source_confidence = FULL`, confirmed by OTA)
   - **Tier B 🔵** System-Derived States (calculated by iHouse Core from Tier A)
   - **Tier C ⚠️** Estimated/Incomplete (`source_confidence = PARTIAL` / `lifecycle_status = UNKNOWN`)

2. **PAYOUT_RELEASED** = Tier B → A (B unless OTA sends explicit payout event; most providers don't)

3. **4-Ring Financial UI Architecture** (deferred, Phase 100+):
   - Ring 1: Financial API layer
   - Ring 2: Per-booking financial state surface (+ epistemic tier)
   - Ring 3: Portfolio surfaces
   - Ring 4: Owner-facing statements (tier-filtered, only Tier A+B)

This is **documented, not yet built**. No code was changed. No phase is blocked on this.

---

## Phase 99 — What to Do Next

**Phase 99 — Despegar Replay Fixture Contract**

Exact same pattern as Phase 97 (Klook replay) and Phase 95 (MMT replay):

1. Create `tests/fixtures/ota_replay/despegar.yaml` with 2 YAML documents:
   - `despegar_create`: `event_type: BOOKING_CONFIRMED`, `reservation_code: DSP-AR-REPLAY-001`, `hotel_id`, `passenger_count: 2`, `total_fare: "75000.00"`, `despegar_fee: "11250.00"`, `net_amount: "63750.00"`, `currency: ARS`
   - `despegar_cancel`: `event_type: BOOKING_CANCELLED`, same `reservation_code`, no `net_amount`

2. Update `tests/test_ota_replay_fixture_contract.py`:
   - `EXPECTED_PROVIDERS`: add `"despegar"` (10→11)
   - `test_e4_total_fixture_count_is_twenty` → rename to `twenty_two` and change 20→22
   - Docstring: 10→11 provider YAML files
   - D1 comment: add `despegar → event_id (standard)`

3. Run full suite — expect **2072+ passed** (2038 + ~34 new)

4. Update docs, commit, push.

---

## Key Invariants (Do Not Break)

1. `booking_state` must **never** contain financial calculations — only booking event metadata
2. `payload_validator.py` Rule 3 now accepts: `reservation_id` | `booking_ref` | `order_id` | `reservation_code` | `booking_code` — do not remove any of these
3. All adapter tests must pass before any phase closes — **0 regressions allowed**
4. `phase-timeline.md` and `construction-log.md` are **append-only** — never edit past entries
5. Replay fixture count invariant = providers × 2 (currently 11 providers → 22 fixtures after Phase 99)

---

## Key Files for New Chat

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Read this first — authority rules + protocols |
| `docs/core/current-snapshot.md` | System state (Phase 98 closed, Phase 99 next) |
| `docs/core/work-context.md` | Active objective and invariants |
| `docs/core/roadmap.md` | Phase sequencing |
| `src/adapters/ota/despegar.py` | Just-implemented adapter (Phase 98) |
| `tests/fixtures/ota_replay/klook.yaml` | Reference: exact YAML structure for Phase 99 |
| `tests/test_ota_replay_fixture_contract.py` | Replay harness — extend this for Phase 99 |
| `docs/core/improvements/future-improvements.md` | Financial UI direction (lines ~316–700) |

---

## What Was Done In This Session (Summary)

| Phase | Description | Tests |
|-------|-------------|-------|
| 93 | Payment Lifecycle (7-state machine) | +118 → 1783 |
| 94 | MakeMyTrip Adapter (Tier 2 India) | +66 → 1849 |
| 95 | MMT Replay Fixture Contract | +34 → 1883 |
| 96 | Klook Adapter (Tier 2 Asia activities) | +60 → 1943 |
| 97 | Klook Replay Fixture Contract | +34 → 1977 |
| 98 | Despegar Adapter (Tier 2 LATAM) | +61 → 2038 |

---

## System Architecture (Unchanged — for orientation)

```
POST /webhooks/{provider}
  └─ signature_verifier.py     (HMAC-SHA256, provider-specific)
  └─ rate_limiter.py           (per-tenant)
  └─ payload_validator.py      (Rule 1-5 + reservation_code/booking_code now)
  └─ pipeline.py               (process_ota_event)
       └─ registry.py          (get_adapter → 11 providers)
       └─ adapter.normalize()  (provder → NormalizedBookingEvent)
       └─ classifier.py        (semantic_kind: CREATE/CANCEL/BOOKING_AMENDED)
       └─ adapter.to_canonical_envelope()
       └─ supabase write (apply_envelope stored procedure)
```

```
Financial stack (Phase 93+):
  financial_extractor.py → BookingFinancialFacts
  payment_lifecycle.py   → PaymentLifecycleState (7 states)
  booking_financial_facts Supabase table
```

---

## No Supabase Work In Progress

No pending migrations. No schema changes needed for Phase 99.

---

**Start the new chat by reading:**
1. `docs/core/BOOT.md`
2. `docs/core/current-snapshot.md`
3. `docs/core/work-context.md`

Then proceed directly to Phase 99 — Despegar Replay Fixture Contract.
