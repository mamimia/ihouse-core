# Check-In Staff — Navigation & Link Logic (V1)

---

## Shell & Navigation

### MobileStaffShell
- Full-screen mobile layout
- Forced dark theme (data-theme="dark")
- Safe area handling for notched devices
- No sidebar — mobile only role

### Bottom Nav (4 tabs) [BUILT — confirmed in screenshots]
| Tab | Label | Icon | URL |
|-----|-------|------|-----|
| 1 | Home | 🏠 | `/worker` |
| 2 | Check-in | 📋 | `/ops/checkin` |
| 3 | Tasks | ✓ | `/tasks` |
| 4 | Settings | ⚙ | `/worker/settings` |

Active tab: white icon + label. Inactive: muted.

---

## Flow Diagram

```
S01 List (Arrivals)
  │
  ├── Tap card → S02 Arrival Confirmation
  │     │
  │     ├── "Guest Arrived ✓" → S03 Walk-Through Photos
  │     │     │
  │     │     ├── "Continue →" → S04 Meter (if electricity_enabled)
  │     │     │                   │  OR → S05 Contact Info
  │     │     │                   │
  │     │     │                   ├── "Complete"/"Skip" → S05 Contact Info
  │     │     │                   │
  │     │     │     S05 Contact Info
  │     │     │       │
  │     │     │       ├── "Continue →" → S06 Deposit (if deposit_enabled)
  │     │     │       │                   │  OR → S07 Identity
  │     │     │       │                   │
  │     │     │       │                   ├── "Confirm & Record →" → S07 Identity
  │     │     │       │                   │
  │     │     │       │     S07 Identity (OCR)
  │     │     │       │       │
  │     │     │       │       ├── "Complete"/"Skip" → S08 Summary
  │     │     │       │       │
  │     │     │       │       S08 Summary
  │     │     │       │         │
  │     │     │       │         ├── "✅ Complete Check-in" → S09 Success
  │     │     │       │         │
  │     │     │       │         S09 Success
  │     │     │       │           │
  │     │     │       │           └── "Done — Return to Arrivals" → S01
  │     │     │       │
  │     │     │ (← Back at every step returns to previous step)
  │     │     │
  │     └── ← Back → S01 List
  │
  ├── Tap "Acknowledge" button → acknowledgement API call → card updates
  │
  └── Tap "📍 Navigate" → external maps app (Waze mobile / Google Maps desktop)
```

---

## Navigation Rules

1. **Wizard is linear.** Forward-only (no step jumping). Back returns to previous step.
2. **Back from Step 1 returns to list.** No confirmation dialog needed.
3. **Wizard takes over the screen.** Bottom nav remains visible but the work area is fully wizard.
4. **Success screen is a terminal state.** Only action: "Done — Return to Arrivals".
5. **External navigation** (maps) opens in new window/app — does not leave the wizard.
6. **SMS/Email send** on success screen is fire-and-forget — does not navigate.

---

## Link Table

| From | Action | To | Mechanism |
|------|--------|----|-----------|
| S01 List | Tap task card | S02 Arrival | Wizard entry |
| S01 List | Tap "Acknowledge" | S01 (updated) | API call, card refresh |
| S01 List | Tap "Navigate" | External maps | New window/app |
| S02 Arrival | "Guest Arrived ✓" | S03 Walk-Through | Next step |
| S02 Arrival | ← Back | S01 List | Exit wizard |
| S03 Walk-Through | "Continue →" | S04 or S05 | Conditional next |
| S04 Meter | "Complete"/"Skip" | S05 Contact | Next step |
| S05 Contact | "Continue →" | S06 or S07 | Conditional next |
| S06 Deposit | "Confirm & Record →" | S07 Identity | Next step |
| S07 Identity | "Complete"/"Skip" | S08 Summary | Next step |
| S08 Summary | "✅ Complete" | S09 Success | API call → success |
| S09 Success | "Send SMS/Email" | S09 (feedback) | In-place update |
| S09 Success | "Done — Return" | S01 List | Reset wizard, reload |
| Any step | ← Back | Previous step | Step decrement |
| Bottom Nav | Home | `/worker` | Tab switch |
| Bottom Nav | Tasks | `/tasks` | Tab switch |

---

## Step Progress Bar

The wizard shows a progress bar and "Step N of M" indicator:
- Total steps = 5 (base) + 1 (if electricity) + 1 (if deposit)
- Progress fills proportionally: Step 1 = 1/M, Step 2 = 2/M, etc.
- Bar color: deep-moss (#334036) on dark background
