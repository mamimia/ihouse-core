# System Flow Map – End to End Logic

## 1. Booking Created (External or Direct)

Trigger:
New booking received.

System actions:
1. Validate no overlap.
2. If conflict:
   - Booking → PendingResolution
   - Property → AtRisk
   - Create ConflictTask
   - If OperationalManager does not have can_booking_override:
     Any override action must create OverrideRequest in PendingApproval.
     Admin approval required before execution.
   - While PendingResolution exists:
     Property remains AtRisk.
     Booking remains PendingResolution.
   - No automatic unblocking is allowed.
3. If valid:
   - Booking → Scheduled
   - Write audit event.

---

## 2. Pre Check-in Window

Condition:
Upcoming check-in within configurable hours (default 6h)

System checks:
1. Property state must be Ready.
2. No Critical issues.
3. Cleaning must be completed.

If violation:
Property → AtRisk
Create AlertTask
Escalate per SLA.

## 2.1 Late Check-out Request Rule
1. Late check-out is always a request, never an automatic approval.
2. System must validate remaining buffer until next check-in.
3. If remaining buffer is below minimum buffer policy:
   Request is auto rejected.
   Audit event required.
4. If allowed:
   Request enters PendingApproval for Admin or authorized OperationalManager.
   Approval writes audit event.


---

## 3. Check-out Completed

Trigger:
Check-in staff completes check-out.

System actions:
1. Booking → Completed
2. Create CleaningTask
3. Property → Cleaning
4. Write audit event.

---

## 4. Cleaning Completed

Trigger:
Cleaner marks Ready.

Validation:
Checklist complete
Required photos uploaded
No unresolved Critical issue

If valid:
Property → Ready
Write audit event.

If invalid:
Reject completion.

---

## 5. Check-in Completed

Trigger:
Check-in staff completes check-in.

System actions:
Booking → InStay
Property → Occupied
Write audit event.

---

## 6. Issue Created

Severity:
Normal or Critical

If Normal:
Create IssueTask
Assign Maintenance or Ops
Property may move to AtRisk depending on context.

If Critical:
Property → Blocked
Create IssueTask
Start 5 minute SLA
Escalate if not acknowledged.

## 6.1 Ready Override on New Issue
1. If property is Ready and a new Normal issue is created:
   Property -> AtRisk immediately.
2. If property is Ready and a new Critical issue is created:
   Property -> Blocked immediately.
3. This applies regardless of who marked Ready.
4. Audit event required with reporter role.

---

## 7. Issue Resolved

Trigger:
Maintenance marks Resolved.

If no other Critical:
Property may move from Blocked → AtRisk or Ready.

Audit required.

---

## 8. Escalation Engine

Timers:
Ack SLA
Action SLA

If no Ack within SLA:
Escalate to Admin.

If no Action within SLA:
Escalate again.

All escalations logged.

---

## 9. Relocation Logic

Trigger:
Property Blocked close to check-in.

System:
Suggest alternative properties
Same bedroom count preferred.

Admin or Ops:
Create RelocationTask
Manually override booking.

Audit required.

---

## 10. Archive Flow

Admin archives property.

Effects:
Property → Archived
No new bookings allowed
Historical data retained.

Unarchive:
Property → Available
Audit required.

---

## System Invariants

1. No state transition without audit.
2. No silent override.
3. Critical always overrides Ready.
4. Logs never deleted.
5. Company isolation absolute.