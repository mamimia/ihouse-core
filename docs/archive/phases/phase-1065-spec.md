# Phase 1065 — Guest Portal: Early Check-Out Request + Self Check-Out

**Status:** Implemented  
**Date:** 2026-04-04  
**Commit:** `1af5316`  
**Files Changed:**
- `src/api/guest_portal_router.py` (2 new endpoints)
- `ihouse-ui/app/(public)/guest/[token]/page.tsx` (new component + render injection)

---

## Current real state (before this phase)

| Capability | Before |
|---|---|
| **Ops/admin early checkout pipeline** | ✅ Fully implemented (Phase 998) — request, approve, revoke, task/cleaning rescheduling |
| **Guest conversation thread** | ✅ Fully implemented (Phase 670 / 1053) — guest sends messages, OM replies |
| **Guest portal checkout status** | ❌ Missing — no guest-facing endpoint revealing effective checkout date, early checkout state, or self-checkout eligibility |
| **Guest "Request Early Check-Out" action** | ❌ Missing — guest had no way to formally request an early departure from the portal |
| **Guest Self Check-Out CTA in main portal** | ❌ Missing — the `/guest-checkout/{token}` step portal (Phase 1045) existed but was never surfaced from the main guest portal |
| **Effective checkout window driving Self CTA** | ❌ Missing — the 24h window logic existed in the token TTL calculation but not as a guest-facing eligibility signal |

---

## What was built

### Backend — `GET /guest/{token}/checkout-status`

Pure read endpoint. Returns everything the portal needs to decide which actions to show:

```json
{
  "booking_id": "...",
  "original_checkout_date": "2026-07-25",
  "effective_checkout_date": "2026-07-22",           // early if approved, else original
  "is_early_checkout_approved": true,
  "early_checkout_status": "approved",               // none | requested | approved | completed
  "already_requested_early_checkout": true,
  "self_checkout_eligible": false,                   // true if now within 24h of effective checkout
  "valid_early_request_dates": ["2026-07-21", "2026-07-22", "2026-07-23", "2026-07-24"],
  "guest_checkout_confirmed": false
}
```

**24h window logic:**
1. If `early_checkout_effective_at` (precise TIMESTAMPTZ) exists → `eligible = now >= effective_at - 24h`
2. Else → assume checkout date at 11:00 UTC → `eligible = now >= (checkout_date 11:00 UTC) - 24h`

**valid_early_request_dates** — computed bounded list:
- Starts from `max(today, check_in_date)`
- Ends the day BEFORE `check_out` (original)
- The original checkout date is excluded — requesting that date is not an "early" departure

### Backend — `POST /guest/{token}/request-early-checkout`

```json
// Request body
{ "requested_date": "2026-07-22", "reason": "flight change" }

// Success response
{
  "status": "request_received",
  "booking_id": "...",
  "requested_date": "2026-07-22",
  "early_checkout_status": "requested",
  "message_id": "uuid",
  "detail": "Your request to check out on July 22, 2026 has been received..."
}
```

**What happens on submit:**
1. Date validated against `valid_early_request_dates` window
2. `booking_state` updated: `early_checkout_requested_at`, `early_checkout_request_source=guest_portal`, `early_checkout_status=requested`, `early_checkout_date` (informational, not binding)
3. Chat message inserted to `guest_chat_messages` with `sender_type="system"`:
   ```
   [Early Checkout Request]
   The guest has requested to check out early.
   Requested date: July 22, 2026
   Reason: flight change
   Please confirm or contact the guest to arrange the early departure.
   ```
4. SSE push to OM: `GUEST_EARLY_CHECKOUT_REQUESTED` event
5. Idempotent: if `ec_status` is already `requested|approved|completed`, returns `already_requested` without re-writing

**Admin pipeline: UNCHANGED.** The guest request surfaces in the OM inbox as a chat message. The OM then processes it via the existing `/admin/bookings/{id}/early-checkout/approve` endpoint.

---

## Frontend — `GuestCheckoutActions` component

Self-managing component placed after `YourStay`, before the footer. Fetches `/checkout-status` on mount, returns `null` while loading or if the endpoint fails.

### State machine — what the component shows

