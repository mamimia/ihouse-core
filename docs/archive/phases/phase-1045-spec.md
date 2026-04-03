# Phase 1045 — Guest Checkout Backend Foundation

**Status:** ACTIVE  
**Prerequisite:** Phase 1044 CLOSED, Checkout Workstream Audit complete  
**Date opened:** 2026-04-02  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Scope

Backend-only. No frontend in this phase.

1. Add `GUEST_CHECKOUT` to `TokenType` enum
2. DB migration: `guest_checkout_*` columns on `booking_state`
3. Three new endpoints in `guest_checkout_router.py`:
   - `POST /bookings/{booking_id}/guest-checkout-token` — generate token, issue QR
   - `GET /guest-checkout/{token}` — resolve token, return portal payload
   - `POST /guest-checkout/{token}/complete` — write `guest_checkout_confirmed_at`
4. Contract tests

---

## Product Decisions (from audit review)

- Guest checkout confirmation is **non-blocking** — parallel to worker settlement
- `booking_state.checked_out_at` remains canonical checkout signal (worker path)
- `guest_checkout_confirmed_at` added as separate, additive guest-side timestamp
- QR expiry: **24h from checkout date** (resendable)
- Guest feedback: **optional**, never blocking
- Early checkout: token uses `early_checkout_effective_at` as the effective date — no branching in guest UI

---

## Closure Conditions

- [x] `TokenType.GUEST_CHECKOUT` exists in `access_token_service.py`
- [x] `booking_state` migration applied: `guest_checkout_initiated_at`, `guest_checkout_confirmed_at`, `guest_checkout_token_hash`, `guest_checkout_steps_completed`
- [x] `POST /bookings/{id}/guest-checkout-token` returns token + portal_url + expires_at + qr_data
- [x] `GET /guest-checkout/{token}` returns booking context + step definitions + completion state
- [x] `POST /guest-checkout/{token}/step/{key}` records step completion (3 keys, idempotent)
- [x] `POST /guest-checkout/{token}/complete` writes `guest_checkout_confirmed_at` + audit event (idempotent)
- [x] All 4 endpoints registered in `main.py`
- [x] 21/21 contract tests passing (`tests/test_guest_checkout_contract.py`)
- [x] Adjacent test suites clean (access_token, booking_guest_link, health — 43/43)

**Status: CLOSED — commit `63f9580`**  
**Next: Phase 1046 — Guest Checkout Portal UI**
