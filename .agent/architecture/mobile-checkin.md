# Mobile UI – Check-in Staff

## Purpose
Smooth guest arrival.
Fast verification.
No confusion.

---

## Home Screen

Top:
Today's Check-ins count
Next arrival time

Secondary:
Today's Check-outs count

EN:
Title: Today's Arrivals
TH:
Title: เช็กอินวันนี้

Main:
List of bookings assigned today

Each card shows:
Property code
Guest name
Check-in time
State badge:
Upcoming
Arrived
Completed

Buttons:
Open
Navigate

---

## Check-in Flow

### Step 1 – Arrival Confirmation

Display:
Property code
Guest name
Booking dates
Guest count
Navigate button

Buttons:
Guest Arrived

EN:
Guest Arrived
TH:
แขกมาถึงแล้ว

---

### Step 2 – Property Status Check

System displays:
Current property state

If state != Ready:
Show warning:
Property not ready

If Critical exists:
Block check-in until Ops decision

---

### Step 3 – Passport Capture

Required fields:
Passport image (camera only)
Passport number
Guest full name (auto fill if available)

Visibility:
Admin only after upload
Not visible to Cleaner

EN:
Capture Passport
TH:
ถ่ายภาพพาสปอร์ต

Rule:
PassportImages retained 90 days by default.

---

### Step 4 – Deposit Handling (If required)

Display:
Deposit required yes/no
Deposit amount

Options:
Cash received
Transfer received
Card hold

Field:
Amount confirmed
Optional note

EN:
Confirm Deposit
TH:
ยืนยันเงินมัดจำ

Rule:
Deposit status stored in booking record.

---

### Step 5 – Send Welcome Info

Display predefined templates:
WiFi
House rules
Emergency contacts
Motorbike rental suggestion
Laundry info

Buttons:
Send via Line
Send via Telegram
Send via WhatsApp

Line always first.

EN:
Send Welcome Info
TH:
ส่งข้อมูลต้อนรับ

---

### Step 6 – Complete Check-in

Button:
Complete Check-in

Effect:
Booking state → InStay
Property state → Occupied
Audit event written

---

## Check-out Flow

### Step 1 – Property Inspection

Display:
Reference photos
Room list

Staff must:
Compare visually
Mark each room OK or Issue

---

### Step 2 – Issue Report (if needed)

Fields:
Category
Severity:
Normal
Critical
Photo required

If Critical:
Property state → Blocked
Trigger 5 minute SLA

---

### Step 3 – Deposit Resolution

If damage:
Record deduction
Upload evidence photo

If no damage:
Mark deposit returned

---

### Step 4 – Complete Check-out

Button:
Complete Check-out

Effect:
Booking state → Completed
Create CleaningTask
Property state → Cleaning
Audit event written

---

## Global Rules

1. Check-in staff cannot edit booking dates.
2. Cannot override booking unless permission can_booking_override = true.
3. Cannot delete passport images.
4. Navigate button always visible.
5. Critical issue blocks check-in until resolved or Admin override.