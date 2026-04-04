# Phase 1067 — Guest Checkout Wizard: Completion Fix + Property Name + Copy Polish

**Status:** Deployed  
**Date:** 2026-04-04  
**Commit:** `3c4d9df`  
**Files Changed:**
- `src/api/guest_checkout_router.py`
- `ihouse-ui/app/(public)/guest-checkout/[token]/page.tsx`

---

## Context

Phase 1066 resolved the entry blocker (token, Booking not found). The wizard now opened
successfully. This phase fixes the remaining blockers that prevented the flow from completing.

---

## Root causes fixed

### Bug 1 — PRIMARY BLOCKER: `confirm_departure` never submitted → `/complete` always rejected

**File:** `ihouse-ui/app/(public)/guest-checkout/[token]/page.tsx`

`_REQUIRED_FOR_COMPLETE` on the backend requires:
```
confirm_departure, ac_lights, doors_locked, key_handover, contact_confirm
```

`handleStepAction` had a guard:
```ts
// BEFORE
if (stepId !== 'ready' && stepId !== 'proof_photos') {
    await submitStep(stepId === 'contact' ? 'contact_confirm' : stepId, data);
}
```

Step 0 (`ready`) was explicitly excluded from API calls — the same exclusion as the
purely frontend-side `proof_photos` step. However `confirm_departure` is **required**
for completion. Because it was never POSTed, `POST /guest-checkout/{token}/complete`
always returned:
```json
{"code": "STEPS_INCOMPLETE", "missing_steps": ["confirm_departure"]}
```
The frontend caught this as `stepError` and displayed it inline — appearing to the
guest as a frozen state on both Skip and Confirm button presses.

**Fix:**
```ts
// AFTER
const backendStepId =
    stepId === 'ready'   ? 'confirm_departure' :
    stepId === 'contact' ? 'contact_confirm'   :
    stepId;
if (stepId !== 'proof_photos') {
    await submitStep(backendStepId, data);
}
```
`proof_photos` remains frontend-only. All other steps including `ready` now submit
to their correct backend step keys.

---

### Bug 2 — Property name showed `KPG-500` instead of `Emuna Villa TEST`

**File:** `src/api/guest_checkout_router.py`

`_get_property_for_portal` SELECT included `name`:
```python
# BEFORE
.select("property_id, display_name, name, address, city, country, ...")
```
`properties.name` **does not exist** in the live database — only `display_name` exists.
PostgreSQL throws on an unknown column → `except Exception: return None` fires →
`prop = None` → `(prop or {}).get("display_name")` = None → falls back to `property_id`
= `"KPG-500"`.

The same `.get("name")` reference appeared in 4 places:
1. `_get_property_for_portal` SELECT (throws on query)
2. `"name"` key in `GET /guest-checkout/{token}` response builder
3. `complete_guest_checkout` idempotent return path
4. `complete_guest_checkout` new confirmation path

All four fixed:
```python
# AFTER
.select("property_id, display_name, address, city, country, ...")
# ...
property_name = (prop or {}).get("display_name") or property_id
```

---

## Completion flow after fix

```
Guest presses "Let's go →" on Step 1 (Ready to leave)
  → POST /guest-checkout/{token}/step/confirm_departure   ← NOW FIRES (was skipped)
  → { "status": "step_completed", "step_key": "confirm_departure", ... }

Guest advances through Steps 2–6
  → Step 2: POST /step/ac_lights
  → Step 3: POST /step/doors_locked
  → Step 4: POST /step/key_handover
  → Step 5: proof_photos — frontend only, no POST
  → Step 6: POST /step/contact_confirm

Guest on Step 7 (Feedback):
  → Skip:    rating=null, comment='' → no feedback POST → POST /complete
  → Confirm: rating=N or comment=X → POST /step/feedback first → POST /complete

POST /complete:
  → backend verifies all 5 required steps are present in steps_completed ✓
  → writes guest_checkout_confirmed_at, used_guest_self_checkout=True, summary
  → writes system chat message (OM sees in stay thread)
  → writes audit event GUEST_CHECKOUT_CONFIRMED
  → returns { status: "confirmed", confirmed_at, guest_name, property_name, summary, pending_items }

Frontend: setCompleted(result) → renders SummaryScreen
```

---

## Final confirmation screen (SummaryScreen)

The screen that now appears after successful completion:

| Section | Content |
|---|---|
| **Hero** | ✅ "Checkout complete" — green heading |
| **Timestamp** | Exact UTC ISO timestamp formatted as: `Saturday, April 5, 2026 at 11:34:22 AM UTC` |
| **You confirmed** | Checklist: vacated ✓, AC/lights ✓, doors ✓, keys ✓ (with handover method) |
| **Follow-up contact** | 📞 phone / ✉️ email the guest left |
| **What happens next** | Shown when deposit or electricity review is pending: "Our team will complete a final review including deposit review, electricity settlement. We'll contact you if anything needs clarifying." |
| **Your feedback** | Star rating + comment, only shown if the guest left something |
| **Farewell** | "We hope you had a wonderful stay. 🌟 Safe travels — we look forward to welcoming you back." |

---

## Deposit / electricity follow-up messaging

The pending review block appears on the completion screen when:
- `deposit_status` is not in `(returned, waived, na, n/a, none, unknown)` → shows "deposit review"
- `opening_meter` is non-null → shows "electricity settlement"

For Amuna Villa: both columns are currently `null` (added in Phase 1066), so the
pending block is **not shown** (property_inspection is excluded as that is always internal).
When a future operator fills in `opening_meter` or the deposit is in a review state,
the notice will appear automatically.

The backend also always writes the pending context into `guest_checkout_summary.pending_items`.

---

## Copy changes

| Step | Before | After |
|---|---|---|
| Step 1 checkbox | "I confirm that I and all guests are ready to leave and have collected all our belongings." | "I confirm that all guests and I are ready to leave and have collected all our belongings." |
| Step 2 subtitle | "A small habit that makes a big difference." | "A quick check before you go." |
| Step 2 checkbox | "I've turned off the air conditioning, all lights, fans, and any other appliances." | "I've turned off the AC, all lights, fans, and appliances." |
| Step 3 subtitle | "Just a quick check before you go." | "All locked before you leave." |
| Step 7 subtitle | "This is completely optional — skip if you'd prefer." | "Entirely optional — skip if you'd prefer." |
| Confirm button label (active) | "Confirm checkout →" | "Confirm Check-Out →" |
| Confirm button label (loading) | "Saving…" | "Confirming…" |
| Skip button | Was not disabled during submit | Now disabled during submit (prevents race condition) |

---

## Checks

- `python3 -m py_compile guest_checkout_router.py` → **0 errors** ✅
- `npx tsc --noEmit` → **0 errors** ✅
- `npx vercel --prod --yes` → **exit 0** ✅ → `https://domaniqo-staging.vercel.app`
- Railway: `uptime_seconds: 91` at check time → redeployed ✅
