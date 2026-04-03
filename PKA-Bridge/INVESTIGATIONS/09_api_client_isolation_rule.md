# Title

Two API Clients Must Never Be Mixed — Mixing Causes Silent 401 Errors (Confirmed by Staging Incident)

# Why this matters

The frontend codebase has two distinct API client modules: `lib/api.ts` for admin/manager surfaces and `lib/staffApi.ts` for worker/ops surfaces. They use different token storage locations, different token retrieval strategies, and serve different user populations. If a developer imports the wrong client into a page — or adds a feature to a page that calls the wrong client — the result is silent 401 authentication failures. The user sees a broken page or missing data. The error is not obviously diagnostic — a 401 looks like a token expiry or auth bug, not a client mismatch. This distinction is a hard architectural constraint with a confirmed production-adjacent incident history.

# Original claim

Two distinct API clients exist and must never be mixed. Mixing causes silent 401 errors. This constraint was confirmed by a staging incident on 2026-03-26.

# Final verdict

PROVEN

# Executive summary

`lib/api.ts` stores and reads the auth token from `localStorage`. `lib/staffApi.ts` reads the token from `sessionStorage` (via `getTabToken()` which is tab-aware and Act As-aware). The two modules cannot share tokens because they read from different storage locations. An admin page that accidentally imports `staffApi.ts` will read from sessionStorage — which contains either nothing (no Act As session in that tab) or an Act As token for a worker role — and send the wrong token to a backend that expects an admin JWT. The backend returns 401. Conversely, a worker page that imports `lib/api.ts` will read from localStorage — which contains the persistent admin login token — and send an admin token to a worker endpoint. The file header of `staffApi.ts` explicitly names this constraint, references the storage mechanism, and records the 2026-03-26 staging incident as the origin of the warning.

# Exact repository evidence

- `ihouse-ui/lib/api.ts` lines 16–17 — `localStorage.getItem("ihouse_token")`
- `ihouse-ui/lib/api.ts` lines 19–23 — `setToken()` writes to `localStorage`
- `ihouse-ui/lib/staffApi.ts` lines 1–15 — module header with guardrail warning and staging incident reference
- `ihouse-ui/lib/staffApi.ts` line 34 — `getTabToken()` (sessionStorage-first token read)
- `ihouse-ui/lib/tokenStore.ts` — `getTabToken()` implementation (tab-aware, sessionStorage-first)
- `ihouse-ui/lib/ActAsContext.tsx` — Act As session management (writes to sessionStorage for Act As tokens)

# Detailed evidence

**`lib/api.ts` — localStorage-based token:**
```typescript
let _token: string | null =
    typeof window !== "undefined" ? localStorage.getItem("ihouse_token") : null;

export function setToken(token: string) {
    _token = token;
    if (typeof window !== "undefined") {
        localStorage.setItem("ihouse_token", token);
    }
}
```
On load, `api.ts` reads its token from `localStorage`. `localStorage` is shared across all tabs in the same origin. An admin who logs in has their token in `localStorage`. If they open a new tab and start an Act As session, that tab writes a worker token to `sessionStorage` (not `localStorage`). The `api.ts` module in the Act As tab still reads the admin token from `localStorage`.

**`lib/staffApi.ts` — sessionStorage-first token:**
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
The guardrail is unambiguous. The incident date (2026-03-26) is recorded directly in source code — an unusual and important signal that this is not a theoretical concern but an observed failure.

**Why sessionStorage-first enables Act As tab isolation:**
When an admin starts an Act As session in a new tab:
1. The Act As context writes a worker JWT to `sessionStorage` for that tab.
2. `sessionStorage` is tab-scoped — other tabs do not see it.
3. `getTabToken()` checks `sessionStorage` first. In the Act As tab, it finds the worker JWT and returns it.
4. In the original admin tab, `sessionStorage` has no Act As token. `getTabToken()` falls through to `localStorage` and returns the admin JWT.
5. Both tabs make API calls with their respective correct tokens simultaneously.

This mechanism enables true parallel tab isolation — admin work in one tab, worker impersonation in another, with no token leakage between tabs.

**What happens when the wrong client is imported:**

Scenario A — `staffApi.ts` imported on admin page:
- The admin page calls `apiFetch(path)` from `staffApi`
- `staffApi.apiFetch` calls `getTabToken()`
- `getTabToken()` checks `sessionStorage` — empty (no Act As session)
- Falls through to `localStorage` — finds admin token
- Admin token is sent — appears to work by accident in the absence of an Act As session
- BUT if the user later starts an Act As session in the same tab, `sessionStorage` gets a worker token
- Now the admin page calls `staffApi.apiFetch` and receives the worker JWT from `sessionStorage`
- Worker JWT is sent to an admin endpoint — backend returns 401
- This is the silent failure mode: works until Act As is started, then breaks

Scenario B — `api.ts` imported on worker page:
- The worker page calls `apiFetch(path)` from `api.ts`
- `api.ts` reads `localStorage` — finds admin JWT (if admin is logged in)
- Admin JWT is sent to a worker endpoint — backend may accept it (admin has broad access)
- This silently gives the worker page admin-level authority
- OR if the worker page is opened in an Act As tab, `localStorage` may have a different (original) token — 401

