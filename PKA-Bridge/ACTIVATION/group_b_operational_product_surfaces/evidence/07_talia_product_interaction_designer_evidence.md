# Evidence File: Talia — Product Interaction Designer

**Paired memo:** `07_talia_product_interaction_designer.md`
**Evidence status:** Interaction patterns well-evidenced from frontend code; wizard recovery and empty states need broader audit

---

## Claim 1: 401 vs 403 error handling is clean and correct

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/api.ts`, lines 104-115: 401 → `performClientLogout('/login', reason)` (session destroyed); 403 → raised as `ApiError` to component (no logout)
- File: `ihouse-ui/lib/api.ts`, lines 118-132: Error parsing — `body.code` → `body.error` → `"UNKNOWN_ERROR"` priority chain (Phase 1025 Fix A)
- File: `ihouse-ui/lib/staffApi.ts`: Simpler pattern — `if (!res.ok) throw new Error(${res.status})` (bare status code)

**What was observed:** Admin API client (`api.ts`) provides structured error handling with code extraction and human messages. Worker API client (`staffApi.ts`) throws bare status codes. The 401/403 distinction is correctly implemented in `api.ts` but not in `staffApi.ts` — a 401 to a worker surface won't trigger automatic logout through staffApi.

**Confidence:** HIGH for api.ts. MEDIUM for staffApi.ts — the simpler pattern works but loses structured error information.

**Uncertainty:** Whether staffApi.ts 401 handling has caused real-world issues. Workers may experience "stuck" sessions if their token expires but staffApi doesn't trigger logout.

---

## Claim 2: CAPABILITY_DENIED inline handling works

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/capabilityCheck.ts`, lines 22-28: `isCapabilityDenied(err)` checks `detail.startsWith('CAPABILITY_DENIED')`, `extractDeniedCapability(err)` parses capability name from `"CAPABILITY_DENIED:financial"` format
- Usage pattern: Components catch `ApiError` → check `isCapabilityDenied(err)` → set `deniedCapability` state → render inline "access denied" UI

**What was observed:** The pattern exists and the helper functions are correctly implemented. Components that use this pattern show local access-denied UI without navigation disruption. However, how many components actually implement this pattern (vs. showing generic errors on 403) was not exhaustively audited.

**Confidence:** HIGH on the pattern implementation. MEDIUM on coverage across all capability-gated surfaces.

**Uncertainty:** Not all components may implement the CAPABILITY_DENIED check. Some may show generic "Error: 403" for capability-denied responses.

---

## Claim 3: Booking status → UI state mapping is comprehensive

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/bookings/page.tsx`, lines 88-124: `deriveOperationalStatus(booking)` function
- Maps to 9 states: in_stay, checkout_today, overdue_checkout, checking_in_today, upcoming, completed, admin_closed, cancelled, unknown
- Each state has: label, icon, background color, text color, optional border

**What was observed:** The function uses raw DB status (`active`, `confirmed`, `checked_in`, `checked_out`, `canceled`) + UTC date comparisons to derive operational display states. Logic is deterministic and handles edge cases (overdue checkout detected by comparing checkout date to today). Color coding provides clear visual hierarchy: green for in_stay, indigo for today-actions, amber for overdue, red for cancelled.

**Confidence:** HIGH

**Uncertainty:** Whether `deriveOperationalStatus()` is used consistently across all surfaces that display bookings, or if some surfaces use raw DB status directly.

---

## Claim 4: Task status → UI state mapping with animations

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/WorkerTaskCard.tsx`, lines 78-143: Countdown with adaptive tick rate (1s if <1h, 60s otherwise)
- Lines 93-99: Status-to-display mapping (PENDING=dim, ACKNOWLEDGED=accent, IN_PROGRESS=primary+pulse, COMPLETED=green, CANCELED=faint)
- Phase 1027b: IN_PROGRESS tasks get 3px left border + `liveTaskPulse 2s ease-in-out infinite` animation
- Time-to-action: normal → warning (25min) → critical (5min) → overdue

**What was observed:** Task cards provide real-time countdown with color progression. The adaptive tick rate (1s precision when countdown matters, 60s otherwise) is a correct mobile performance optimization. Priority colors (CRITICAL=danger, HIGH=warn, MEDIUM=primary) add urgency layering. Server-computed timing gates (`ack_is_open`, `ack_allowed_at`) prevent premature action.

**Confidence:** HIGH

**Uncertainty:** None on the pattern. Duration format variation ("13d" → "42m 08s") was confirmed.

---

