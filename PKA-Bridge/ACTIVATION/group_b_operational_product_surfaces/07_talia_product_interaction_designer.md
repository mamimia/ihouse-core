# Activation Memo: Talia — Product Interaction Designer

**Phase:** 972 (Group B Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (ihouse-ui/lib/api.ts, staffApi.ts, capabilityCheck.ts, PreviewContext.tsx, ActAsContext.tsx, PreviewAsSelector.tsx, ActAsSelector.tsx, validation-rules.tsx, FormField.tsx, Skeleton.tsx, Toast.tsx, WorkerTaskCard.tsx, bookings/page.tsx, ops/checkin/page.tsx, ops/checkout/page.tsx)

---

## 1. What in the Current Real System Belongs to This Domain

Talia's domain is interaction architecture — how users move through the system, what they see at each state, and how errors are handled. The real system implements interaction patterns across:

- **Error handling**: Structured 401/403 distinction in `api.ts` with CAPABILITY_DENIED parsing via `capabilityCheck.ts`
- **Capability-gated UI**: Components catch 403 errors and show local "access denied" rather than redirecting
- **Preview-as / Act-as interaction**: Two distinct admin impersonation modes with different visual indicators, mutation gating, and session management
- **State-to-UI mapping**: `deriveOperationalStatus()` in bookings, task status color/animation system in WorkerTaskCard
- **Multi-step wizard flows**: 7-step check-in wizard (with conditional step skipping), 6-step checkout flow
- **Form validation**: Centralized `useFormValidation` hook with declarative rule sets
- **Loading/feedback**: Skeleton shimmer system, Toast notification stack, live countdown components

## 2. What Appears Built

- **401 vs 403 error handling (Phase 862 P44)**: `api.ts` lines 104-115 cleanly separate authentication failure (401 → logout) from authorization failure (403 → component handles locally). Error parsing (Phase 1025 Fix A) normalizes `{code, message}` from both standard and legacy backend formats. `staffApi.ts` is simpler — throws `Error(status)` without structured parsing.

- **CAPABILITY_DENIED pattern**: `capabilityCheck.ts` exports `isCapabilityDenied(err)` and `extractDeniedCapability(err)` that parse the `"CAPABILITY_DENIED:financial"` error format. Components use this to show inline "access denied" UI instead of a global error page.

- **Preview-as mode**: SessionStorage-based with yellow "👀 PREVIEWING" banner. `isPreviewActive` flag disables all mutations. X-Preview-Role header sent to backend for server-enforced read-only. Opens in new tab via PreviewAsSelector.

- **Act-as mode**: Scoped JWT with TTL countdown, stored in sessionStorage per-tab. Red "🔴 ACTING AS" banner. Opens in new tab. POST `/auth/act-as/start` → scoped token → redirect to role-appropriate surface. TTL-based session expiry (default 3600s).

- **Booking status → UI mapping**: `deriveOperationalStatus()` function maps raw DB status + UTC date comparisons to 9 operational display states (in_stay, checkout_today, overdue_checkout, checking_in_today, upcoming, completed, admin_closed, cancelled, unknown). Each has distinct color, icon, and background treatment.

- **Task status → UI mapping**: WorkerTaskCard renders 5 states (PENDING, ACKNOWLEDGED, IN_PROGRESS, COMPLETED, CANCELED) with distinct colors, animations (liveTaskPulse for IN_PROGRESS), and countdown displays. Priority colors (CRITICAL=danger, HIGH=warn, MEDIUM=primary). Time-to-action color progression: normal → warning (25min) → critical (5min) → overdue.

- **Check-in wizard (Phase 971)**: 7 steps with conditional skipping. `getFlow()` dynamically builds step array based on `chargeConfig` (electricity_enabled, deposit_enabled). Step types: list → arrival → walkthrough → meter? → contact → deposit? → passport → complete → success. StepHeader shows "Step X of Y" with progress bar.

- **Checkout flow (Phase D-7)**: 6 steps: list → inspection → closing_meter → issues → deposit → complete → success. Static flow (no conditional skipping). Early checkout detection adds context.

- **Form validation**: Centralized in `validation-rules.tsx` with rule sets for bookings (date format, date ordering), properties (name length, numeric ranges), tasks (kind, priority enum), and maintenance (title length, priority enum). `FormField` component renders label, error message (aria role="alert"), and hint text.

- **Skeleton loading**: 4 variants (line, card, circle, table) with CSS shimmer animation (1.5s). Used across admin pages.

- **Toast notifications**: 4 types (success, error, warning, info) with auto-dismiss, click-to-dismiss, slideIn animation. Max 5 visible. Fixed bottom-right positioning.

- **Server-computed timing gates (Phase 1033)**: Tasks provide `ack_is_open`, `ack_allowed_at`, `start_is_open`, `start_allowed_at` for gating worker actions. AckButton shows "Opens in Xh Ym" when gate is closed.

## 3. What Appears Partial

- **Checkout wizard conditional steps**: Unlike check-in which dynamically skips meter/deposit steps, checkout uses a static flow array. Whether the closing_meter step should be conditional (matching check-in's electricity_enabled) was not observed.
- **staffApi.ts error handling**: Much simpler than `api.ts` — throws bare `Error(status)` without structured code/message parsing. Worker surfaces may show generic error messages where admin surfaces show specific ones.
- **Empty state patterns**: Found in PreviewAsSelector ("No active users for this role") and ActAsSelector, but systematic empty state coverage across admin, ops, worker, and owner surfaces was not fully mapped. Whether a newly invited worker with zero tasks sees a helpful empty state vs. a blank page is unknown.
- **Checkout-to-settlement handoff**: The checkout wizard includes a "deposit" step that routes to settlement. Whether the interaction correctly handles the zero-deposit case (no deposit collected at check-in → skip settlement) depends on frontend skip logic that was not fully traced.

**Open Group A question — settlement endpoint authorization**: If settlement mutation endpoints lack full capability guards, the checkout wizard's deposit step may expose settlement actions to users who should only have read access. This interaction question depends on Daniel's settlement authorization verification.

## 4. What Appears Missing

- **No saga/compensation for wizards**: Both check-in and checkout wizards write each step independently. No transaction coordinator, no rollback on mid-flow failure. If step 5 fails after steps 1-4 succeeded, the worker sees an error toast and can retry — but there's no structured recovery path.
- **No step resumability signal**: If a worker's phone dies mid-wizard, the system has the partial data (steps 1-4 written) but the frontend doesn't signal "resume from step 5". The worker likely restarts the flow, and on-conflict upsert handles duplicate writes silently.
- **No capability-loss mid-session handling**: If a manager's capability is revoked while they're using the surface, the next API call returns 403/CAPABILITY_DENIED. The component shows inline "access denied" — but there's no session-level notification that capabilities have changed. The manager discovers it only when they try to act.
- **No confirmation dialog standard**: Destructive actions (admin close booking) use inline confirmation with disclaimer text, but this pattern is hand-built per page rather than using a shared `ConfirmDialog` component. New destructive actions may omit confirmation.

## 5. What Appears Risky

- **staffApi.ts error opacity**: Workers get bare status-code errors. If a CAPABILITY_DENIED response comes to a worker surface (unlikely but possible via Act-as edge cases), it would show as generic "Error: 403" rather than a helpful message.
- **Wizard failure mid-deposit**: In check-in, if the deposit step (step 5) fails, the guest's form data, photos, and meter reading are all saved, but the check-in is not completed and no guest portal token is issued. The practical impact depends on whether the worker can retry step 5 without restarting — if retry works, impact is low.
- **No input sanitization layer visible**: Form validation enforces formats and lengths, but no XSS sanitization or HTML escaping layer was observed in the validation rules. Backend likely handles this, but the frontend pattern doesn't show it.

**Open Group A question — checkout canonicality**: The checkout wizard's final step transitions booking status via direct write (bypassing apply_envelope). If this is considered architecture debt rather than accepted design, any interaction pattern built on checkout completion may need revision.

## 6. What Appears Correct and Worth Preserving

- **401/403 separation**: Clean, correct, and well-implemented. Authentication failure logs out; authorization failure is handled locally. This is the right pattern.
- **CAPABILITY_DENIED inline handling**: Components show access-denied UI locally instead of redirecting. This preserves context — the user doesn't lose their place.
- **Preview-as read-only enforcement**: Server-side via X-Preview-Role header, not just client-side. Even if the frontend flag is bypassed, the backend blocks mutations.
- **Booking operational status derivation**: `deriveOperationalStatus()` is a clean, well-structured function that maps raw data to meaningful operational display. UTC-based date comparison avoids timezone issues.
- **Task countdown with adaptive tick rate**: 1s tick when <1h, 60s tick otherwise. Efficient — doesn't drain battery on mobile with unnecessary re-renders.
- **Conditional wizard steps**: Dynamic flow array based on property charge config. Workers don't see irrelevant steps (no meter step if electricity not tracked, no deposit step if not required).

## 7. What This Role Would Prioritize Next

1. **Map empty states across all surfaces**: Every surface needs a defined empty state. Priority: worker surfaces (new worker with zero tasks), owner portal (no financial data yet), manager dashboard (no team members).
2. **Standardize destructive action confirmation**: Extract the inline confirmation pattern from bookings into a reusable `ConfirmDialog` component.
3. **Improve staffApi.ts error handling**: Add structured error parsing matching api.ts, so worker surfaces show meaningful messages.
4. **Define wizard resumability**: Determine whether wizards should detect partial completion and offer "resume from step X" or always restart.

## 8. Dependencies on Other Roles

- **Daniel**: Talia needs Daniel to clarify settlement endpoint authorization — affects whether the checkout deposit step needs additional capability gating.
- **Marco**: Talia defines interaction logic; Marco validates it works on mobile. The wizard failure/retry UX is a shared concern.
- **Sonia**: Sonia defines which surfaces exist; Talia defines the interaction patterns within them. The empty-state audit needs Sonia's surface differentiation map.
- **Nadia (Group A)**: staffApi.ts error handling improvement depends on Nadia's integration contract work.

## 9. What the Owner Most Urgently Needs to Understand

The interaction architecture is well-structured with correct error handling patterns, clean state-to-UI mappings, and a working capability-denial system. The check-in and checkout wizards are the most complex interaction flows and they work — conditional steps, progress indicators, OCR capture with confidence scoring.

Two interaction concerns need attention:

1. **No wizard recovery path**: If a worker's flow fails mid-way, there's no structured resume. Workers retry manually, and on-conflict upsert handles duplicates. This works at current scale but creates risk at higher volume.

2. **Error message asymmetry**: Admin surfaces get structured error messages with capability names. Worker surfaces get bare status codes. Field workers who encounter errors have no diagnostic information — they just see "Error: 403" and need to escalate to admin.
