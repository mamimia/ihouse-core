# Phase 1066 — Guest Self-Checkout Resolution Fix

**Status:** Deployed  
**Date:** 2026-04-04  
**Commits:** `1868de0`, `d2c802a`, `<phase-1066>`  
**DB Migration:** `add_checkout_portal_missing_columns`  

---

## Problem statement

The guest self-checkout flow (`/guest-checkout/{token}`) was broken end-to-end
for the real Amuna Villa case (booking `ICAL-36ff7d9905e0`, original checkout Apr 7,
approved early checkout Apr 5). Clicking the "Start Self Check-Out →" CTA always
landed on **Link unavailable / Booking not found.**

Three distinct bugs were stacked on top of each other.

---

## Root causes (in order of execution)

### Bug 1 — Frontend: `undefined` token (Phase 1065B fix, commit `d2c802a`)

**File:** `ihouse-ui/app/(public)/guest/[token]/page.tsx` line 1097

```ts
// BEFORE
const token = params?.token as string;   // 'as string' is a TS lie — runtime value is still undefined

// AFTER
const token = (params?.token as string | undefined) ?? '';
```

`useParams()` in Next.js App Router can return `null` or `{}` on the first render
before hydration. The `as string` cast satisfies the TypeScript compiler but does not
prevent `undefined` at runtime. On first mount the `token` prop was literally
`undefined`, which template-interpolated to the string `"undefined"`:
`/guest-checkout/undefined`.

**Additional guard in `GuestCheckoutActions` useEffect:**

```ts
// Added before the fetch:
if (!token) return;   // never fire checkout-status with an empty token
```

Without this, the fetch fired as `/guest/undefined/checkout-status`, errored,
set `loadError=true` permanently — preventing the CTA from appearing even after
the real token arrived.

---

### Bug 2 — Frontend: self-checkout link used wrong token (Phase 1065B fix, commit `1868de0`)

**File:** `ihouse-ui/app/(public)/guest/[token]/page.tsx` line ~912

```tsx
// BEFORE
href={`/guest-checkout/${token}`}         // passes GUEST_PORTAL token to wizard

// AFTER
href={status.checkout_portal_url ?? `/guest-checkout/${token}`}
```

The guest portal page is served under a **GUEST_PORTAL** token
(`guest_token.py`, message format: `{booking_ref}:{email}:{exp}`, signed with
`IHOUSE_GUEST_TOKEN_SECRET`).

The checkout wizard (`/guest-checkout/{token}`) expects a **GUEST_CHECKOUT**
token (`access_token_service.py`, format: `guest_checkout:{entity_id}:{email}:{exp}`,
signed with `IHOUSE_ACCESS_TOKEN_SECRET`). The verification function
(`_verify_guest_checkout_token`) has a Path 2 fallback that accepts GUEST_PORTAL
tokens, but the GUEST_CHECKOUT verification in Path 1 always fails for a GUEST_PORTAL
token because:
- Different secret (`IHOUSE_ACCESS_TOKEN_SECRET` vs `IHOUSE_GUEST_TOKEN_SECRET`)
- Different message format (4-part vs 3-part)

Fix: the backend already generates the correct GUEST_CHECKOUT token and returns it
as `checkout_portal_url` in the `GET /guest/{token}/checkout-status` response
(Phase 1065B). The frontend CTA now uses that URL when available.

---

### Bug 3 — Database: missing columns caused booking lookup exception (Phase 1066, this phase)

**Migration:** `add_checkout_portal_missing_columns`  
**Applies to:** `booking_state` table

`_get_booking_for_portal()` in `guest_checkout_router.py` includes these columns
in its `SELECT`:

```python
.select(
    "booking_id, tenant_id, status, property_id, guest_name, guest_id, "
    "check_in, check_out, checked_out_at, "
    "early_checkout_approved, early_checkout_date, early_checkout_effective_at, "
    "early_checkout_status, "
    "guest_checkout_initiated_at, guest_checkout_confirmed_at, "
    "guest_checkout_steps_completed, guest_checkout_token_hash, "
    "used_guest_self_checkout, guest_checkout_contact_phone, guest_checkout_contact_email, "
    "guest_checkout_summary, deposit_status, opening_meter"   # ← THESE DID NOT EXIST
)
```

