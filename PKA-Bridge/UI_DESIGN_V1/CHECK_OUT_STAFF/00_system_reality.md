# Check-Out Staff — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase
**Date:** 2026-04-03

---

## What Already Exists

### Screens (Frontend: `/ops/checkout/page.tsx`, ~24K lines)
1. **LIST** — CHECKOUT_VERIFY tasks grouped by overdue/today/upcoming, with summary strip
2. **Step 1: Property Inspection** — Before/after photo comparison (3 tabs: Reference, Check-in, Checkout), inspection notes, damage toggle
3. **Step 2: Closing Meter** — OCR capture for closing electricity reading, live delta preview (closing - opening × rate)
4. **Step 3: Report Issues** — Category dropdown (7 options), severity select (LOW/MED/HIGH/CRITICAL), description, creates problem report
5. **Step 4: Deposit Resolution** — Full return or add damage deduction, auto-electricity calculation
6. **Step 5: Checkout Summary** — Final review with settlement breakdown, early checkout context if applicable
7. **Success Screen** — "Check-out completed" confirmation

### Key Architectural Decision (Phase 883)
List sources from CHECKOUT_VERIFY **tasks**, NOT booking status. Task-based reliability.

### Fields Captured
- Room condition photos (6 room types: Living, Bedroom, Bathroom, Kitchen, Balcony, Other)
- Inspection notes (free text) + "All Good" / "Issues Found" toggle
- Closing meter reading (OCR or manual)
- Issue reports: category (7 types), severity (4 levels), description
- Deposit action: Full Return or Damage Deduction (amount + reason)

### Settlement Flow During Checkout
1. `POST /settlement/start` → creates draft
2. `POST /settlement/deductions` → add damage deduction (if any)
3. `POST /settlement/calculate` → auto-creates electricity deduction from meter delta × rate
4. `POST /settlement/finalize` → locks settlement, updates cash_deposits status

### Early Checkout (Phase 1000)
- Amber banner: "EARLY DEPARTURE — Exception Flow"
- Shows effective date, original date, reason
- Requires `early_checkout_approved=true` (by admin/manager) for non-admin workers
- Same workflow, same steps — different date context

### Task Statuses
PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED (or CANCELED / MANAGER_EXECUTING)

### Navigation (BottomNav)
- 🏠 Home → `/worker`
- 🚪 Check-out → `/ops/checkout`
- ✓ Tasks → `/tasks`

### Non-Blocking Failures
All photo uploads, meter reading, issue submission, and settlement are best-effort. Checkout completes even if any of these fail.

---

## What Is Missing

1. **No "guest still present" formal blocking** — worker proceeds regardless
2. **No property walkthrough checklist** (unlike cleaning) — free-form inspection only
3. **No key/access code return capture** — no formal handover step
4. **No guest departure confirmation step** — worker starts checkout, no "Guest has left?" gate
5. **No post-checkout cleaning trigger visibility** — worker doesn't see that a CLEANING task was auto-created

---

## What Is Unclear

1. Whether "Issues Found" toggle blocks deposit resolution or just flags
2. Whether local photo storage fallback actually gets synced later
3. Whether settlement finalization can be reversed after completion
