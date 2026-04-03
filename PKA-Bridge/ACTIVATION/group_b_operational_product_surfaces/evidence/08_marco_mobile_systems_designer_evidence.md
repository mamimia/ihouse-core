# Evidence File: Marco — Mobile Systems Designer

**Paired memo:** `08_marco_mobile_systems_designer.md`
**Evidence status:** Strong evidence on mobile surfaces and session isolation; offline resilience confirmed as missing

---

## Claim 1: 7-step check-in wizard with conditional steps

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/ops/checkin/page.tsx`: CheckInStep type definition, `getFlow()` function
- Step sequence: list → arrival → walkthrough → meter (if electricity_enabled) → contact → deposit (if deposit_enabled) → passport → complete → success
- ChargeConfig drives conditional inclusion of meter and deposit steps

**What was observed:** The wizard is implemented as a single-page state machine. `getFlow()` dynamically constructs the step array. StepHeader renders "Step X of Y" with visual progress. The step count adapts from 5 (no meter, no deposit) to 7 (both enabled). Each step has a dedicated view rendering within the same page component.

**Confidence:** HIGH

**Uncertainty:** None on structure. The back-navigation capability (whether workers can return to a previous step) was not explicitly confirmed.

---

## Claim 2: MobileStaffShell provides forced dark theme and mobile-native layout

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/MobileStaffShell.tsx`, line 186: `data-theme="dark"` forced
- File: `ihouse-ui/components/AdaptiveShell.tsx`, lines 41-73: MOBILE_STAFF_PREFIXES detection → bypass sidebar → MobileStaffShell
- MobileStaffShell: safe area insets (`env(safe-area-inset-top)`, `env(safe-area-inset-bottom)`), touch target minimum 44px, phone simulation at 480px on desktop

**What was observed:** All worker routes (`/worker`, `/ops/cleaner`, `/ops/checkin`, `/ops/checkout`, `/ops/maintenance`) bypass the standard sidebar and render inside MobileStaffShell. Dark theme is forced at the component level (not a toggle). Touch targets use `var(--touch-target-min) = 44px`. Safe area handling covers both iPhone notch (top) and home indicator (bottom). Desktop renders a 480px phone simulation for dev testing.

**Confidence:** HIGH

**Uncertainty:** Whether touch targets are consistently ≥44px across ALL interactive elements (buttons, links, toggles) or just the primary ones.

---

## Claim 3: staffApi.ts provides session isolation via sessionStorage-first reads

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/staffApi.ts`: `getTabToken()` returns `sessionStorage.getItem(TOKEN_KEY) ?? localStorage.getItem(TOKEN_KEY)`
- `setActAsTabToken(token)` stores ONLY in sessionStorage
- `clearTabToken()` removes ONLY from sessionStorage (admin's localStorage untouched)
- `apiFetch()` uses `getToken()` (which calls `getTabToken()`) and adds `X-Preview-Role` header when preview is active

**What was observed:** Complete isolation chain:
1. Each browser tab has its own sessionStorage (OS-enforced)
2. Act-as token goes to sessionStorage only
3. Admin's normal login token stays in localStorage
4. `getTabToken()` tries sessionStorage first → uses Act-as token if present → falls back to localStorage
5. Closing Act-as tab destroys its sessionStorage → admin's token unaffected

The code comment warns against importing staffApi from admin pages (citing 2026-03-26 staging incident). This is a discipline-based guardrail, not a build-time enforcement.

**Confidence:** HIGH

**Uncertainty:** The mixing guardrail is a code comment only. No ESLint rule or build-time check prevents `import from staffApi` in admin pages.

---

## Claim 4: OCR capture with confidence scoring and manual fallback

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/OcrCaptureFlow.tsx`: OcrCaptureType = 'identity_document_capture' | 'checkin_opening_meter_capture' | 'checkout_closing_meter_capture'
- HTML5 `<input type="file" capture="environment">` for camera
- Base64 JPEG at 85% quality compression
- Document types: PASSPORT, NATIONAL_ID, DRIVING_LICENSE
- Confidence scoring: HIGH (≥0.92, green), MEDIUM (0.85-0.92, yellow), LOW (<0.85, red + "please verify")
- 6-second timeout → manual entry fallback
- Manual entry always available as alternative path

**What was observed:** OCR is used for 3 capture types shared across check-in and checkout wizards. The capture flow: camera → processing (6s timeout) → review (with confidence indicators) → manual override option. Fields vary by document type (passport has 6 fields, national ID has 4, driving license has 4). All fields support both OCR-extracted and manual entry.

**Confidence:** HIGH

**Uncertainty:** None on the implementation. OCR accuracy in real-world conditions (dirty passports, poor lighting in rental units) was not testable through code reading.

---

## Claim 5: Cleaner surface has interactive checklist with photo capture and supply verification

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/ops/cleaner/page.tsx`: Screen types: list → detail → checklist → complete → success
- Checklist: per-item toggle, progress bar (done/total)
- Photo capture: `<input accept="image/*" capture="environment">` → FormData upload → JSON fallback with `pending-upload://` marker
- Supply check: cyclic toggle (unchecked → ok → low → empty → unchecked)
- Issue reporting: category selector + severity + description → POST `/problem-reports` with source="cleaner_flow"
- Completion blockers: 409 response with blockers array (checklist_incomplete, photos_missing, supplies_not_ok)