`deposit_status` and `opening_meter` were never migrated to the live database.
PostgreSQL throws an error when selecting non-existent columns, causing the
`except Exception: return None` path to fire → `booking = None` →
**"Booking not found."**

The same missing columns also caused `_generate_guest_checkout_url` (which reads
the same booking_state row via the checkout-status query) to fail silently, so
`checkout_portal_url` was always `null` and the GUEST_PORTAL fallback token was
always used — which then also failed at `_get_booking_for_portal`.

**Migration applied:**

```sql
ALTER TABLE public.booking_state
    ADD COLUMN IF NOT EXISTS deposit_status TEXT,
    ADD COLUMN IF NOT EXISTS opening_meter  TEXT;
```

This is the root cause that destroyed the entire fallback chain.

---

## Changes summary

| Layer | Change | Commit/Action |
|---|---|---|
| **Frontend** | Coerce `params?.token` with `?? ''` to prevent `undefined` at runtime | `d2c802a` |
| **Frontend** | Guard `GuestCheckoutActions` useEffect: skip if `!token` | `d2c802a` |
| **Frontend** | Use `status.checkout_portal_url` for self-checkout CTA URL | `1868de0` |
| **Database** | `ALTER TABLE booking_state ADD COLUMN deposit_status TEXT` | Supabase migration |
| **Database** | `ALTER TABLE booking_state ADD COLUMN opening_meter TEXT` | Supabase migration |

---

## Data model additions

### `booking_state.deposit_status`
- Type: `TEXT`, nullable
- Purpose: operational snapshot of deposit state at checkout time. Informational — not authoritative. The authoritative source is `cash_deposits.status`.
- Set by: future phase when deposit reconciliation is confirmed after checkout.

### `booking_state.opening_meter`
- Type: `TEXT`, nullable
- Purpose: electricity/utility meter reading taken at guest check-in (opening reading for end-of-stay electricity cost settlement).
- Set by: check-in worker photo or manual entry. Future phase.

---

## Flow after fix

```
1. Guest opens portal: /guest/{GUEST_PORTAL_TOKEN}
   → useParams() correctly resolved, token = 'ICAL-36ff...' encoded GUEST_PORTAL token
   → GuestCheckoutActions fetches /guest/{token}/checkout-status
   → Backend resolves GUEST_PORTAL token → booking_ref = ICAL-36ff7d9905e0
   → Queries booking_state: all columns now exist → returns row
   → self_checkout_eligible = true (within 24h of Apr 5 effective checkout)
   → _generate_guest_checkout_url() called → issues GUEST_CHECKOUT token
   → returns checkout_portal_url = https://domaniqo-staging.vercel.app/guest-checkout/{CHECKOUT_TOKEN}

2. Guest clicks "Start Self Check-Out →"
   → href = status.checkout_portal_url (GUEST_CHECKOUT token URL)
   → navigates to /guest-checkout/{CHECKOUT_TOKEN}

3. Wizard loads: GET /guest-checkout/{CHECKOUT_TOKEN}
   → _verify_guest_checkout_token: Path 1 succeeds (proper GUEST_CHECKOUT token)
   → entity_id = ICAL-36ff7d9905e0
   → _get_booking_for_portal(db, 'ICAL-36ff7d9905e0')
   → all columns exist → booking returned → wizard renders

4. Guest completes steps → POST /guest-checkout/{token}/complete
   → booking_state.guest_checkout_confirmed_at = now
   → booking_state.used_guest_self_checkout = true
   → audit_events entry written
   → chat system message written → OM sees closure in inbox
```

---

## What remains open from Phase 1065

All items in the "What remains open" section of Phase 1065 are unchanged:
1. `sender_type="system"` rendering in ConversationThread — cosmetic
2. `confirm_contacts` step in checkout portal — enhancement
3. OM inbox alert for `GUEST_EARLY_CHECKOUT_REQUESTED` — enhancement  
4. Portal token TTL reset when early checkout is approved — operational gap

---

## Checks

- DB migration: `add_checkout_portal_missing_columns` → **applied** ✅
- `npx next build` → **exit 0** ✅
- `npx vercel --prod --yes` → **exit 0** ✅ → `https://domaniqo-staging.vercel.app`
- Railway backend: `GET /health` → `{"status":"ok"}` ✅
- Booking `ICAL-36ff7d9905e0` full SELECT (all columns) → row returned ✅
