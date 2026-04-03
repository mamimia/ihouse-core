# Activation Memo: Marco — Mobile Systems Designer

**Phase:** 972 (Group B Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (ihouse-ui/app/(app)/ops/*, ihouse-ui/app/(app)/worker/page.tsx, ihouse-ui/components/MobileStaffShell.tsx, AdaptiveShell.tsx, BottomNav.tsx, WorkerTaskCard.tsx, OcrCaptureFlow.tsx, ihouse-ui/lib/staffApi.ts, ihouse-ui/lib/roleRoute.ts)

---

## 1. What in the Current Real System Belongs to This Domain

Marco's domain is the worker and ops mobile surfaces — every screen a field worker uses on their phone. The real system has:

- **6 ops surfaces**: `/ops` (hub), `/ops/checkin` (7-step wizard), `/ops/checkout` (6-step flow), `/ops/checkin-checkout` (combined hub), `/ops/cleaner` (checklist flow), `/ops/maintenance` (task board + problem reports)
- **1 worker landing**: `/worker` (role-aware home with sub-role resolution)
- **MobileStaffShell**: Forced dark theme, full-screen mobile layout, role-specific bottom navigation, safe area handling, touch target standards
- **staffApi.ts**: Token isolation via sessionStorage-first `getTabToken()`, Act-as session scoping
- **OcrCaptureFlow**: Shared OCR component for identity documents and meter readings
- **5 role-specific bottom nav configs**: CHECKIN_BOTTOM_NAV, CHECKOUT_BOTTOM_NAV, CHECKIN_CHECKOUT_BOTTOM_NAV, CLEANER_BOTTOM_NAV, MAINTENANCE_BOTTOM_NAV

## 2. What Appears Built

- **7-step check-in wizard (Phase 971)**: Steps: list → arrival → walkthrough → meter (conditional) → contact → deposit (conditional) → passport → complete → success. Dynamic flow via `getFlow()` based on `chargeConfig.electricity_enabled` and `chargeConfig.deposit_enabled`. StepHeader component shows "Step X of Y" with progress bar. Each step writes to a dedicated backend endpoint independently.

- **6-step checkout flow (Phase D-7)**: Steps: list → inspection → closing_meter → issues → deposit → complete → success. Static flow (all steps always present). Early checkout context detection. Integrates deposit settlement routing.

- **Cleaner surface (Phase E)**: Screen flow: list → detail → checklist → complete → success. Interactive checklist with per-item toggle. Photo capture via `<input type="file" capture="environment">` (rear camera). Supply check with cyclic status toggle (unchecked → ok → low → empty). Inline issue reporting (Phase E-9) creates problem_reports. Completion blocker UI when pre-conditions fail (409 with blockers array). Progress bars for items, photos, supplies.

- **Maintenance surface (Phase F)**: View modes: list → detail → work. MAINTENANCE tasks only. Problem report integration with severity coloring (CRITICAL 5min SLA, HIGH, MEDIUM, LOW). Work notes, start/stop tracking. GPS integration for property location (Waze/Google Maps link).

- **Combined checkin-checkout hub (Phase 865)**: Hub page for `checkin_checkout` role — two cards linking to `/ops/checkin` and `/ops/checkout` respectively. Shows countdown to next arrival/departure. Fetches CHECKIN_PREP and CHECKOUT_VERIFY tasks separately.

- **Worker landing (Phase 290/850)**: Role resolution from JWT: sessionStorage preview override → `worker_role` → `worker_roles[0]` → fallback to generic. ROLE_CONFIGS map each sub-role to work href + task filter. Detects combined role from `worker_roles` array (has both checkin and checkout → checkin_checkout). CompactLangSwitcher for multilingual workers.

- **MobileStaffShell (Phase 376)**: Forced dark theme via `data-theme="dark"`. Safe area insets for notch (`env(safe-area-inset-top)`) and home indicator (`env(safe-area-inset-bottom)`). Touch targets ≥44px (`var(--touch-target-min)`). Phone simulation on desktop (480px centered). Bottom nav per role. Brand-compliant spacing/typography tokens.

- **OcrCaptureFlow (Phase 988)**: Shared across 3 wizard steps (identity_document_capture, checkin_opening_meter_capture, checkout_closing_meter_capture). HTML5 `<input capture="environment">` for camera. Base64 JPEG at 85% quality. Document type selection (PASSPORT, NATIONAL_ID, DRIVING_LICENSE). Confidence scoring: HIGH ≥0.92 (green), MEDIUM 0.85-0.92 (yellow), LOW <0.85 (red + "please verify"). Manual entry fallback if OCR fails. 6-second timeout → manual entry.

- **staffApi.ts session isolation**: `getTabToken()` reads sessionStorage first (Act-as scoped token), falls back to localStorage (normal login). `setActAsTabToken()` stores only in sessionStorage. Each tab gets isolated sessionStorage. Admin's localStorage token untouched when Act-as tab closes.

- **Task card with countdown (Phase 883/885/886/887)**: `useCountdown()` hook with adaptive tick rate. Time-to-action color progression: normal → warning (25min) → critical (5min) → overdue. Duration format adapts: "13d" → "1d 6h" → "18h 20m" → "42m 08s". Server-computed timing gates (`ack_is_open`, `ack_allowed_at`) for AckButton gating.

- **Role-based routing**: `roleRoute.ts` with Phase 948a worker sub-role resolution from JWT. 5 worker sub-roles each map to their specific `/ops/*` surface. Workers with no sub-role get `/worker` generic landing.

## 3. What Appears Partial

- **Photo upload resilience**: Cleaner photo capture attempts FormData upload first, falls back to JSON endpoint with `pending-upload://` marker URL. Checkout photos have a local queue with `local: true` flag. But there's no systematic offline-first pattern — no service worker, no IndexedDB queue, no upload retry scheduler.
- **Checkout wizard static flow**: All 6 steps are always present. Unlike check-in (which skips meter/deposit based on config), checkout doesn't skip closing_meter even if electricity isn't tracked. This may force workers through an irrelevant step.
- **Worker multi-role handling**: `roleRoute.ts` resolves `worker_roles[0]` (first in array). A worker with roles `['cleaner', 'maintenance']` lands on cleaner surface with no access to maintenance. No role-selector screen exists for multi-role workers.

## 4. What Appears Missing

- **No offline mode**: No service worker, no cache-first strategy, no offline indicator UI. Workers in areas with poor connectivity (rural rental properties, basements) get network errors. Photo uploads may fail silently if the fallback also fails.
- **DEV_PASSPORT_BYPASS**: Not found in the frontend codebase. This was either a backend-only bypass or has been removed. The OCR flow always runs through the full capture process.
- **No swipe gestures**: Worker surfaces use tap-only interaction. No swipe-to-acknowledge, swipe-to-complete, or gesture-based navigation. This may be intentional (simpler interaction model) but limits mobile-native feel.
- **No push notification → deep link**: Worker receives LINE/Telegram/WhatsApp alert, opens app, lands on `/worker` (generic landing) rather than the specific task. No deep-link parameter to route directly to the assigned task.

## 5. What Appears Risky

- **Photo upload failure chain**: If both FormData upload and JSON fallback fail, the photo is lost. The cleaner's phone captured it but no persistent local storage exists. At scale, this means lost evidence (e.g., damage documentation during checkout).
- **staffApi.ts mixing guardrail**: Comment in code warns "NEVER import staffApi from admin pages" citing a staging incident (2026-03-26). This is enforced only by developer discipline (code comment), not by a build-time check or ESLint rule. Future developers may violate it.
- **Single-step wizard failure**: Each wizard step writes independently. If a step fails, the worker sees a toast error and can retry. But if the retry also fails (persistent network issue), there's no "save draft locally and sync later" pattern.

## 6. What Appears Correct and Worth Preserving

- **Forced dark theme for field workers**: Correct for the use case — check-in/checkout often happens in dimly lit units.
- **Safe area handling**: Proper `env()` usage for notch and home indicator. Workers on various iPhone/Android models get correct spacing.
- **Conditional wizard steps**: Check-in wizard dynamically builds flow based on property config. Workers don't see irrelevant steps.
- **OCR with manual fallback**: OCR is a nice-to-have; manual entry is always available. The 6-second timeout prevents workers from being stuck.
- **Role-specific bottom nav**: Each worker sub-role gets exactly the navigation they need. Cleaner doesn't see check-in options; check-in agent doesn't see cleaning options.
- **Session isolation via staffApi.ts**: Correct architecture — Act-as token lives in sessionStorage only, never contaminates admin's localStorage. Per-tab isolation is OS-enforced.
- **Adaptive countdown tick rate**: 1s tick <1h, 60s otherwise. Correct battery/performance optimization for mobile.
- **Server-computed timing gates**: Backend decides when AckButton opens. Frontend just reads the flag. No client-side time calculation that could drift.

## 7. What This Role Would Prioritize Next

1. **Photo upload resilience**: Implement a persistent local queue (IndexedDB or SQLite) for photos that fail upload. Retry on connectivity restoration. Show sync status indicator.
2. **Multi-role worker routing**: Add a role-selector screen for workers with multiple sub-roles instead of defaulting to `worker_roles[0]`.
3. **Checkout conditional steps**: Match check-in's pattern — skip closing_meter if electricity not tracked for the property.
4. **Deep-link from notifications**: When a worker receives a task notification, include task_id in the link so the app opens directly to that task.

## 8. Dependencies on Other Roles

- **Talia**: Marco validates mobile behavior; Talia defines the interaction logic. Wizard step navigation, error states, and resumability are shared concerns.
- **Sonia**: Sonia defines that field workers get MobileStaffShell (not standard sidebar). Marco implements that shell. They share the structural boundary.
- **Claudia**: Claudia defines checklist content and photo requirements; Marco ensures the cleaner surface renders them correctly on mobile. The photo capture UX directly implements Claudia's standards.
- **Hana**: Hana manages staff assignment; Marco owns what the worker sees after assignment. The "new worker, zero tasks" empty state is a shared boundary.

## 9. What the Owner Most Urgently Needs to Understand

The mobile worker surfaces are substantially more complete than typical property management mobile apps. The system has working wizards with conditional steps, OCR capture with confidence scoring, role-specific navigation, forced dark theme, and proper mobile safety (safe areas, touch targets, session isolation).

Two mobile-specific concerns need attention:

1. **No offline resilience**: Workers in rental properties often have weak connectivity. Photo uploads fail → no persistent retry queue → evidence lost. This is the #1 mobile gap.

2. **Multi-role workers get only their first role**: A worker assigned `['cleaner', 'maintenance']` can only access cleaner surface from the default routing. No role-selector exists. At scale with multi-skilled workers, this becomes a daily friction point.
