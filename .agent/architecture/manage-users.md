# Manage Users UI Spec

## Purpose
Control who has access.
Control what they can do.
Full audit visibility.

---

## Main View

Table columns:
Name
Email
Role
Status (Active, Pending, Inactive)
Last active
Permissions summary

Search:
Search by name or email

Filters:
Role
Status

EN:
Title: Manage Users
TH:
Title: จัดการผู้ใช้งาน

---

## Actions

Primary:
Invite User
Generate One Time Join Code
Rotate Static Join Code

EN:
Invite User
Generate Code
Rotate Code

TH:
เชิญผู้ใช้
สร้างรหัส
เปลี่ยนรหัส

---

## Invite User Modal

Fields:
Email
Role (Admin, OperationalManager, Cleaner, CheckInStaff, Maintenance)
Phone optional
Nickname optional
Emergency contact optional

Button:
Send Invite

Rule:
Invite link expires 72h.

---

## Access Requests Panel

Separate tab:
Pending Requests

Columns:
Requested name
Email
Requested role optional
Requested at

Buttons:
Approve
Reject

On Approve:
Select role
Optional permissions:
can_approve_access_requests
can_booking_override

All actions logged.

---

## User Detail Page

Sections:

### Profile
Name
Nickname
Email
Phone
Emergency contact

### Role
Role dropdown
Permission flags:
can_approve_access_requests
can_booking_override

### Activity
Last login
Active sessions
Recent actions

### Security
Reset password
Deactivate account

EN:
Deactivate
TH:
ปิดการใช้งาน

Rule:
Deactivated users cannot log in.
Audit event required.

---

## Join Code Section

Shows:
Static join code masked
Last rotated date

Actions:
Reveal (Admin only)
Rotate

One time codes:
List:
Code
Created at
Expires at
Used status

Action:
Generate new one time code

---

## Audit Requirements

Every action writes audit:
Invite created
Invite expired
User activated
User deactivated
Permission changed
Join code rotated
Access request approved or rejected