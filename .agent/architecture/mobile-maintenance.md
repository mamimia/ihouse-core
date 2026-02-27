# Mobile UI – Maintenance (Handyman + Gardening)

## Purpose
Fix issues fast.
Track parts and time.
Keep properties operational.

---

## Home Screen

Top:
Open issues count
Critical count

EN:
Title: Maintenance Queue
TH:
Title: คิวงานซ่อมบำรุง

Main:
List of IssueTasks and MaintenanceTasks

Card shows:
Property code
Category badge
Severity badge (Normal or Critical)
Time created
Deadline
Buttons:
Acknowledge
Start
Navigate

---

## Task Detail

Top:
Property code + name
Navigate button
Issue category
Severity
Reported by role
Photos evidence

EN:
Navigate
TH:
นำทาง

---

## Specialization Tags (Configurable)
Default:
General

Optional:
Plumbing
Electrical
AC
Pool
Gardening

Rule:
Admin can split one Maintenance role into multiple workers by specialization.
Task assignment should prefer matching specialization when available.

---

## Work Log

Maintenance must record:
1. Work started time
2. Work ended time
3. Notes
4. Photos after fix

Optional:
Parts used:
Name
Quantity
Cost

EN:
Add Work Log
TH:
เพิ่มบันทึกงาน

---

## Completion

Button:
Mark Resolved

Rules:
1. If Critical issue resolved:
Property may move from Blocked to AtRisk or Ready depending on readiness rules.
2. Completion requires:
Work log present
After photo present

Audit event required.

---

## Communication Shortcuts
Buttons:
Call Operational Manager
Message via Line
Message via Telegram
Message via WhatsApp

Line first.

---

## Global Rules
1. Maintenance cannot see passport images.
2. Maintenance cannot change booking dates.
3. Maintenance can create Relocation suggestion but cannot execute booking override unless granted.