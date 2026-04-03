# OPS Manager — Navigation & Link Logic (V1)

---

## Shell Behavior

### Mobile (< 768px)
- **OMBottomNav**: 4 primary tabs + "More" overflow sheet
- Primary: Hub | Alerts | Stream | Team
- More sheet: Bookings | Tasks | Calendar | Profile | End Session
- Active tab: white icon + label + top pip
- Badge dot on Alerts when unread critical items exist

### Tablet (768–1023px)
- **OMSidebar collapsed**: 64px icon rail
- Icons only, tooltip on hover
- Same item order as sidebar

### Desktop (≥ 1024px)
- **OMSidebar expanded**: 220px
- Sections: COCKPIT (Hub, Alerts, Stream, Team) | OPERATIONS (Bookings, Tasks, Calendar)
- Mode footer: Preview/Act-As badge + End Session button
- Profile accessed via avatar in sidebar header

---

## Navigation Flow Diagram

```
                    ┌──────────────────┐
                    │   S01 HUB        │
                    │  (Landing Page)  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │S02 Brief │  │ S03/S06  │  │ S08      │
        │ Cockpit  │  │ Alert    │  │ Stream   │
        └──────────┘  │ Detail   │  │ Overview │
                      └────┬─────┘  └────┬─────┘
                           │              │
                    ┌──────┼──────┐  ┌────┼────────────┐
                    │      │      │  │    │    │    │   │
                    ▼      ▼      ▼  ▼    ▼    ▼    ▼   ▼
                  S04    S07   back S09  S11  S14  S16 S10
                  Pick   Esc        C/O  Cln  Mnt  C/I Item
                  Worker Owner      │    │    │        Detail
                    │               ▼    ▼    ▼
                    ▼              S10  S12  S15
                  S05              Item Cln  Mnt
                  Confirmed        Det  Det  Det
                                        │
                                        ▼
                                       S13
                                       Assign
                                       Support

        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │S17 Alert │  │S18 Team  │  │S22 Book  │
        │ List     │  │ Staffing │  │ ings     │
        └────┬─────┘  └────┬─────┘  └────┬─────┘
             │              │              │
             ▼              ▼              ▼
          S03/S06       S19/S21        S23/S24/S25
          Alert Det     Worker Det     Booking Det
                           │
                           ▼
                          S20
                          Redistribute

        ┌──────────┐  ┌──────────┐
        │S26 Cal   │  │S27 Prof  │
        │ endar    │  │ ile      │
        └──────────┘  └──────────┘
```

---

## Link Table

| From | Action | To | Mechanism |
|------|--------|----|-----------|
| S01 Hub | Tap briefing card | S02 Briefing Cockpit | Push (or expand) |
| S01 Hub | Tap alert card | S03/S06 Alert Detail | Push |
| S01 Hub | Tap stream card | S08 Stream (filtered) | Push + filter param |
| S01 Hub | Tap activity feed item | Inline task expansion | Drawer |
| S01 Hub | Tap avatar | S27 Profile | Push |
| S02 Briefing | Back | S01 Hub | Pop |
| S03 Alert Detail | "Reassign" | S04 Pick Worker | Push or drawer |
| S03 Alert Detail | "Escalate" | S07 Escalate | Modal |
| S03 Alert Detail | Back | S01 or S17 | Pop |
| S04 Pick Worker | Tap worker | S05 Confirmed | Replace |
| S04 Pick Worker | Back | S03 Alert Detail | Pop |
| S05 Confirmed | "Return to Hub" | S01 Hub | Replace to root |
| S06 Alert (Amber) | Same as S03 | Same links | — |
| S07 Escalate | Send | Return to alert + status | Dismiss modal |
| S07 Escalate | Cancel | Return to alert | Dismiss modal |
| S08 Stream | Tap task row | S10 Item Detail | Inline or push |
| S08 Stream | Tap lane tab | S09/S11/S14/S16 | Filter |
| S09 CO Runway | Tap card | S10 Detail | Push |
| S10 Item Detail | "Reassign" | Worker picker (S04 variant) | Drawer |
| S10 Item Detail | "Takeover" | Execution drawer | Drawer (embedded wizard) |
| S10 Item Detail | Back | S08/S09 | Pop |
| S11 Cleaner Runway | Tap card | S12 Cleaner Detail | Push |
| S12 Cleaner Detail | "Assign Support" | S13 | Drawer |
| S14 Maint Runway | Tap card | S15 Maint Detail | Push |
| S17 Alerts List | Tap alert | S03/S06 | Push |
| S18 Team | Tap worker | S19/S21 Worker Detail | Push or inline |
| S19 Worker (Overloaded) | "Redistribute" | S20 | Drawer |
| S22 Bookings | Tap booking | S23/S24/S25 | Expand or push |
| S22 Bookings | "Add Note" | Note modal | Modal |
| S22 Bookings | "Approve Early C/O" | Early checkout modal | Modal |
| S26 Calendar | Tap stay | S22 Bookings (filtered) | Push |
| S26 Calendar | Tap task | S18 Tasks | Push |
| Bottom Nav | Any primary tab | S01/S17/S08/S18 | Tab switch (no push) |
| Bottom Nav | "More" | Sheet | Sheet overlay |
| Sidebar | Any item | Target screen | Router push |

---

## Deep-Link Patterns

The manager needs to receive external notifications (LINE, push, email) that link directly to specific screens:

| Notification Type | Deep Link Target |
|-------------------|------------------|
| Task overdue | `/manager/alerts` (filtered to task) |
| Worker no-show | `/manager/team/{worker_id}` |
| Early checkout request | `/manager/bookings/{booking_id}` |
| SLA breach imminent | `/manager/stream?lane={lane}` |
| Guest message received | `/manager/bookings/{booking_id}` (with comms tab) |

---

## Drawer vs. Push vs. Modal Decision Rules

| Pattern | When to Use | Example |
|---------|-------------|---------|
| **Push** (full page nav) | Moving to a new conceptual surface | Hub → Alert Detail |
| **Inline expansion** | Viewing detail of a list item without losing context | Task row → task card expansion |
| **Drawer** (slide panel) | Parallel task that returns to current context | Reassign worker, Task execution |
| **Modal** (centered overlay) | Confirming destructive action or quick input | Escalate form, Add note |
| **Sheet** (bottom) | Mobile overflow menu | "More" nav items |

On desktop, drawers slide from right (40–50% width).
On mobile, drawers go full-screen.
Modals are centered on both.