## Claim 5: Check-in wizard has conditional steps

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/ops/checkin/page.tsx`: CheckInStep type = 'list' | 'arrival' | 'walkthrough' | 'meter' | 'contact' | 'deposit' | 'passport' | 'complete' | 'success'
- `getFlow()` function dynamically builds step array based on `chargeConfig.electricity_enabled` and `chargeConfig.deposit_enabled`
- StepHeader component shows "Step X of Y" with progress bar

**What was observed:** The wizard dynamically includes/excludes meter and deposit steps based on property-level configuration. The flow is linear (forward only — no back navigation observed). Step count adapts (5 to 7 depending on config). Navigation between steps is state-driven via the step type.

**Confidence:** HIGH

**Uncertainty:** Back navigation — whether the worker can go back to a previous step was not explicitly confirmed. No back-button handler was observed in the agent's reading, but absence of evidence is not evidence of absence.

---

## Claim 6: Checkout flow uses static step array (no conditional skipping)

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/app/(app)/ops/checkout/page.tsx`: CheckoutStep type includes all steps
- Static flow array: `['list', 'inspection', 'closing_meter', 'issues', 'deposit', 'complete']`

**What was observed:** Unlike check-in which dynamically builds its flow, checkout uses a hardcoded static array. All 6 steps are always present regardless of property configuration. The closing_meter step is always included even if the property doesn't track electricity.

**Confidence:** HIGH

**Uncertainty:** Whether this is intentional (checkout always needs all steps) or a gap (should mirror check-in's conditional logic).

---

## Claim 7: No wizard saga/compensation pattern

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- Check-in steps write to separate endpoints: guest_checkin_form_router, checkin_photos_router, checkin_settlement_router, checkin_identity_router, booking_checkin_router
- Each step writes independently with its own try/catch
- No transaction coordinator or rollback mechanism observed

**What was observed:** Each wizard step is a standalone API call. Success of step N does not depend on step N+1. Failure at any step shows error toast; worker can retry. No "resume from step X" detection — if the worker's phone dies mid-flow, they restart from step 1 (though on-conflict upsert handles re-submission of already-completed steps).

**Confidence:** HIGH

**Uncertainty:** Whether the on-conflict upsert pattern effectively provides resumability in practice (steps 1-4 silently succeed on re-submission, step 5 resumes naturally). If so, the lack of explicit saga may be a non-issue.

---

## Claim 8: Form validation is centralized

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/validation-rules.tsx`, lines 1-153: Rule sets for bookings, properties, tasks, maintenance
- File: `ihouse-ui/components/FormField.tsx`, lines 36-75: Wrapper component with error display
- Lines 92-171: `useFormValidation(rules)` hook

**What was observed:** Validation rules are declarative (required, minLength, maxLength, pattern, validate). FormField renders label, error (aria role="alert"), and hint text. Cross-field validation exists for booking dates. Rules cover 4 domains (bookings, properties, tasks, maintenance) with specific constraints.

**Confidence:** HIGH

**Uncertainty:** Whether all forms in the system use this centralized validation or if some forms have inline/ad-hoc validation.

---

## Claim 9: Preview-as enforces read-only at server level

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/PreviewContext.tsx`, line 19: `isPreviewActive` client-side flag
- File: `ihouse-ui/lib/staffApi.ts`: `X-Preview-Role` header added to all requests when preview is active
- Server enforcement: Backend checks `X-Preview-Role` header and blocks mutations

**What was observed:** Double enforcement: client-side (isPreviewActive disables mutation UI) and server-side (X-Preview-Role header triggers backend read-only mode). Even if the frontend flag is bypassed (e.g., developer tools), the backend blocks mutations based on the header.

**Confidence:** HIGH

**Uncertainty:** Whether ALL backend endpoints check the X-Preview-Role header, or only some. If coverage is partial, some mutations could slip through in preview mode.

---

## Summary of Evidence

| Memo Claim | Evidence Status | Confidence |
|---|---|---|
| 401/403 error separation | PROVEN (api.ts), PARTIAL (staffApi.ts) | HIGH / MEDIUM |
| CAPABILITY_DENIED handling | PROVEN (pattern), PARTIAL (coverage) | HIGH / MEDIUM |
| Booking status → UI mapping | DIRECTLY PROVEN | HIGH |
| Task status → UI mapping | DIRECTLY PROVEN | HIGH |
| Conditional check-in wizard | DIRECTLY PROVEN | HIGH |
| Static checkout flow | DIRECTLY PROVEN | HIGH |
| No wizard saga pattern | DIRECTLY PROVEN | HIGH |
| Centralized form validation | DIRECTLY PROVEN | HIGH |
| Preview-as server enforcement | DIRECTLY PROVEN | HIGH |
