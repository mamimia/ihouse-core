# Property Detail UI Spec

## Purpose
Single source of truth for a property.
All operational actions start here.

---

## Header

Shows:
Property code (immutable display ID)
Property name
Status badge:
Available, Occupied, Cleaning, Ready, AtRisk, Blocked, Archived

Primary actions:
Navigate
Open in Maps

EN:
Navigate
TH:
นำทาง

---

## Tabs

1. Overview
2. Reference Photos
3. House Info
4. Tasks
5. Issues
6. Audit

---

## Tab 1: Overview

Cards:
1. Next booking
2. Today timeline
3. Current assignees (Cleaner, Check-in staff, Maintenance)
4. Deposit setting

Actions:
Assign staff
Take over task
Archive property
Unarchive property

EN:
Archive
Unarchive

TH:
เก็บเข้าคลัง
นำกลับมาใช้งาน

Rule:
Archived properties cannot accept new bookings.

---

## Tab 2: Reference Photos

Shows:
Room list based on bedrooms_count
Required areas:
Living
Kitchen optional
Bathrooms
Pool optional
Exterior

Actions:
Upload
Replace
Reorder

Rule:
Reference photo set required before property becomes Active.

EN:
Reference Photos
TH:
ภาพอ้างอิง

---

## Tab 3: House Info

Fields:
WiFi name
WiFi password
House rules text
Emergency contacts
Guest message templates:
Line (EN + TH)
Telegram (EN + TH)
WhatsApp (EN + TH)

Actions:
Copy template
Send template (Line first)

EN:
Copy
Send via Line
TH:
คัดลอก
ส่งผ่านไลน์

---

## Tab 4: Tasks

Shows:
Active tasks
Completed tasks (log)

Filter:
Active | Completed

Rule:
Completed tasks never disappear.

---

## Tab 5: Issues

Shows:
Open issues
Resolved issues

Each issue:
Severity
Category
Created time
Owner

Actions:
Assign to maintenance
Escalate
Create relocation task (if Critical)

---

## Tab 6: Audit

Shows last 100 audit entries for this property

Fields:
Time
Action
Role

EN:
Audit
TH:
บันทึก

---

## Location Requirements

Property must include:
location_lat
location_lng
location_label

If missing:
Show Setup Required banner
Block activation until filled.

---

## Mobile Rule
On mobile:
Tabs become segmented controls.
Reference photos scroll vertically.
No tables.
