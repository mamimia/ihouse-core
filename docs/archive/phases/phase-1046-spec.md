# Phase 1046 — Current Stay Portal v1 Enhancement: Departure Block

**Phase:** 1046  
**Status:** OPEN  
**Depends on:** Phase 1045 (CLOSED — backend foundation, token system, step-tracking endpoints)  
**Phase type:** Frontend enhancement — additive section inside existing portal

---

## Framing

This phase adds a **Departure Block** as a new section inside the existing
**Current Stay Portal** (`/guest/[token]`).

This is NOT a new guest portal. It is NOT a separate guest checkout app.
The Current Stay Portal is one continuous product experience from post-check-in
through departure and a short grace window after checkout.

The Departure Block is the guest's departure path inside that experience.

---

## Surface Definitions (mandatory from Phase 1046 onwards)

| Term | What it is |
|---|---|
| **Worker Checkout Wizard** | Staff-only operational surface at `/ops/checkout`. Inspection, deposit, meter, issue flagging. Do NOT touch this workstream here. |
| **Current Stay Portal** | Guest-facing surface at `/guest/[token]`. One continuous portal from check-in to post-departure. |
| **Departure Block** | A new section inside the Current Stay Portal. Guest-side departure guidance and confirmation. |

---

## Current Stay Portal Structure After This Phase

```
/guest/[token]
├── Welcome / Stay Header          (existing)
├── Home Essentials                (existing)
├── How This Home Works            (existing)
├── Need Help                      (existing)
├── Around You                     (existing)
├── Your Stay                      (existing — guest count, deposit status)
├── Departure Block                ← NEW in Phase 1046
└── (future) Save This Stay        ← placeholder, out of scope
```

---

## Departure Block — Product Spec

