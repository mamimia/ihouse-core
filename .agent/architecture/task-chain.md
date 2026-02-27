# Task Chain Engine

## Booking Trigger Types

1. Booking Created
2. Booking Modified
3. Booking Cancelled
4. Check-in Completed
5. Check-out Completed

Each trigger may generate one or more tasks.

---

## Cleaning Flow

After Check-out Completed:

1. Create CleaningTask
2. Assign to Cleaner
3. Set Property → Cleaning
4. Write audit entry

When CleaningTask is completed:

Cleaner must:
1. Upload required photos
2. Complete checklist
3. Confirm completion

System validates:
If all required fields present:
   Property → Ready
Else:
   Reject completion

Audit entry required.

---

## Issue Reported

Issue severities:

1. Normal
2. Critical

Behavior:

Normal:
1. Create IssueTask
2. Assign to Maintenance or OperationalManager
3. Property may remain Ready or move to AtRisk depending on rule
4. Write audit entry

Critical:
1. Immediately set Property → Blocked
2. Create IssueTask
3. Notify OperationalManager
4. Notify Admin immediately
5. Trigger relocation evaluation workflow
6. Write audit entry

No other severity levels allowed.

---

## Conflict Task

When booking overlap detected:

1. Create ConflictTask
2. Assign to OperationalManager
3. Deadline = SLA window
4. Property → AtRisk
5. Booking → PendingResolution
6. Write audit entry

If not acknowledged within SLA:
   Escalate to Admin

---

## Task Status

Task states:

1. Created
2. Assigned
3. Acknowledged
4. InProgress
5. Completed
6. Escalated
7. Cancelled

Every state transition must:
1. Write audit entry
2. Store triggering role
3. Store timestamp

---

## Invariant

Every task must include:

1. task_uuid
2. company_uuid
3. property_uuid
4. related booking_uuid optional
5. owner_role
6. deadline
7. status
8. created_at

No task may:
1. Be deleted
2. Change state without audit
3. Bypass escalation logic