# Roles & Permissions

## Core Principle
State mutation is permission-bound.
Only specific roles may trigger specific transitions.

---

## Roles

### Admin
- Full visibility across company
- Can override booking
- Can force state change
- Can reassign tasks
- Can archive property
- Escalation level 2+
- Can approve access requests
- Can generate invite links and join codes
- Can grant can_booking_override permission
- Can rotate static join code

### Operational Manager
- Can acknowledge escalation
- Can reassign tasks
- Can mark issue severity
- Can trigger relocation suggestion
- Cannot force Blocked without reason
- Booking override: Only if Admin granted explicit permission flag
- Can view access requests
- Can approve access requests only if granted can_approve_access_requests
- Can request booking override
- Can booking override only if granted can_booking_overridev

### Check-in / Check-out Staff
- Can confirm check-in
- Can confirm checkout
- Can report issues
- Cannot change property state directly

### Cleaner
- Can start cleaning task
- Can complete cleaning task
- Must upload photos
- Cannot mark property Ready directly

### Maintenance
- Can resolve issue tasks
- Cannot change booking data
- Cannot override state

---

## Escalation Authority

Level 1 → Operational Manager  
Level 2 → Admin  
Level 3 → Admin Dashboard Red State  

---

## Invariant

No role may:
- Modify booking dates directly (except Admin)
- Change state without audit entry
- Bypass task chain