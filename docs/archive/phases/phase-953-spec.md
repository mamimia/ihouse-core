# Phase 953 — Check-in Flow Bug Fix: Task Completion, Booking State Guard, Guest Dedup

**Status:** Closed
**Prerequisite:** Phase 949 (Check-in Document Intake & Guest Identity Persistence)
**Date Closed:** 2026-03-27

## Goal

Audit and fix three critical bugs discovered during real worker check-in testing on staging:

1. **Complete Check-in did not finish operationally** — the booking remained in `confirmed` status because the `checkin` state guard rejected it (only allowed `active`/`observed`). The CHECKIN task also remained `ACKNOWLEDGED` because the wizard never called the task completion endpoint.

2. **Guest canonical-name overwrite appeared broken** — the identity chain was actually written correctly on first real run, but the booking was stuck at `confirmed` so the worker ran the wizard again, creating a new guest record.

3. **Duplicate guest records on repeat wizard runs** — the dedup logic only keyed on `passport_no`. When passport number was omitted (or empty), the dedup block was skipped entirely and a new guest was always inserted. A booking-anchor dedup fallback was missing.

## Invariants (Locked)

- `confirmed` bookings (manually-created) MUST be treated as a valid pre-arrival state for check-in. Operationally equivalent to `active`.
- Guest dedup MUST check `booking_state.guest_id` as a fallback anchor when no document number is provided. A booking can only have one canonical guest at a time.
- The CHECKIN task MUST be explicitly completed via `PATCH /worker/tasks/{task_id}/complete` as part of the Complete Check-in wizard action. The `/bookings/{id}/checkin` endpoint does not and should not auto-complete the task.
- Duplicate guest rows with identical `full_name + nationality` for the same booking are always bugs.

## Design / Files

| File | Change |
|------|--------|
| `src/api/booking_checkin_router.py` | MODIFIED — Phase C: Add `confirmed` to allowed check-in states (was: `active`, `observed` only). Also fixes error message text. |
| `src/api/checkin_identity_router.py` | MODIFIED — Phase B: Add booking-anchor dedup fallback: if no passport_no match found and booking already has a `guest_id` linked, reuse that guest record instead of inserting a new one. |
| `ihouse-ui/app/(app)/ops/checkin/page.tsx` | MODIFIED — Phase D: After successful `/bookings/{id}/checkin`, also call `PATCH /worker/tasks/{task_id}/complete` to formally close the CHECKIN task. Removes booking from active arrivals surface. |

## Staging Data Repair (Phase A — One-time, not a code change)

Executed directly on staging Supabase (tenant: `tenant_mamimia_staging`, booking: `MAN-KPG-502-20260326-f360`):

1. Deleted orphan guest `4c5d32e5` (Kiko Papir — booking name inserted as guest, no document)
2. Deleted orphan guest `1e9e895b` (Sam Longie — second run duplicate, no passport_no)
3. Kept canonical guest `fbe72e04` (Sam Longie + GT2345432 + Portugal)
4. Set `booking_state.guest_id = fbe72e04` (was pointing to deleted orphan)
5. Fixed `booking_state.status` from `confirmed` → `active`

Post-repair state: 1 guest record, correct canonical chain, booking ready for check-in.

## Dedup Priority Stack (New Canonical Rule)

```
1. Match by (passport_no + tenant_id)                — strongest: biometric document
2. Match by (booking_state.guest_id + tenant_id)     — booking already has a linked guest
3. CREATE new                                         — only if both above fail
```

## Result

**3 code files changed. 5 staging DB rows fixed.**
- Booking status guard now accepts `confirmed` bookings (unblocks all manually-created booking check-ins)
- Guest dedup now prevents duplicate creation on repeat wizard runs for the same booking
- CHECKIN task is formally completed when wizard reaches Complete Check-in — booking leaves worker arrival surface
