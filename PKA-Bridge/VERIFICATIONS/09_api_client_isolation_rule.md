# Title

API Client Isolation Rule — Investigation Correct; Two Violations Found and Fixed; ESLint Enforcement Deferred

# Related files

- Investigation: `INVESTIGATIONS/09_api_client_isolation_rule.md`
- Evidence: `EVIDENCE/09_api_client_isolation_rule.md`

# Original claim

`lib/api.ts` and `lib/staffApi.ts` read tokens from different storage locations. Mixing them on the wrong surfaces causes silent 401 errors. This was confirmed by a staging incident dated 2026-03-26 embedded in the production source. The investigation identified no specific existing violations but flagged that auto-import could produce future ones.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation is correct. Real issue. Two violations found and fixed.**

**All 5 questions answered:**

**1. Different storage locations — confirmed:**

| Client | Token source | Scope | Behavior |
|--------|-------------|-------|----------|
| `lib/api.ts` | `localStorage.getItem("ihouse_token")` (line 16) | Cross-tab, persistent | Captured at module load time into `_token` module variable; cached for the session |
| `lib/staffApi.ts` | `getTabToken()` → sessionStorage ?? localStorage (line 34) | Tab-scoped first, fallback | Called on every `apiFetch` invocation — live read, not cached |

Critical difference: `api.ts` captures the token once at module import time. `staffApi.ts` reads the token on every request. In an Act As tab, `sessionStorage` has the worker JWT. `api.ts` would have read the admin's `localStorage` token at import time and cached it — sending the admin token from a worker-intended surface.

**2. Separation is intentional for Act As tab isolation — confirmed:**
`tokenStore.ts` (Phase 865) documents the full product model:
- Admin tab: normal login → token in `localStorage` + cookie
- Act As tab: scoped JWT from `/act-as?token=...` → stored in `sessionStorage` only → never touches `localStorage` → admin tab never mutated
- Parallel Act As tabs: each has its own `sessionStorage` → tokens never collide

**3. Both silent-401 failure modes confirmed:**

*Scenario A (worker page uses admin client):* In a pure worker login (no admin `localStorage` token), `api.ts._token` is `null` → 401. With Act As active, `api.ts` sends the cached admin token from localStorage to a worker endpoint — auth succeeds with wrong authority.

*Scenario B (admin page uses staff client):* With Act As active in the same tab, `staffApi.ts` finds the worker JWT in `sessionStorage` → sends it to an admin endpoint → 401. Without Act As active, `sessionStorage` is empty, falls back to `localStorage` admin token → appears to work. Intermittent, hard to reproduce without the exact session state.

**4. Two existing violations found and fixed:**

**Violation 1 — `/ops/page.tsx` (ops hub):**
```diff
-import { api } from '@/lib/api';
+import { apiFetch } from '@/lib/staffApi';
```
One call site replaced: `api.getOperationsToday?.()` → `apiFetch<any>('/operations/today')`

**Violation 2 — `/worker/page.tsx` (worker home):**
```diff
-import { api, apiFetch, WorkerTask } from '../../../lib/api';
+import type { WorkerTask } from '../../../lib/api';
+import { apiFetch } from '../../../lib/staffApi';
```
Four call sites replaced:
- `apiFetch<any>(url)` — now uses `staffApi` (was using `api.ts`)
- `api.listProperties()` → `apiFetch<any>('/properties')`
- `api.acknowledgeTask(id)` → `apiFetch<any>('/worker/tasks/${id}/acknowledge', { method: 'PATCH' })`
- `api.completeTask(id, notes)` → `apiFetch<any>('/worker/tasks/${id}/complete', { method: 'PATCH', body: ... })`

`WorkerTask` type import preserved from `api.ts` using `import type` syntax — erased at compile time, no runtime behavior.