| Condition | What renders |
|---|---|
| `status = null` or load failed | Nothing |
| `guest_checkout_confirmed = true` | Nothing |
| `self_checkout_eligible = true` | **Self Check-Out CTA** (Flow B) |
| `is_early_checkout_approved = true` AND not yet in window | **Approved confirmation** card |
| `already_requested_early_checkout = true` AND not approved | **Request pending** card |
| `valid_dates.length > 0` AND none of the above | **Request Early Check-Out** collapsible card (Flow A) |
| None of the above | Nothing (mid-stay, no special action needed) |

### Flow A — Request Early Check-Out

- Collapsible card showing current scheduled checkout date
- When expanded: radio button list of `valid_early_request_dates` (no free calendar, no past dates, no dates beyond original checkout)
- Optional reason textarea (200 char max)
- On submit: calls `POST /request-early-checkout`, optimistic state transition
- Error handling: shows inline error message on failure

### Flow B — Self Check-Out

- Appears only within 24h of effective checkout
- Copy adapts: shows early checkout date if approved, original date otherwise  
- **Financial honesty card:** "our team will complete a final review — deposit/electricity to be handled after inspection"
- **Contact continuity reminder:** "make sure your host has your correct phone or email"
- CTA button: `Start Self Check-Out →` → links to `/guest-checkout/{token}` (Phase 1045 step portal)

---

## How effective checkout changes the logic

When admin approves an early checkout (via `early_checkout_router.py`):
1. `early_checkout_approved = true`
2. `early_checkout_date = <new date>`
3. `early_checkout_effective_at = <precise TIMESTAMPTZ>`

The `/checkout-status` endpoint picks this up:
- `effective_checkout_date` changes to the approved early date
- `self_checkout_eligible` uses `effective_at - 24h` as the window start
- Self Check-Out CTA appears 24h before the approved early date
- All date range calculations shift to the new effective date

---

## Chat / messaging integration

The guest's early checkout request writes a `sender_type=system` message to `guest_chat_messages`. This means:
- It appears in the OM's conversation inbox immediately
- It follows the existing thread for this booking (scoped by `booking_id`)
- It does NOT appear as a guest bubble — it renders as a system/notification message
- The existing `/guest/{token}/messages` endpoint returns this message in the thread, so the guest also sees their request in the conversation

> [!NOTE]
> The `sender_type="system"` value is new. The frontend `ConversationThread` component currently shows `sender_type="guest"` and `"host"` with different styles. The system message will render in the thread but without special styling differentiation until the conversation component is updated to handle `sender_type="system"` distinctly.

---

## Contact continuity

The Self Check-Out CTA block includes a prominent reminder:
> 📞 Make sure your host has your correct phone or email in case they need to reach you after checkout.

This is a presentation-layer nudge, not a form. The rationale is:
- The guest already provided contact details during booking
- Forcing a re-entry form adds friction to the checkout flow
- The reminder is sufficient for the common case (guest checks their info is correct)

If the property requires verified contact before checkout, a future phase can add a `confirm_contacts` step to the guest checkout portal (Phase 1045 step sequence).

---

## What remains open

### 1. `sender_type="system"` rendering in ConversationThread
The frontend `ConversationThread` component only handles `guest` and `host` render paths. A system message will render but without dedicated styling (no special background, icon, or label). A future polish pass should add a `system` message card style.

### 2. Contact confirmation step in checkout portal
The Phase 1045 guest checkout portal (`/guest-checkout/{token}`) has steps: confirm_departure, key_handover, feedback. A `confirm_contacts` step that captures or verifies phone/email before finalizing checkout would close the contact continuity gap completely.

### 3. OM inbox — early checkout request flag
The OM inbox (guest dossier) currently shows early checkout state. But the new `GUEST_EARLY_CHECKOUT_REQUESTED` SSE event is not yet wired to a notification badge or alert in the OM dashboard. A future phase should surface this event as a distinct alert.

### 4. Guest portal token expiry on early checkout
When early checkout is approved, the portal token TTL is recalculated based on `early_checkout_effective_at + 4h`. This means the portal could expire before a late-arriving guest realizes they're in the self-checkout window. Staff should re-issue the token (via `/bookings/{id}/guest-checkout-token`) when approving early checkout to reset the TTL.

---

## Checks

- `npx tsc --noEmit` → **0 errors** ✅
- `python3 -m py_compile guest_portal_router.py` → **0 errors** ✅
- `vercel --prod` → **exit 0** ✅ → `https://domaniqo-staging.vercel.app`
