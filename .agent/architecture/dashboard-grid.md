# Dashboard Grid System

## Core Principle
Same information architecture across devices.
Layout adapts, not redesigns.

---

## Containers

Desktop:
Max width: 1200 to 1320
Centered
Side padding: 24

Tablet:
Max width: 960
Centered
Side padding: 20

Mobile:
Full width
Side padding: 16

---

## Admin Dashboard Layout

Row 1:
4 Flight Cards
Desktop: 4 columns
Tablet: 2x2
Mobile: stacked

Row 2:
Left: Task Timeline (Today + Next 24h)
Right: Risk Queue (AtRisk + Blocked)

Row 3:
Properties Overview Table
Filterable

Row 4:
Recent Audit Events (last 20)

---

## Operational Manager Dashboard Layout

Row 1:
4 Flight Cards

Row 2:
Task Board (Kanban)
Columns:
To Do
Acknowledged
In Progress
Done

Row 3:
Critical Queue + Relocation Suggestions

Row 4:
Team Status (List first, map optional later)

---

## Mobile Staff Layout (Cleaner, Check-in, Maintenance)

Top:
Today tasks count + next deadline

Main:
Task list (one task per card)

Task detail:
Checklist
Photos
Issue report
Navigate button

No tables on mobile.

---

## Interaction Rules

1. Filters always pinned above lists.
2. Search always present for Admin tables.
3. Primary CTA always on the right on desktop, bottom sticky on mobile.
4. Never hide critical alerts behind menus.