### When to show
The Departure Block is visible from check-in through approximately 4 hours
after the effective checkout time (the token's natural expiry window).

- If `already_confirmed = true`: show a "You've completed checkout" confirmation state
- If `already_confirmed = false`: show the active departure guidance flow
- If the token is expired (portal 401s): the block is irrelevant (portal is gone)

### What it contains

#### A. Departure timing card
- Shows effective checkout time (pulls from /guest-checkout/{token} `booking.effective_checkout_date`)
- If early checkout approved: shows the early checkout date prominently, NOT the original
- Shows property checkout time (e.g. "11:00 AM")

#### B. Departure checklist
Three steps, rendered as guest-confirmable cards:

1. **Confirm Departure** (`confirm_departure`) — required
   - "Confirm that you and all guests have vacated the property and collected all belongings"
   - Guest taps to confirm → calls `POST /guest-checkout/{token}/step/confirm_departure`

2. **Key / Access Return** (`key_handover`) — required
   - "Confirm that all keys, key cards, and access devices have been returned as instructed"
   - Guest taps to confirm → calls `POST /guest-checkout/{token}/step/key_handover`

3. **Leave Feedback** (`feedback`) — optional, never blocks
   - Star rating (1–5) + optional short text
   - Guest submits → calls `POST /guest-checkout/{token}/step/feedback` with `{rating, comment}`
   - Label: "Optional — takes 30 seconds"

#### C. Complete departure button
- Active only when `confirm_departure` + `key_handover` are both done
- Calls `POST /guest-checkout/{token}/complete`
- On success: shows a "Thank you" confirmation card (replaces the checklist)
- Idempotent: if already confirmed, shows the confirmation state on load

### Visual behaviour
- Steps transition from "pending" → "confirmed" state inline (no page reload)
- Confirmed steps show a checkmark and grey out (but remain visible)
- Complete button is disabled until required steps are done (not hidden)
- Feedback step is shown after the other two complete, with "optional" label

---

## Token Architecture for Phase 1046

### Two token systems exist — they serve different purposes

| System | Token type | Route | Purpose |
|---|---|---|---|
| Old HMAC guest token | `guest_tokens` table | `/guest/{token}` | Core stay portal — issued at check-in, 30-day TTL |
| New access_token | `GUEST_CHECKOUT` in `access_tokens` | `/guest-checkout/{token}` | Departure-side backend — issued by staff, booking-date-anchored TTL |

### Integration approach for Phase 1046

The Departure Block lives inside `/guest/[token]` (the old token route / page).  
The backend step-tracking calls use the **new GUEST_CHECKOUT token** from the
`/guest-checkout/{token}` API.

This means the guest stay portal needs access to the GUEST_CHECKOUT token.
Resolution: the portal backend (`/guest/portal/{token}`) enriches the response
with the `guest_checkout_token` (if one has been issued for this booking).

The frontend then uses:
- The old guest token for the portal shell and existing sections
- The GUEST_CHECKOUT token for all Departure Block API calls

This keeps the guest-facing URL unified (`/guest/{token}`) while allowing the
departure backend to use the proper token type.

### Required backend change (small)
Add `guest_checkout_token: str | None` to the `/guest/portal/{token}` response.
Look up from `access_tokens` where `token_type = 'guest_checkout'` and `entity_id = booking_id`
and `revoked_at IS NULL` and `expires_at > now()`, order by created_at DESC, limit 1.
Return the raw token (not the hash) so the frontend can use it directly.

This is a read-only query addition — no new write path.

---

## What Does NOT Belong Here

| Out of scope | Belongs to |
|---|---|
| Property inspection | Worker Checkout Wizard |
| Deposit deduction | Worker Checkout Wizard |
| Closing meter reading | Worker Checkout Wizard |
| `POST /bookings/{id}/checkout` (status → checked_out) | Worker Checkout Wizard |
| Settlement finalization | Worker Checkout Wizard |
| QR generation/delivery for the GUEST_CHECKOUT token | Phase 1047 |
| Escalation if guest doesn't complete | Phase 1048 |
| Regression test pass | Phase 1049 |

---

## Direct-Write Architectural Debt (carried from Phase 1045 audit)

The Departure Block backend writes to `booking_state` directly
(`guest_checkout_steps_completed`, `guest_checkout_confirmed_at`, `guest_checkout_initiated_at`).

This is consistent with the operational layer's established direct-write pattern
(used by `booking_checkin_router`, `early_checkout_router`, `self_checkin_portal_router`).

The applies-only-to-OTA `apply_envelope` / `CoreExecutor` path is **not** used here.

**Product constraint (non-negotiable from Phase 1045 audit):**
Guest-side writes must remain limited to additive, telemetry-only columns.
They must never mutate booking state-machine fields (`status`, `checked_out_at`, etc.).

The broader architectural decision about whether to formalize a canonical path for
operational-layer mutations is deferred and will be addressed as a system-wide
concern, not as a guest-portal-specific patch.

---

## Closure Conditions

- [ ] `/guest/portal/{token}` backend enriched with `guest_checkout_token` (read-only)
- [ ] Departure Block component added to `/guest/[token]/page.tsx` as Section 7
- [ ] Departure timing card shows effective checkout date (handles early checkout)
- [ ] Three step cards render with correct labels and step instructions
- [ ] Step confirmation calls `POST /guest-checkout/{token}/step/{key}` correctly
- [ ] Steps transition to confirmed state inline after API success
- [ ] Required step guard: Complete button disabled until `confirm_departure` + `key_handover` done
- [ ] Feedback step marked as optional, does not block Complete
- [ ] Complete departure calls `POST /guest-checkout/{token}/complete`
- [ ] Already-confirmed state detected on load and shown correctly (no re-confirmation prompt)
- [ ] No flashy departure UI shown when `guest_checkout_token` is not yet issued (graceful fallback)
- [ ] Portal shell sections (Welcome, Essentials, etc.) unaffected
- [ ] Staging proof: screenshots of departure block in both "active" and "confirmed" states

**Status: OPEN**
