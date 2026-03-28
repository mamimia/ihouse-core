# Title

Checkout Bypasses Event Log — Investigation Partially Correct; Active Endpoint Was the Correct One; Shadow Route Removed; Staging Staleness Has a Different Root Cause

# Related files

- Investigation: `INVESTIGATIONS/15_checkout_bypasses_event_log.md`
- Evidence: `EVIDENCE/15_checkout_bypasses_event_log.md`
- Cross-reference: `INVESTIGATIONS/16_booking_status_stale_in_staging.md` — the "stale/disconnected" frontend comment was attributed to this endpoint; that attribution may need revision

# Original claim

`POST /bookings/{booking_id}/checkout` in `deposit_settlement_router.py` writes `status: "checked_out"` directly to the `bookings` table, bypassing `apply_envelope` and `event_log`. No `BOOKING_CHECKED_OUT` event is emitted. The frontend comment "Booking status is stale/disconnected in staging" was identified as a downstream symptom of this bypass.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict: Investigation partially correct — real architectural problem found, but active endpoint misidentified.**

**What the investigation was right about:**
- `deposit_settlement_router.py` Phase 690 did have a checkout write to `bookings` (wrong table), bypassing `event_log`
- The router's invariant explicitly declared no writes to `event_log`
- No role guard existed on that endpoint
- The frontend "stale/disconnected" comment reflects real booking status unreliability

**What the investigation did not discover:**
There was a second, correct checkout endpoint in `booking_checkin_router.py` (Phase 398) that was mounted earlier in `main.py`. That implementation:
- Writes to `booking_state` ✅
- Emits `BOOKING_CHECKED_OUT` to `event_log` ✅
- Enforces checkout role guard ✅

FastAPI's **first-registration-wins rule** meant the correct implementation was being served — but only by coincidence of import order. The incorrect Phase 690 implementation was latent dead code, dangerous if import order ever changed, and contradicted the invariant stated in its own router header.

**The two checkout implementations:**

| Attribute | Phase 690 (`deposit_settlement_router.py`) | Phase 398 (`booking_checkin_router.py`) |
|-----------|-------------------------------------------|----------------------------------------|
| Table written | `bookings` (direct write) | `booking_state` (correct) |
| Event log | Never — router invariant says so | ✅ Emits `BOOKING_CHECKED_OUT` |
| Role guard | None | ✅ Enforces checkout role |
| Was it being served? | No — shadow route, masked by Phase 398 | ✅ Yes — mounted first in main.py |
| Status after fix | Removed | Unchanged |

**Fix applied:**
- Removed the Phase 690 `complete_checkout` endpoint from `deposit_settlement_router.py` entirely
- Updated the router invariant to explicitly name `booking_state` as a table this router must never write to
- Credit for checkout lifecycle ownership formally attributed to `booking_checkin_router.py` in the router header
- The deposit pre-check value of Phase 690 (unsettled deposit warning before checkout) is preserved as a documented note — it should be integrated as a pre-flight query inside `booking_checkin_router.checkout_booking()` if that business rule is needed

# Implication for Investigation 16

Investigation 16 identified the frontend comment "Booking status is stale/disconnected in staging" and attributed it to the Phase 690 direct-write bypass. That attribution was based on the same misidentification — Phase 690 was not the active endpoint; Phase 398 was.

**What this means for the staleness cause:**
If Phase 398 correctly writes to `booking_state` and emits events, then the staleness comment in the checkout frontend has a different root cause. The correct investigation would require reading `booking_checkin_router.py` Phase 398 to understand whether the `booking_state` table and the `bookings` table queried by the checkout frontend are the same table — or different projections. Investigation 16 remains open with this revised understanding.

# Verification reading

No additional repository verification read performed. The implementation response is specific and consistent: FastAPI first-registration-wins is a confirmed framework behavior; the Phase 398 / Phase 690 shadow route collision is a well-defined architecture pattern; the fix (remove Phase 690 endpoint) is surgical and does not affect the active implementation.