**What was observed:** The cleaner surface is a complete task-execution interface. Checklist items are toggleable with progress tracking. Photos use rear camera with FormData upload (fallback to JSON if upload fails). Supply checks are simple status toggles. Issue reporting is inline (Phase E-9) — cleaner can report problems without leaving the flow. Completion is gated by three conditions; blockers are shown explicitly.

**Confidence:** HIGH

**Uncertainty:** The fallback chain (FormData → JSON → `pending-upload://` → potential loss) was observed. If both upload attempts fail, the photo data exists only in the browser's temporary memory.

---

## Claim 6: No offline mode exists

**Status:** DIRECTLY PROVEN (absence confirmed)

**Evidence basis:**
- No service worker files found in `ihouse-ui/`
- No IndexedDB or local storage queue for failed uploads
- No offline indicator UI component found
- Photo upload fallback: `pending-upload://` marker URL stored in DB, but actual file data lost if upload fails
- Checkout photos: `local: true` flag marks photos for retry, but queue is in-memory (component state), not persistent
- Error handling: `showNotice('⚠️ Upload failed — please retry')` — user-facing retry message only

**What was observed:** The system has no offline-first architecture. Workers who lose connectivity mid-flow will see error toasts. Photos captured but not uploaded are in browser memory only — if the page is refreshed or the tab closes, the data is lost. The `pending-upload://` and `storage-failed://` marker URLs preserve metadata but not the actual photo data.

**Confidence:** HIGH (confirmed absence)

**Uncertainty:** None — the absence is conclusive from codebase search.

---

## Claim 7: DEV_PASSPORT_BYPASS not found in frontend

**Status:** CONFIRMED NOT PRESENT IN FRONTEND

**Evidence basis:**
- Search for `DEV_PASSPORT_BYPASS` across entire `ihouse-ui/` directory returned zero results
- Search for `BYPASS` in ops/checkin paths returned zero relevant results

**What was observed:** The string does not exist in the frontend codebase. It may exist in the Python backend (not searched here) as a server-side flag, or it may have been removed. The OCR flow in the frontend always runs the full capture process.

**Confidence:** HIGH (for frontend absence)

**Uncertainty:** May exist as a backend-only bypass. Backend code was not searched for this specific string.

---

## Claim 8: Role-specific bottom navigation is correctly configured

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/BottomNav.tsx`, lines 57-98:
  - CHECKIN_BOTTOM_NAV: [Home (/worker), Check-in (/ops/checkin), Tasks (/tasks)]
  - CHECKOUT_BOTTOM_NAV: [Home (/worker), Check-out (/ops/checkout), Tasks (/tasks)]
  - CHECKIN_CHECKOUT_BOTTOM_NAV: [Today (/ops/checkin-checkout), Arrivals (/ops/checkin), Departures (/ops/checkout), Tasks (/tasks)]
  - CLEANER_BOTTOM_NAV: [Home (/worker), Cleaning (/ops/cleaner), Tasks (/tasks)]
  - MAINTENANCE_BOTTOM_NAV: [Home (/worker), Maintenance (/ops/maintenance), Tasks (/tasks)]

**What was observed:** Five distinct bottom nav configurations. Each provides exactly the tabs relevant to that worker's daily job. The combined checkin_checkout role uniquely gets 4 tabs instead of 3. No cross-contamination (cleaner doesn't see check-in tabs, check-in doesn't see cleaning tabs).

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 9: Worker sub-role routing resolves from JWT correctly

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/roleRoute.ts`, lines 32-45: ROLE_ROUTES map
- Phase 948a: For `role=worker`, reads `worker_role` or `worker_roles[0]` from JWT
- File: `ihouse-ui/app/(app)/worker/page.tsx`: `resolveWorkerRole()` function with same resolution order plus Preview-as override check

**What was observed:** Routing resolution order:
1. Explicit role (e.g., `role=cleaner`) → direct routing
2. Worker + sub-role (`role=worker, worker_role=cleaner`) → sub-role routing
3. Worker + multi-role array (`role=worker, worker_roles=['checkin','checkout']`) → combined role detection → `/ops/checkin-checkout`
4. Worker + no sub-role → `/worker` generic landing

Multi-role workers with `worker_roles=['cleaner', 'maintenance']` get routed to `cleaner` (first in array). No role-selector screen.

**Confidence:** HIGH

**Uncertainty:** The multi-role routing gap is confirmed — only `worker_roles[0]` is used. Workers with multiple roles cannot access their second role from the default landing.

---

## Summary of Evidence

| Memo Claim | Evidence Status | Confidence |
|---|---|---|
| 7-step check-in wizard | DIRECTLY PROVEN | HIGH |
| MobileStaffShell dark theme + mobile layout | DIRECTLY PROVEN | HIGH |
| staffApi.ts session isolation | DIRECTLY PROVEN | HIGH |
| OCR with confidence scoring | DIRECTLY PROVEN | HIGH |
| Cleaner interactive surface | DIRECTLY PROVEN | HIGH |
| No offline mode | CONFIRMED ABSENT | HIGH |
| DEV_PASSPORT_BYPASS | NOT IN FRONTEND | HIGH |
| Role-specific bottom nav | DIRECTLY PROVEN | HIGH |
| Worker sub-role routing | DIRECTLY PROVEN | HIGH |
