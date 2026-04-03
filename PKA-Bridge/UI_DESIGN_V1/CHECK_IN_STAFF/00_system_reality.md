# Check-In Staff — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase
**Date:** 2026-04-03

---

## What Already Exists

### Screens (Frontend: `/ops/checkin/page.tsx`)
1. **LIST** — Arrivals for today + next 7 days, with summary strip (Today/Upcoming/Next countdown), task cards, completed section
2. **WIZARD** — 7-step conditional flow (see below)
3. **SUCCESS** — QR code handoff + portal link delivery (SMS/email)

### Wizard Steps (Dynamic Order)
| Step | Name | Always? | Condition |
|------|------|---------|-----------|
| 1 | Arrival Confirmation | Yes | — |
| 2 | Property Walk-Through Photos | Yes | — (skippable if no ref photos) |
| 3 | Electricity Meter (OCR) | No | `electricity_enabled` on property |
| 4 | Guest Contact Info | Yes | — |
| 5 | Deposit Collection | No | `deposit_enabled` on property |
| 6 | Guest Identity (Passport/ID OCR) | Yes | — |
| 7 | Complete Check-in (Summary) | Yes | — |

Step count: 5–7 depending on property config.

### Fields Captured
- Walk-through photos (matched to reference photos per room)
- Opening meter reading (OCR or manual, decimal kWh)
- Guest phone (required/recommended), guest email (optional)
- Deposit method: Cash / Transfer / Card Hold + optional note
- Identity: doc type (Passport/National ID/Driving License), full_name, doc_number, DOB, expiry, nationality
- All OCR fields have confidence scoring (High ≥92%, Medium 85-92%, Low <85%)

### Task Statuses
PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED (or CANCELED / MANAGER_EXECUTING)

### Timing Gates
- `ack_is_open` flag (server-computed): if false, acknowledge button shows "Opens in Xh Ym"
- `ack_allowed_at` ISO timestamp defines when window opens

### Navigation (BottomNav)
- 🏠 Home → `/worker`
- 📋 Check-in → `/ops/checkin`
- ✓ Tasks → `/tasks`

### Terminology
- "Arrivals" (page title), "Today + next 7 days" (subtitle)
- "Guest Arrived ✓" (step 1 CTA)
- "Settlement Policy" banner (deposit + electricity rates)
- Payment options: "💵 Cash received", "🏦 Transfer received", "💳 Card hold"
- Doc types: "📘 Passport", "🪪 National ID", "🚗 Driving License"
- "Guest Portal QR" (success screen title)
- "Done — Return to Arrivals" (final CTA)

### Worker Limitations
- Cannot modify booking data (read-only)
- Cannot skip conditional steps if enabled (400 error)
- Cannot bulk check-in (one at a time)
- Cannot edit saved identity after submission
- Cannot jump steps (sequential only, back allowed)
- Cannot acknowledge before timing gate opens

---

## What Is Missing

1. **No offline mode** — no service worker, no persistent upload queue
2. **No "cannot complete" formal flow** — worker can only go back or call for help
3. **No escalation button in wizard** — must exit wizard entirely to escalate
4. **No explicit "property not ready" blocking** — warning shown but worker can proceed
5. **No guest signature capture in wizard** — exists in separate guest form flow, not in worker wizard
6. **No multi-guest handling** — single identity capture, no companion passport flow
7. **No explicit "late arrival" workflow** — worker sees the task regardless of time

---

## What Is Unclear

1. Whether walk-through photo upload failures are silently swallowed or surfaced to worker
2. Whether the timing gate (`ack_is_open`) can be overridden by the worker in urgent cases
3. How the "Navigate to Property" button handles properties without GPS coordinates
4. Whether the SMS/email delivery on success screen actually works (notification dispatch not fully traced)
