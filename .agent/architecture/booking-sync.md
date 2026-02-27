# Booking Sync & Source of Truth

## Core Principle
External platforms are authoritative for booking timeframes.
Internal system validates and reacts. It does not silently override.

---

## Source of Truth Hierarchy

1. Airbnb
2. BookingCom
3. DirectBooking

If conflict exists:
External platform wins on timeframe.
No automatic cancellation is allowed.

---

## External Change Overlap with DirectBooking

Scenario:
An external platform creates or modifies a booking that overlaps an existing DirectBooking.

System behavior:

1. Detect overlap.
2. Mark DirectBooking as PendingResolution.
3. Set Property state to AtRisk.
4. Create ConflictTask assigned to OperationalManager.
5. Write audit event.
6. Notify OperationalManager immediately.
7. If not acknowledged within SLA → escalate to Admin.
8. No automatic cancellation of external booking.
9. DirectBooking remains blocked until manual resolution.

Resolution options (Admin or authorized OperationalManager):
1. Cancel DirectBooking
2. Reassign guests to another property (RelocationTask)
3. Manually override with explicit audit log entry

All actions must generate audit entries.

---

## Booking Creation Rules

When creating DirectBooking:

1. Validate against synced external calendar snapshot.
2. If overlap detected:
   - Reject creation.
   - Write audit log.
3. If valid:
   - Create DirectBooking.
   - Push block to external calendars if integration supports it.
4. No silent creation allowed.

---

## Booking Lifecycle

Booking states:

1. Scheduled
2. InStay
3. Completed
4. Cancelled
5. PendingResolution

Transitions:

1. Scheduled → InStay on check-in completion
2. InStay → Completed on check-out completion
3. Any → PendingResolution on detected conflict
4. Any → Cancelled only via:
   - External cancellation event
   - Explicit Admin action

All transitions must generate audit entries.