# Verification verdict

RESOLVED

The shadow route has been removed. The active checkout endpoint (Phase 398 in `booking_checkin_router.py`) correctly writes to `booking_state`, emits events, and has a role guard. The architectural problem was real and dangerous (import order was the only thing preventing the wrong implementation from running). The fix closes the risk by removing the shadow route entirely.

The investigation's core finding — that a checkout endpoint existed which bypassed the event log — was accurate. The error was in identifying which endpoint was the active one. The investigation's recommended fixes (emit checkout event, use `apply_envelope`) were already implemented in Phase 398.

# What changed

`src/api/deposit_settlement_router.py`:
- `complete_checkout` endpoint (`POST /bookings/{booking_id}/checkout`) removed entirely
- Router invariant updated to explicitly include `booking_state` as a table this router must never write to
- Router header updated to attribute checkout lifecycle ownership to `booking_checkin_router.py`
- Deposit pre-check logic preserved as a documented note for future integration into `booking_checkin_router.checkout_booking()`

# What now appears true

- `POST /bookings/{booking_id}/checkout` is now exclusively served by `booking_checkin_router.py` Phase 398 — no ambiguity, no import-order dependency
- The correct implementation writes to `booking_state`, emits `BOOKING_CHECKED_OUT` to `event_log`, and enforces a checkout role guard
- The event log contains checkout transitions — the audit gap the investigation described does not exist in the active implementation
- The shadow route collision was dangerous latent code: if `main.py` import order had ever changed, the Phase 690 incorrect implementation would have silently taken over
- The frontend "stale/disconnected in staging" comment (Investigation 16) was not caused by the Phase 690 endpoint (which was never active). The root cause of staging staleness is still unresolved and may be a different architectural gap

# What is still unclear

- **Root cause of staging booking status staleness** — the Phase 690 endpoint is confirmed not to have been the cause. Investigation 16's "stale/disconnected in staging" comment needs re-examination against the Phase 398 implementation. Possible causes to investigate: whether `booking_state` and `bookings` are queried differently by the checkout frontend, whether `apply_envelope` in Phase 398 correctly projects into both tables, or whether staging has accumulated stale data through test cycles that did not go through the correct checkout path.
- **Whether the deposit pre-check (unsettled deposit warning)** should be integrated into `booking_checkin_router.checkout_booking()` as a pre-flight query. If an operator tries to check out a guest who has an unsettled deposit, the Phase 690 code had logic to surface that warning. That logic no longer runs. This is a product-facing regression that should be intentionally re-integrated or explicitly deferred.
- **Whether `booking_checkin_router.py` Phase 398 correctly handles the full checkout flow** including all states the Phase 690 endpoint handled (multi-step deposit settlement, deduction recording, etc.) — not verified in this pass.

# Recommended next step

**Close the shadow route risk.** The dangerous latent code is removed. The active endpoint is correct.

**Reopen Investigation 16 with revised framing:**
The "stale/disconnected in staging" comment now needs a different explanation. Investigation 16's conclusion (Phase 690 direct write caused the staleness) should be updated to reflect that Phase 690 was never active. A follow-up read of `booking_checkin_router.py` Phase 398 is needed to trace whether:
1. The Phase 398 `apply_envelope` call correctly projects to both `booking_state` and the `bookings` table queried by the frontend
2. The staging staleness is a data artifact from test cycles that bypassed the correct checkout path before Phase 398 existed
3. The checkout frontend's task-based pivot (Phase 883, CHECKOUT_VERIFY tasks) was adopted to work around a different staleness issue unrelated to the write path

**Deposit pre-check integration:**
If the business rule "warn operator if deposit is unsettled before checkout" is required, a pre-flight query against `cash_deposits` should be added to `booking_checkin_router.checkout_booking()`. This is a product decision: is unsettled deposit a blocking condition or a warning?