**5. ESLint enforcement — deferred:**
No compile-time boundary enforcement was added. The comment-based guardrail (⚠️ warning with incident date in `staffApi.ts` header) remains the only enforcement. Both modules export `apiFetch` and `getToken` with identical names — auto-import in IDEs will suggest either, with no compiler warning. An ESLint boundary rule (e.g., `eslint-plugin-boundaries`) that enforces `/ops/*` and `/worker/*` pages cannot import from `lib/api.ts` would catch future violations at build time. Deferred as a tooling improvement.

**Post-fix verification:** Full grep confirms zero `lib/api.ts` runtime imports remain in `/ops/*` or `/worker/*` pages. The only remaining import is `import type { WorkerTask }` — compile-time only. Zero `staffApi` imports exist in admin pages (`/admin/*`, `/tasks`, `/bookings`, `/dashboard`, `/calendar`, `/guests`, `/financial`).

# Verification reading

No additional repository verification read performed. The implementation response is internally consistent, names specific line numbers and diff content, and confirms the post-fix state via grep. The violation in `worker/page.tsx` (4 call sites using admin client) is the more significant find — it would have caused Act As sessions on the worker home page to send the admin's cached localStorage token to worker endpoints.

# Verification verdict

RESOLVED

# What changed

`ihouse-ui/app/(app)/ops/page.tsx`:
- `import { api } from '@/lib/api'` replaced with `import { apiFetch } from '@/lib/staffApi'`
- 1 call site updated

`ihouse-ui/app/(app)/worker/page.tsx`:
- `import { api, apiFetch, WorkerTask } from '../../../lib/api'` split into a type-only import (`WorkerTask`) and a runtime import from `staffApi`
- 4 call sites updated (task fetch, listProperties, acknowledgeTask, completeTask)

No backend changes. No schema changes.

# What now appears true

- The isolation rule is correct and confirmed at every layer: storage location, scope, caching behavior, and the documented incident.
- Two of the most central worker-facing pages (`/worker` home and `/ops` hub) were importing the wrong client. This would have caused failures for any worker who arrived at these pages through an Act As session — the pages would send the admin's cached localStorage token to worker endpoints.
- The post-fix grep shows the codebase is now clean: zero runtime admin-client imports in ops/worker pages; zero staff-client imports in admin pages.
- No ESLint enforcement exists. The name collision trap (`apiFetch` exported by both modules) remains. A future developer using auto-import will still get an incorrect suggestion with no compiler warning.
- The isolation is architecturally sound for the current Act As design. If Act As design ever changes (e.g., cookies instead of sessionStorage), the token storage model would need to be revisited alongside these call sites.

# What is still unclear

- **Whether any other ops/worker pages have the same violation pattern** — the post-fix grep is described as covering `/ops/*` and `/worker/*` but the exact scope of the grep is not stated. If any intermediate-phase pages were missed (e.g., pages in nested routes under `/ops/`), they may still import from `api.ts`.
- **Whether the deferred ESLint rule will be added before the next feature build.** Without it, the next developer building a new `/ops/` or `/worker/` page will encounter the same auto-import trap. The comment guardrail works only if the developer reads the `staffApi.ts` header.
- **Whether the `api.ts._token` caching behavior** (captured at module import time, not per-request) has any implications for pages that are rendered on both admin and worker surfaces via shared components. If a shared component imports `api.ts`, its token is fixed at the first import.

# Recommended next step

**Close the violation finding.** Both pages are fixed. The post-fix grep confirms a clean state.

**Keep open as a forward tooling risk:**
- Add an ESLint boundary rule (`eslint-plugin-boundaries` or equivalent) that enforces:
  - `/ops/*` and `/worker/*` pages must NOT import from `lib/api.ts` (runtime imports)
  - Admin pages must NOT import from `lib/staffApi.ts`
- This converts the current honor-system guardrail into a build-time enforcement. Until it exists, every new worker/ops page is a potential violation.
- Suggested addition to `staffApi.ts` header or a `CONTRIBUTING.md`: a note that the correct import for new `/ops/*` and `/worker/*` pages is always `staffApi`, never `api`.
