# Dashboard Flight Mode

## Core Principle
Dashboards show operational truth in 5 seconds.
No decorative metrics in the top row.

---

## Admin Dashboard (Top 4 Cards)

### 1. Check-ins Today
Purpose:
Immediate awareness of arrivals.
Counts:
- Total check-ins today
- Next check-in time
CTA:
Open Today's Check-ins

EN label: Check-ins Today
TH label: เช็กอินวันนี้

---

### 2. Villas At Risk
Purpose:
Prevent late readiness and guest failure.
Counts:
- Properties in AtRisk
- Earliest deadline
CTA:
Open Risk Queue

EN label: Villas At Risk
TH label: วิลล่าที่มีความเสี่ยง

---

### 3. Occupancy %
Purpose:
Business heartbeat.
Counts:
- Current occupancy %
- Properties occupied now
CTA:
Open Occupancy View

EN label: Occupancy
TH label: อัตราการเข้าพัก

---

### 4. Revenue This Month
Purpose:
Financial pulse.
Counts:
- Month revenue
- Change vs last month optional
CTA:
Open Revenue

EN label: Revenue This Month
TH label: รายได้เดือนนี้

---

## Operational Manager Dashboard (Top 4 Cards)

### 1. Active Tasks Now
Purpose:
Immediate workload visibility.
Counts:
- Tasks due in next 4 hours
- Overdue tasks
CTA:
Open Task Board

EN label: Active Tasks
TH label: งานที่กำลังดำเนินอยู่

---

### 2. Critical Alerts
Purpose:
Fast reaction to true emergencies.
Counts:
- Critical unacknowledged (5 min SLA)
- Critical in progress
CTA:
Open Critical Queue

EN label: Critical Alerts
TH label: แจ้งเตือนฉุกเฉิน

---

### 3. Check-ins Today
Same definition as Admin.

EN label: Check-ins Today
TH label: เช็กอินวันนี้

---

### 4. Team Status
Purpose:
Detect no-shows and coverage gaps.
Counts:
- Cleaner on task / idle
- Check-in staff on task / idle
- Maintenance on task / idle
CTA:
Open Team Map / List

EN label: Team Status
TH label: สถานะทีม

---

## Rendering Rules

1. Top row must always be 4 cards.
2. Each card shows:
   - Primary number
   - One secondary line
   - One CTA button
3. Red state rules:
   - Any unacknowledged Critical → card border red + badge
   - Any AtRisk property within 3 hours of check-in → red badge
4. All labels must exist in EN and TH.