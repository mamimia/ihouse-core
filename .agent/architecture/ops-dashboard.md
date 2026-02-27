# Operational Manager Dashboard UI Spec

## Purpose
Ops Manager runs the day.
Fast triage. Fast assignment. Fast recovery.

---

## Top Row: Flight Cards (4)

### Card 1: Active Tasks
Primary:
Tasks due within next 4 hours

Secondary:
Overdue count

CTA:
Open Task Board

EN:
Title: Active Tasks
CTA: View tasks

TH:
Title: งานที่กำลังดำเนินอยู่
CTA: ดูงาน

---

### Card 2: Critical Alerts
Primary:
Critical unacknowledged

Secondary:
Critical in progress

CTA:
Open Critical Queue

EN:
Title: Critical Alerts
CTA: View critical

TH:
Title: แจ้งเตือนฉุกเฉิน
CTA: ดูเหตุฉุกเฉิน

Rule:
If unacknowledged critical exists -> red badge

---

### Card 3: Check-ins Today
Same definition as Admin.

EN:
Title: Check-ins Today
CTA: View check-ins

TH:
Title: เช็กอินวันนี้
CTA: ดูรายการเช็กอิน

---

### Card 4: Team Status
Primary:
Number of staff currently on task

Secondary:
No-response staff count

CTA:
Open Team Status

EN:
Title: Team Status
CTA: View team

TH:
Title: สถานะทีม
CTA: ดูทีม

---

## Row 2: Main Work Surface

### Panel A: Task Board (Kanban)
Columns:
To Do
Acknowledged
In Progress
Done

Each task card shows:
Property code
Task type
Deadline time
Owner role
Badges:
AtRisk, Blocked, Critical

Task actions:
Acknowledge
Start
Reassign
Take over
Navigate

EN:
Title: Task Board

TH:
Title: กระดานงาน

Rules:
1. Acknowledge moves To Do -> Acknowledged
2. Start moves Acknowledged -> In Progress
3. Completion requires required fields per task type

---

### Panel B: Critical Queue
List only Critical issues and Blocked properties

Row shows:
Property code + name
Category
Time since created
Buttons:
Acknowledge
Call
Navigate
Create RelocationTask

EN:
Title: Critical Queue
Buttons: Call | Navigate

TH:
Title: คิวเหตุฉุกเฉิน
Buttons: โทร | นำทาง

Call options:
Call Admin
Call Maintenance
Call Cleaner
Call Check-in Staff

---

## Row 3: Relocation Suggestions
Shows:
If property Blocked close to check-in:
Suggested alternative properties (same bedrooms first)

Each suggestion shows:
Property code
Bedrooms
Distance estimate optional
Buttons:
Open Override Page
Assign RelocationTask

EN:
Title: Relocation
TH:
Title: ย้ายที่พัก

---

## Row 4: Team Status List
Shows:
Cleaner, Check-in Staff, Maintenance

Each row:
Name / nickname
Role
Current task
Last active time
Buttons:
Message via Line
Message via Telegram
Message via WhatsApp
Call
Assign task

EN:
Title: Team Status
TH:
Title: สถานะทีม

Rule:
Line first, Telegram second, WhatsApp third.

---

## Global UX Rules
1. No tables as primary surface for Ops.
2. Ops must be able to navigate to property from every task and issue.
3. Critical actions must be one tap: Call, Navigate, Take over.
4. All actions create audit events.