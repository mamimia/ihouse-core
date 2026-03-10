# Phase 194 — Booking → Guest Link

**Opened:** 2026-03-10
**Closed:** 2026-03-10
**Status:** ✅ Closed

## Goal

Best-effort nullable `guest_id` annotation on `booking_state`. Operator convenience — never affects the canonical event spine.

> **Architecture invariant:** `guest_id` is NOT written through `apply_envelope`. It is a sidecar annotation, like `source` or `property_id`. No FK constraint. Null = no link. Never blocks any booking mutation.

## New / modified files

| File | Change |
|------|--------|
| Supabase migration `add_guest_id_to_booking_state` | ADD COLUMN guest_id UUID NULLABLE + sparse index |
| `src/api/booking_guest_link_router.py` | NEW — POST link, DELETE unlink |
| `src/main.py` | + booking_guest_link_router registration |
| `tests/test_booking_guest_link_contract.py` | NEW — 11 tests |
| `ihouse-ui/app/bookings/[id]/page.tsx` | + GuestLinkPanel, guest_id to BookingState type, apiFetchMut |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/bookings/{id}/link-guest` | Body: `{guest_id}`. Validates both booking + guest for tenant. |
| `DELETE` | `/bookings/{id}/link-guest` | Sets `guest_id = NULL`. Idempotent. |

## UI — GuestLinkPanel

Mounted below the tab panel on `/bookings/[id]`:
- If linked: shows guest UUID → `/guests/{id}` link + "Unlink Guest" button
- If not linked: UUID input + "Link Guest" button + "Browse guests →" shortcut
- Flash success/error messages (auto-clear after 3s)

## Tests

```
pytest tests/test_booking_guest_link_contract.py -v → 11 passed
Full suite → exit 0, 0 regressions
npm run build → exit 0
```
