# Claim

`lib/api.ts` (admin) and `lib/staffApi.ts` (worker) use different token storage locations and must never be mixed. Mixing them causes silent 401 errors. This is documented in source code with a confirmed staging incident date.

# Verdict

PROVEN

# Why this verdict

Direct reading of both files confirms the storage difference: `lib/api.ts` reads from `localStorage` (cross-tab persistent), `lib/staffApi.ts` reads via `getTabToken()` which is sessionStorage-first (tab-scoped for Act As isolation). The module header of `staffApi.ts` contains an explicit ⚠️ GUARDRAIL comment that names the constraint, the consequence (silent 401 errors), and the date of the incident that prompted it (2026-03-26). This is direct, dated evidence of a confirmed real-world failure.

# Direct repository evidence

- `ihouse-ui/lib/api.ts` lines 16–17 — `localStorage.getItem("ihouse_token")`
- `ihouse-ui/lib/api.ts` lines 19–23 — `setToken()` writes to `localStorage`
- `ihouse-ui/lib/staffApi.ts` lines 1–15 — full module header with ⚠️ GUARDRAIL
- `ihouse-ui/lib/staffApi.ts` line 34 — `getTabToken()` (sessionStorage-first)
- `ihouse-ui/lib/tokenStore.ts` — `getTabToken()` implementation

# Evidence details

**`lib/api.ts` — localStorage:**
```typescript
let _token: string | null =
    typeof window !== "undefined" ? localStorage.getItem("ihouse_token") : null;
```
Token is read from and written to `localStorage`. Shared across all browser tabs in the same origin.

**`lib/staffApi.ts` — sessionStorage-first with explicit guardrail:**
```typescript
/**
 * Phase 864 — Shared Staff API Utilities
 * Phase 865 — Tab-aware token reads via tokenStore (sessionStorage-first)
 *
 * Single source of truth for API helpers used by worker-facing ops surfaces:
 *   /ops/cleaner, /ops/maintenance, /ops/checkin, /ops/checkout
 *
 * Token reads use getTabToken() which prioritizes sessionStorage (Act As tab)
 * over localStorage (normal login), enabling true parallel tab isolation.
 *
 * ⚠️  GUARDRAIL: This module must ONLY be imported from /ops/* worker surfaces.
 *  NEVER import this from admin pages (/tasks, /bookings, /admin/*, /dashboard).
 *  Admin pages use lib/api.ts which authenticates via localStorage token.
 *  Mixing the two causes silent 401 errors (2026-03-26 staging incident).
 */
```
The incident date `2026-03-26` is embedded in production source code. This is not documentation — it is a warning written after a real failure.

**Why the failure mode is silent:**
- Admin page imports `staffApi.ts` → reads sessionStorage → finds Act As worker token → sends it to admin endpoint → 401.
- This works without Act As active (sessionStorage empty → falls back to localStorage admin token → appears correct).
- Breaks only when an Act As session is open in the same tab, making it intermittent and hard to reproduce without the right session state.

**Token storage summary:**
| Module | Storage | Scope | Intended use |
|--------|---------|-------|--------------|
| `lib/api.ts` | `localStorage` | Cross-tab | Admin/manager pages |
| `lib/staffApi.ts` | `sessionStorage` (via `getTabToken`) | Tab-scoped | Worker/ops pages |

# Conflicts or contradictions

- Both modules export a function named `apiFetch`. Auto-import tools may suggest either. There is no compile-time enforcement preventing the wrong one from being imported.
- Both export `getToken` — same name, different implementations, different storage.

# What is still missing

- Whether any current pages violate the guardrail (would require a grep for wrong-module imports per page type).
- Whether an ESLint rule or TypeScript module boundary enforces the constraint automatically.

# Risk if misunderstood

New pages or components that import the wrong client will work in normal sessions and silently fail when Act As is active. The failure is intermittent, appears as a generic 401, and is not obviously traceable to a client mismatch without knowing this constraint.
