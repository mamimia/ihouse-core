# Check-In Staff — States, Profile & Open Questions (V1)

---

## States Per Screen

### S01 List
| State | Trigger | Visual |
|-------|---------|--------|
| Loading | Initial mount | Centered spinner |
| Empty | No arrivals in 7 days | "No arrivals in the next 7 days" (calm) |
| Populated | Tasks exist | Summary strip + grouped task list |
| Overdue task | Past check-in time | Red left accent, "+XX min" blinking, card sorts to top |
| Timing gate locked | Worker taps Acknowledge before window | Flash: "Opens in Xh Ym" for 3 seconds, button reverts |
| All done | All today's tasks completed | Only "Completed Today" section visible |

### Wizard (All Steps)
| State | Trigger | Visual |
|-------|---------|--------|
| Step active | Normal flow | Progress bar + step content |
| OCR processing | Camera captured, waiting | Processing spinner (6s timeout) |
| OCR low confidence | Result <85% | Red-bordered fields, "Low — please verify" |
| OCR timeout | No result in 6s | Manual entry form shown |
| Photo uploading | File being sent | "⏳ Uploading…" on photo slot |
| API error | Save failed | Toast: "⚠️ [error message]" (non-blocking) |

### S09 Success
| State | Trigger | Visual |
|-------|---------|--------|
| QR shown | Check-in completed | QR image + portal explanation |
| SMS sent | Worker tapped send | "✅ Portal link sent via SMS" |
| Email sent | Worker tapped send | "✅ Portal link sent via Email" |
| Send failed | Delivery failed | "⚠️ Send failed" toast |

---

## Profile Structure

Profile is accessed via `/worker` (Home tab).

### Sections
1. **Identity**: Display name, email, role ("Check-in Staff"), status (Active/Suspended), user ID
2. **Properties**: List of assigned properties (chip format)
3. **Notification Preferences**: LINE ID, Phone (editable + Save)
4. **Session**: Last login, current device

The profile page is shared across all worker roles — same structure, different role label.

---

## Open Questions

### Q1: Property Not Ready — Should Worker Be Warned More Strongly?
Currently shows a ⚠ badge on Step 1 but doesn't block. Should there be a confirmation dialog: "This property is not marked as ready. Proceed anyway?"

### Q2: Multi-Guest Identity Capture
System captures only one identity document. For group bookings (3+ guests), should there be a "Add companion" flow, or is one identity sufficient?

### Q3: Wizard Exit Confirmation
If worker is on Step 5 and taps Back repeatedly to list, all captured data is lost. Should there be a "Are you sure?" confirmation when exiting mid-wizard?

### Q4: Task Card Countdown Precision [RESOLVED by screenshots]
Screenshots confirm precise format: "XXh XXm XXs" (e.g., "15h 36m 38s"). Ticks every second even at long durations. Label "Upcoming" shown alongside. This is the BUILT behavior.

### Q5: Photo Upload Failure Recovery
Walk-through photos: if upload fails, the photo appears captured locally but may not be on server. Should the UI show a "⚠ Not uploaded" indicator per photo?
