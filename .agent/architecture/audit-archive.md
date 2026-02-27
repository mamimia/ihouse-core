# Audit & Archive System

## Core Principle
Nothing disappears.
Everything is traceable.

---

## Audit Log Requirements

Every event must log:

- Timestamp
- Entity (Property / Booking / Task)
- Action
- Previous State
- New State
- Triggering Role
- Notes (optional)

Logs are immutable.
No deletion allowed.
Redaction allowed for sensitive media (passport photos), but event record remains.

---

## Task Completion Logging

When task is:
- Created
- Reassigned
- Acknowledged
- Completed
- Escalated

→ Write audit entry.

---

## Booking Change Logging

If booking:
- Created
- Modified
- Cancelled
- Date changed externally

→ Write delta log.

---

## Property Archive

When property archived:
- Status → Inactive
- Remains queryable
- Historical logs preserved
- Cannot accept new bookings

Admin may:
- Unarchive property
- Restore operational state

---

## Data Retention

Passport images:
Default 90 days.
Configurable by Admin.

Archived properties:
Never auto-delete.

---

## Invariant

System must:
- Prevent silent data mutation
- Prevent hard deletion of records
- Preserve historical truth