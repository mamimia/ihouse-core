# Mobile UI – Cleaner

## Purpose
Cleaner sees only what matters.
No dashboards.
No analytics.
Only tasks.

---

## Home Screen

Top:
Greeting + first name
Today tasks count
Next deadline time

EN:
Title: Today's Tasks
TH:
Title: งานวันนี้

Main:
List of assigned tasks
One card per task

Card shows:
Property code
Task type: Cleaning
Check-out time
Deadline time
State badge:
To Do
Acknowledged
In Progress

Buttons:
Acknowledge
Start
Navigate

---

## Task Detail – Cleaning

Top section:
Property code + name
Check-out time
Deadline
Navigate button

EN:
Button: Navigate
TH:
Button: นำทาง

---

## Cleaning Checklist

Checklist is dynamic per property.

Each property must define:
- Rooms
- Required photo points
- Custom cleaning rules

Cleaner must:
1. Complete checklist items
2. Upload required photos (per room)
3. Confirm no visible damage OR create Issue

No completion allowed without:
All required checklist items done
All required photos uploaded

---

## Photo Categories

Per room:
Room photo
Bathroom photo if exists
Living area photo
Kitchen photo if exists
Pool photo if exists
Exterior photo

System validates required count before completion.

---

## Issue Report from Cleaner

Button:
Report Issue

Fields:
Category dropdown
Description
Severity:
Normal
Critical
Photo upload required for Critical

EN:
Report Issue
TH:
รายงานปัญหา

Rules:
Critical immediately sets property Blocked and triggers 5 minute SLA.

---

## Completion

Button:
Mark as Ready

Enabled only if:
Checklist complete
Photos complete
No unresolved Critical issues

On completion:
Property state → Ready
Audit event written
Cleaner loses access to task after completion

---

## Global Rules

1. Cleaner cannot see revenue.
2. Cleaner cannot see booking details beyond:
   Check-out time
   Next check-in time
3. Cleaner cannot see passport images.
4. After task completion, media becomes read-only for Admin and Ops only.
