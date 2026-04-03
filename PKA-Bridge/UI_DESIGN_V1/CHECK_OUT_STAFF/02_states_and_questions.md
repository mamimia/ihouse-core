# Check-Out Staff — States, Profile & Open Questions (V1)

---

## States Per Screen

### S01 List
| State | Visual |
|-------|--------|
| Loading | Centered spinner |
| Empty | "No pending checkouts" (🏠 icon) |
| Overdue | Red section header, red accent cards, "+XX min" |
| Early checkout | Amber "⚡ EARLY" badge on card |
| Timing locked | Card shows "Checkout: Jan 15" date label, no action button |

### Wizard Steps
| State | Visual |
|-------|--------|
| Inspection OK | Green toggle, issues step skipped |
| Inspection Issues | Red toggle, issues step shown |
| No reference photos | "No reference photos configured" message |
| No check-in photos | "No check-in walkthrough photos found" |
| OCR processing | Spinner (6s timeout) |
| No deposit | "No deposit on file — skip to completion" |
| Settlement error | "⚠️ Settlement calculation unavailable" (non-blocking) |
| Photo upload fail | "Photo saved locally (upload queued)" |
| Early checkout | Amber banner with context on inspection step |

### S07 Success
- Confirmation message only. Simpler than check-in success (no QR, no SMS/email).

---

## Profile Structure
Same shared worker profile as all field roles:
- Identity (name, email, role: "Check-out Staff", status)
- Properties (chip list)
- Notification Preferences (LINE, phone)
- Session info

---

## Open Questions

### Q1: Guest Departure Confirmation
Currently no "Has the guest left?" step. Worker starts inspection regardless. Should Step 0 be "Confirm guest has departed"?

### Q2: Key/Access Code Return
No capture for key return or lockbox confirmation. Should there be a "Keys returned?" toggle on inspection step?

### Q3: Issue → Deduction Linkage
When issues are reported (Step 3) and worker reaches deposit resolution (Step 4), should reported issues auto-suggest a deduction amount?

### Q4: Settlement Finalization Reversibility
Once "Complete Checkout" finalizes settlement, can it be undone? Currently terminal. If the worker makes an error, admin intervention is required.

### Q5: Post-Checkout Cleaning Visibility
Worker completes checkout → system auto-creates CLEANING task. Should the success screen show "Cleaning task created for this property" as operational visibility?
