# Admin Dashboard UI Spec

## Purpose
Admin sees operational truth in 5 seconds.
Admin can intervene without micromanaging.

---

## Top Row: Flight Cards (4)

### Card 1: Check-ins Today
Primary number:
Count of check-ins today

Secondary line:
Next check-in time + property code

CTA:
Open Today's Check-ins

EN:
Title: Check-ins Today
CTA: View check-ins

TH:
Title: เช็กอินวันนี้
CTA: ดูรายการเช็กอิน

---

### Card 2: Villas At Risk
Primary number:
Count of properties in AtRisk + Blocked (two values)

Secondary line:
Earliest deadline among those properties

CTA:
Open Risk Queue

EN:
Title: Villas At Risk
CTA: View risks

TH:
Title: วิลล่าที่มีความเสี่ยง
CTA: ดูความเสี่ยง

---

### Card 3: Occupancy
Primary number:
Current occupancy percentage

Secondary line:
Occupied now / total active properties

CTA:
Open Occupancy View

EN:
Title: Occupancy
CTA: View occupancy

TH:
Title: อัตราการเข้าพัก
CTA: ดูอัตราการเข้าพัก

---

### Card 4: Revenue This Month
Primary number:
Revenue amount this month

Secondary line:
Optional: change vs last month

CTA:
Open Revenue

EN:
Title: Revenue This Month
CTA: View revenue

TH:
Title: รายได้เดือนนี้
CTA: ดูรายได้

---

## Row 2: Admin Control Panels

### Panel A: Today Timeline
Shows:
Today events ordered by time:
- Check-outs
- Cleaning start deadlines
- Check-ins
- Critical issues

Interactions:
Filter:
All | Check-ins | Check-outs | Cleaning | Issues

CTA:
Open full calendar view

EN:
Title: Today Timeline
Filter label: Filter
CTA: Open calendar

TH:
Title: ไทม์ไลน์วันนี้
Filter label: ตัวกรอง
CTA: เปิดปฏิทิน

---

### Panel B: Risk Queue
Shows list:
AtRisk and Blocked properties
Each row shows:
Property code + name
Reason badge
Deadline
Owner role
Buttons:
Assign
Take over
Navigate

EN:
Title: Risk Queue
Buttons: Assign | Take over | Navigate

TH:
Title: คิวความเสี่ยง
Buttons: มอบหมาย | รับงานเอง | นำทาง

Rules:
Blocked always pinned above AtRisk.

---

## Row 3: Properties Overview Table

Columns:
Property code
Name
State
Next check-in
Cleaner assigned
Check-in staff assigned
Open issues count

Actions per row:
Open property
Archive
Unarchive

EN:
Title: Properties
Search: Search properties
Filters: State | Bedrooms | Deposit

TH:
Title: รายการทรัพย์สิน
Search: ค้นหาทรัพย์สิน
Filters: สถานะ | ห้องนอน | เงินมัดจำ

---

## Row 4: Recent Audit Events

Shows last 20 events
Fields:
Time
Entity
Action
Triggered by role

EN:
Title: Audit Log
CTA: View all logs

TH:
Title: บันทึกการทำงาน
CTA: ดูบันทึกทั้งหมด

---

## Global UI Elements

### Quick Search
Always visible in header:
Search property by code or name
Search booking by guest name
Search task by ID

EN placeholder:
Search property, booking, task

TH placeholder:
ค้นหาทรัพย์สิน การจอง งาน

---

### Help System
Help icon appears only near:
SLA settings
Escalation policy
Booking override
Archive

Help opens:
Short tooltip line + link to "Explain this page" panel.

---

## Color States
Ready: subtle green indicator
AtRisk: amber border
Blocked: red border
Cleaning: neutral blue indicator
Occupied: neutral

Never blinking.
No neon.

---

## Admin Interventions (Core Buttons)
1. Take over task
2. Reassign task
3. Approve override request
4. Approve access request
5. Generate join code (one time)

All actions must create audit events.