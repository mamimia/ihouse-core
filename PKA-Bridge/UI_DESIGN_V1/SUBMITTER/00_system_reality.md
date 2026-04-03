# Submitter UI — System Reality (Read Before Design)

**Read from:** ihouse-core real codebase + Team_Inbox screenshots (15 screenshots)
**Date:** 2026-04-03

> **Grounding key:** [BUILT] = confirmed in screenshots. [INFERRED] = from codebase. [V1 PROPOSAL] = new design.

> **Note:** "Submitter" is the property onboarding flow — a person submitting their property to be managed by Domaniqo. This is NOT the problem/issue report submitter (that is part of the maintenance/operations system).

---

## What Already Exists [BUILT]

### Architecture
- **Route:** `/get-started` — public, no auth required initially
- **Auth:** Optional at start. Required at Step 6 (account creation/verification) to save the property.
- **Shell:** Minimal — Domaniqo logo only, no sidebar, no nav bar. Clean wizard environment.
- **Theme:** Dark background, centered content, green/copper accents

### Onboarding Wizard (7 steps) [BUILT — confirmed across multiple screenshots]

**Step 1 of 7 — Portfolio Size [BUILT — Screenshot 23.11.35]**
- "Get Started" title, "Step 1 of 7" progress indicator (green line)
- Question: "How many properties do you manage?"
- 3 radio options:
  - 1-5 properties ("Getting started") — selected by default
  - 5-20 properties ("Growing portfolio")
  - 20+ properties ("Established manager")
- [Continue →] button
- "Already a user? Log in" link at bottom

**Step 4 of 7 — Listing URL Import [BUILT — Screenshot 23.12.49]**
- "Get Started" title, "Step 4 of 7" progress indicator
- Instruction: "How it works: Paste the URL of your existing listing. We'll pull publicly available details to speed up your setup."
- AIRBNB LISTING URL field with pasted URL
- Example URL shown
- [← Back] + [Importing property details...] (loading state, green CTA)
- Auto-extraction via Playwright headless browser (Airbnb currently supported)

**Step 6 of 7 — Account Verification [BUILT — Screenshot 23.13.53]**
- "Save Your Property" title, "Step 6 of 7"
- "Create an account to save your property and track its review status."
- Email verification sent indicator
- 8-DIGIT VERIFICATION CODE input (large, centered: "00214559")
- Blue checkmark when verified
- [Verify & Continue →] CTA
- "Use a different email" link
- "Already have an account? Log in" link
- [← Back to property details] link

### What the Wizard Collects (from code)

**Step 1:** Portfolio size (1-5 / 5-20 / 20+)
**Step 2:** [INFERRED] Property type and location
**Step 3:** [INFERRED] Property details (name, capacity, bedrooms, etc.)
**Step 4:** Listing URL for auto-extraction (Airbnb, Booking.com, VRBO)
**Step 5:** [INFERRED] Photos and additional details
**Step 6:** Account creation + email verification
**Step 7:** [INFERRED] Submission confirmation + next steps

### Listing URL Extraction [BUILT]
- `POST /api/listing/fetch` — proxy to backend extraction
- `POST /api/listing/extract` — Playwright headless extraction
- Extracts: property name, description, photos, capacity, type, location
- Confidence scoring per field
- Currently supports Airbnb only

### Property Submission API [BUILT]
- `POST /api/onboard` — creates property draft (status: 'draft')
- Auto-generates clean IDs (DOM-001, KPG-002)
- Handles deduplication, photo uploads, channel mappings
- Submitter contact auto-populated from auth user metadata

### Draft Management [BUILT]
- `PATCH /api/properties/[propertyId]/submit` — draft → pending_review
- `GET /api/properties/mine` — user's drafts
- Auto-expiry: 90 days for abandoned drafts
- Statuses: draft → pending_review → approved → active

### Admin Intake Queue [BUILT]
- Admin reviews submitted properties
- Approve/reject workflow with notes
- Property photos shown on intake cards
- Phase 877: tenant_id migration on approval

---

## What Is Visible in Screenshots

**Screenshot count:** 15 screenshots in SUBMITER UI folder (screenshots span the full wizard flow)

**Key screens confirmed:**
1. Landing page (pre-wizard)
2. Step 1: Portfolio size selection
3. Step 4: Listing URL import with loading state
4. Step 6: Email verification with code input
5. Post-submission welcome page
6. My Properties page with draft/submitted cards

**Visual observations:**
- Dark theme throughout
- Centered, focused wizard — no distractions
- Progress indicator: green line, "Step N of 7"
- Radio buttons with descriptions
- Large verification code input
- Clean loading states ("Importing property details...")

---

## What Is Missing

1. **Steps 2, 3, 5, 7 not visible in screenshots** — wizard middle steps not captured
2. **No mobile screenshots** — wizard appears desktop-focused
3. **No error states visible** — what happens if URL extraction fails? If verification fails?
4. **No VRBO/Booking.com extraction** — only Airbnb currently supported
5. **No progress save** — if user leaves mid-wizard, can they resume?
6. **No property edit after submission** — once submitted for review, can the submitter make changes?

---

## What Is Already Strong

1. **URL extraction** — Auto-populating from existing Airbnb listing is a strong UX. Reduces manual entry significantly.
2. **Clean wizard flow** — 7 steps, focused, no distractions. Professional feel.
3. **Email verification** — 8-digit code, clean input, clear feedback.
4. **Draft lifecycle** — Submit → review → approve with visual status on My Properties page.
5. **Low-friction start** — No login required to begin. Auth only at save point.

---

## Open Questions

### Q1: Wizard Resume
If a user starts the wizard, leaves, and returns — can they resume from where they left off?

### Q2: Multi-Platform Import
Only Airbnb extraction works. When will Booking.com and VRBO be supported?

### Q3: Post-Submission Editing
Can the submitter edit their property after submitting for review? Or is it locked until admin action?

### Q4: Rejection Flow
If admin rejects a property, what does the submitter see? Is there a "fix and resubmit" flow?

### Q5: Staff Application
A 773-line staff application form exists at `/staff/apply`. Should this be part of the Submitter UI design scope, or is it a separate surface?
