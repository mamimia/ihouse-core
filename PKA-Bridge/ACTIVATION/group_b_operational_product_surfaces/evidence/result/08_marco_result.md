# Audit Result: 08 — Marco (Mobile Systems Designer)

**Group:** B — Operational Product Surfaces
**Reviewer:** Marco
**Final closure pass:** 2026-04-04 (depth check complete)
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Final Closure State |
|---|---|
| 7-step check-in wizard with conditional steps | ✅ **Proven resolved** |
| MobileStaffShell mobile layout | ✅ **Proven resolved** |
| staffApi.ts session isolation via sessionStorage | ✅ **Proven resolved** |
| No offline mode / photo upload failure chain | ⚠️ **Real residual risk, partially mitigated** — DB record survives via sentinel; photo bytes can still be permanently lost |
| staffApi.ts mixing guardrail is comment-only | ✅ **Fixed** (prior pass) — ESLint rule added |
| Multi-role worker routing uses only first role | ✅ **Fixed now** — secondary-role links added to worker home |
| Checkout static steps (no conditional skip) | 🔵 **Intentional future gap** — UX inconsistency, not a safety issue |

---

## Fix Applied: ESLint `no-restricted-imports` Rule

**File:** `ihouse-ui/eslint.config.mjs`

Added a `no-restricted-imports` ESLint rule that makes importing `lib/staffApi` from any file outside `app/(app)/ops/**` and `app/(app)/worker/**` a **build-time error**. This converts the comment-only guardrail (which caused the 2026-03-26 staging incident) into a structural enforcement that fails the build before it reaches staging.

Any non-ops page that accidentally imports `staffApi` will now produce:
> `"staffApi must only be imported from /ops/* or /worker/* surfaces. Use lib/api.ts for admin pages."`

This rule covers both `@/lib/staffApi` (alias imports) and relative `**/staffApi` path patterns.

---

## Closure Detail: No Offline Mode / Photo Upload Failure Chain

**Classification: Real residual risk, partially mitigated**

**What is mitigated:** When a Supabase Storage upload fails (network drop, timeout), the code catches the exception and writes a sentinel URL `storage-failed://{booking_id}/{label}/{uuid}` into the DB record. This means:
- The task completion record is not lost
- The event trail exists (cleaning task `COMPLETED`, checkout photos table row exists)
- The failure is detectable by querying `photo_url LIKE 'storage-failed://%'`

**What is NOT mitigated — the real residual risk:** The photo bytes are permanently lost. For scenarios where photo evidence matters operationally (property damage documentation, deposit dispute, insurance claim), losing the photo bytes is a real, non-trivial outcome. The sentinel URL is not a substitute for the photo.

**Why this is not "safe enough":** A property manager discovering a damage dispute after checkout cannot recover the missing photo from the sentinel URL. The sentinel proves the upload was attempted and failed, but does not recover the evidence. This is qualitatively different from "data integrity is maintained."

**Why full closure is not currently possible without larger infra work:**
- A proper fix requires: service worker registration + fetch handler, IndexedDB upload queue, retry-on-reconnect logic, and UX for "pending upload" state
- These are major frontend infrastructure components — not a one-file patch
- Without persistent local storage (IndexedDB), there is no retry path: once the page unloads, the file bytes are gone

**What is the minimum additional hardening done:** None beyond the existing sentinel. Adding a backend query endpoint for `storage-failed://` records (so ops can surface them for re-upload requests) is the next sensible incremental step, but that is a future ops tooling build, not an audit-pass fix.

**Honest closure state:** Partially mitigated. The DB record and audit trail are preserved. The photo bytes can be permanently lost. This is an accepted operational risk at current scale (properties with WiFi, low failure frequency) but must be addressed before deployment in connectivity-constrained environments.

---

## Fix Applied: Multi-Role Worker Secondary Navigation

**Final closure: Fixed now**

**Depth check result:** `worker_roles[0]` was used as the primary surface. A worker with `['cleaner', 'maintenance']` landed on `/ops/cleaner` with no discoverable path to `/ops/maintenance` in the UI.

**Why this was NOT just limited UX:**
- The worker had NO visible link to their secondary work surface
- `/ops/maintenance` is valid for `role=worker` in middleware, but not surfaced
- The actual maintenance tasks assigned to that worker were invisible from their home screen (stats query used `taskRole='CLEANER'`, not `'MAINTENANCE'`)
- Not a safety issue, but a real access gap — legitimate task surfaces were hidden

**Fix applied:** Added `resolveSecondaryRoles()` function to `worker/page.tsx` that reads `worker_roles` from the JWT and returns all recognized roles beyond the primary. An "Also available to you" section is rendered on the worker home page with direct surface links for each secondary role. Middleware already grants access — the fix is purely navigation surfacing.

**What was NOT done (correctly):** A full role-selector page (`/worker/select-role`) remains a future build. The secondary links approach is the safe minimum fix — no new pages, no routing changes, no auth changes. It works within the existing surface model.

---

## What Was Disproven

- **DEV_PASSPORT_BYPASS in frontend**: Confirmed absent from frontend codebase.
- **Role-specific bottom nav gaps**: Confirmed correct — 5 independent configs, no cross-contamination.
- **OCR reliability concern**: Implementation correct. Real-world accuracy is an operational metric.