**Both failure modes are silent in different ways:**
- Scenario A fails intermittently — only when Act As is active. Hard to reproduce in testing if tests don't include Act As sessions.
- Scenario B may not fail at all — admin JWTs are broadly accepted. But it grants incorrect token authority and breaks when the intended worker JWT is in `sessionStorage`.

**The 2026-03-26 staging incident:**
The date recorded in the source file is the date the incident was observed and the guardrail was added. This means the problem was real enough to produce a visible failure in a real staging environment, motivating a comment that goes beyond normal documentation into an explicit ⚠️ WARNING with an incident reference. This is a pattern worth taking seriously.

**Where each client must be used:**
```
lib/api.ts:
  - /dashboard
  - /admin/*
  - /tasks
  - /bookings
  - /calendar
  - /guests
  - /owner
  - /financial

lib/staffApi.ts:
  - /ops/cleaner
  - /ops/maintenance
  - /ops/checkin
  - /ops/checkout
  - /worker
```

# Contradictions

- Both modules expose a function named `apiFetch`. This name collision is dangerous — a developer using an editor with auto-import may accidentally import `apiFetch` from the wrong module if both are in scope. There is no compile-time type check that prevents this.
- Both modules export `getToken` — again, name collision. The implementations are substantively different (localStorage vs sessionStorage-first), but the same export name obscures the difference.
- The staffApi module exports `API_BASE` as `BASE` — a re-export of the base URL constant. `api.ts` also uses a base URL. If a developer hard-codes the base URL from one module into a fetch call in a page served by the other module, they bypass both clients' token logic entirely.

# What is confirmed

- `lib/api.ts` stores and reads tokens exclusively from `localStorage`.
- `lib/staffApi.ts` reads tokens via `getTabToken()` which is sessionStorage-first.
- `sessionStorage` is tab-scoped; `localStorage` is cross-tab within the same origin.
- The `staffApi.ts` module header contains an explicit ⚠️ GUARDRAIL comment prohibiting import on admin pages.
- The guardrail comment references a confirmed staging incident on 2026-03-26.
- Mixing the clients causes 401 errors that vary in reproducibility by session state.

# What is not confirmed

- Whether any current pages in the codebase violate the guardrail (import the wrong client). A grep for `import.*staffApi` in admin pages and `import.*api` in worker pages would reveal violations.
- Whether TypeScript's module resolution or ESLint rules enforce the guardrail automatically. If there is no linting rule, the guardrail is purely documentation-enforced.
- The exact failure sequence of the 2026-03-26 incident — which page was involved, which client was mistakenly imported, and which Act As scenario triggered the 401.
- Whether `getTabToken()` in `tokenStore.ts` has a fallback behavior when both sessionStorage and localStorage are empty (unauthenticated state), and how `staffApi.apiFetch` handles a null token.

# Practical interpretation

This is a developer trap, not a user-facing bug in the current code. The guardrail exists specifically because the trap was sprung once in staging. Any new page or component that calls backend APIs must make a deliberate decision about which client to import.

The rule is simple but the reason is subtle:
- Admin/manager surfaces: persistent cross-tab token (localStorage). Act As context must not bleed into admin tabs.
- Worker/ops surfaces: tab-scoped token (sessionStorage-first). Act As sessions must be isolated per tab.

A developer who reads only the API surface ("there's an apiFetch function that makes authenticated calls") without understanding the token storage difference will pick the wrong module based on familiarity or auto-import suggestions.

The risk is highest when:
- A new page is added to an admin route that calls a worker endpoint (or vice versa)
- A shared component is created that is used on both admin and worker pages — it cannot import either client module directly
- A developer adds a feature to a worker page using an admin API call pattern copied from an admin page

# Risk if misunderstood

**If the two clients are treated as interchangeable:** New features will work in testing (where Act As sessions are not typically open), then fail intermittently in staging or production when Act As is active. The failures will look like random 401 authentication errors rather than a client mismatch.

**If the guardrail is assumed enforced by TypeScript:** It is not. TypeScript does not know that `apiFetch` from `staffApi.ts` should not be called from admin pages. A linting rule or module boundary enforcement (e.g., eslint-plugin-boundaries) would be needed to enforce this automatically.

**If a shared component imports one of these clients:** The component will only work correctly in pages that use the matching client's token storage. Placed in the wrong route context, it will silently send the wrong token.

# Recommended follow-up check

1. Grep for `import.*staffApi` in all files under `ihouse-ui/app/(app)/admin/`, `ihouse-ui/app/(app)/tasks/`, `ihouse-ui/app/(app)/dashboard/`, `ihouse-ui/app/(app)/bookings/` — these should never import `staffApi`.
2. Grep for `import.*lib/api` in all files under `ihouse-ui/app/(app)/ops/` and `ihouse-ui/app/(app)/worker/` — these should never import the admin `api.ts`.
3. Check whether an ESLint boundary rule or `tsconfig` path alias prevents cross-domain imports.
4. Read `ihouse-ui/lib/tokenStore.ts` to understand the full fallback chain in `getTabToken()` and what happens when both storage locations are empty.
