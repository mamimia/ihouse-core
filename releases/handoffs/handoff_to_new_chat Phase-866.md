# Handoff to New Chat — Phase 866 Closure
**Date:** 2026-03-25
**Current Phase:** 867 (Next — not yet started)
**Last Closed Phase:** 866 — Model B Concurrent Act As Sessions

---

## 1. What Was Accomplished in This Session

### Phase 866 — Model B Concurrent Act As Sessions (CLOSED)

**The objective:** Transition the "Act As" admin impersonation feature from a single-session policy to a fully concurrent, tab-isolated architecture.

**What was done:**

| Area | Change | File |
|------|--------|------|
| Backend: Removed 409 gate | The single-session constraint preventing parallel Act As was removed. Admins can now hold multiple concurrent worker sessions. | `src/api/act_as_router.py` |
| Backend: Session-scoped /status | `/auth/act-as/status` now validates strictly by `acting_session_id` from the JWT — no longer returns global "most active session". Prevents cross-tab confusion. | `src/api/act_as_router.py` |
| Frontend: localStorage pollution fix | `cleanupActAs` was writing a `__new_tab__` sentinel to global localStorage, which logged out the admin and all other active tabs when ending a worker session. Fixed. | `ihouse-ui/lib/ActAsContext.tsx` |
| Frontend: Safari popup fix | Act As was blocked in real Safari ("Pop-up window blocked") because `window.open` was called after an `await`. Fixed by opening a synchronous `about:blank` placeholder immediately on click, then redirecting it after the fetch. Now mirrors the same safe opener pattern as Preview As. | `ihouse-ui/components/ActAsSelector.tsx` |
| E2E test added | `ihouse-ui/e2e/multi_tab_safari.spec.ts` — WebKit automation proof for concurrent session creation, token isolation, and end-session safety. | New file |

### What Was Proven (Evidence Standard)

| Proof | Status |
|-------|--------|
| Chrome concurrent sessions (2 worker tabs simultaneously) | ✅ Proven on staging |
| Chrome token isolation (sessionStorage per tab) | ✅ Proven on staging |
| Chrome admin localStorage preservation after worker tab close | ✅ Proven on staging |
| WebKit/Safari architectural session model | ✅ Proven via Playwright webkit script |
| Manual Safari popup interaction | ✅ Proven by user on real Safari after fix |

### Deliverables Created

- `docs/archive/phases/phase-866-spec.md` — Phase spec (closed)
- `releases/phase-zips/iHouse-Core-Docs-Phase-866.zip` — Full docs/core snapshot
- `docs/core/phase-timeline.md` — Updated with Phases 864, 865, 866
- `docs/core/construction-log.md` — Updated
- `docs/core/current-snapshot.md` — Current Phase = 867
- `docs/core/work-context.md` — Last Closed Phase = 866
- Git commit: `7edb7b8` — pushed to `checkpoint/supabase-single-write-20260305-1747`
- Vercel: `domaniqo-staging.vercel.app` reflects all frontend fixes

---

## 2. Design Decisions Locked in This Session

### Canonical Storage Rule (LOCKED)
- **Admin token** lives in `localStorage` (shared across tabs, survives browser restart)
- **Act As worker token** lives in `sessionStorage` (isolated per tab, evicted on tab close)
- All future code must use `getTabToken()` from `lib/tokenStore.ts` — NEVER read `ihouse_token` directly from `localStorage` in worker context

### Safari Window Opening Rule (LOCKED)
Opening new tabs from React async handlers requires:
1. `window.open('about:blank', '_blank')` synchronously inside the click handler
2. Await the API call
3. Set `popup.location.href = finalUrl` after fetch completes
This is now the canonical pattern. Both `ActAsSelector` and `PreviewAsSelector` implement it.

### Model B Concurrency (LOCKED)
Multiple concurrent Act As sessions per admin are explicitly permitted. Each tab is sovereign. Ending one tab never affects another. Backend validates by `acting_session_id` from JWT, not by global "latest active session" query.

---

## 3. Work Started But Not Closed — Acknowledge Button Audit

At the end of this session, a deep audit of the Cleaner task card's **Acknowledge** button was started. This audit is **not closed** — it is an active open item for the next phase.

### Audit Summary (findings so far)

**Origin:** Acknowledge was introduced in Phase 111 (Task System Foundation) as a formal lifecycle state, and wired to the UI in Phase 157. It is NOT random residue. It exists to serve the SLA escalation engine — a worker's ack stops the external notification cascade (LINE → WhatsApp → Telegram → SMS).

**Lifecycle:**
```
PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED
```
Acknowledge = "I have seen this task." Start Cleaning = "I am physically doing it now."

**Architecture (as designed):**
- `PATCH /worker/tasks/{task_id}/acknowledge`
- Enforces `PENDING → ACKNOWLEDGED` via `VALID_TASK_TRANSITIONS`
- Writes `TASK_ACKNOWLEDGED` audit event
- Staff performance metrics (`avg_ack_minutes`, `sla_compliance_pct`) derive from `acknowledged_at`

**Bug found (code-level, not yet staging-verified):**
`cleaner/page.tsx` at line 317 calls:
```
PATCH /tasks/${task.task_id}/status   { status: 'ACKNOWLEDGED' }
```
instead of the canonical:
```
PATCH /worker/tasks/${task.task_id}/acknowledge
```

**Staging proof captured:**
- Emuna Villa KPG-500 (2026-03-28) was acknowledged on staging
- After click, the card correctly disappeared from top of "Upcoming" section (moved down or removed)
- Network call confirmed: `PATCH /tasks/3627b917b67d30aa/status` → 200 OK
- This confirms the `/tasks/{id}/status` legacy path accepts the mutation — but it is NOT the canonical worker endpoint

**What still needs investigation:**
- Whether the legacy `/tasks/{id}/status` path is tenant-isolated (uses service role key instead of worker JWT?)
- Whether the SLA escalation system observes this transition (does the escalation engine check `ACKNOWLEDGED` status in DB?)
- Whether `acknowledged_at` is being populated correctly when using the legacy path
- Whether the button should be kept, redesigned, or merged into "Start Cleaning"

**Recommendation (preliminary):**
Fix the API path bug first, then make a product decision on whether Acknowledge should appear for all tasks (including upcoming days-away ones) or only for same-day urgent tasks about to breach SLA.

---

## 4. Test Suite State (Run: 2026-03-25)

```
.venv/bin/pytest tests/
7933 passed, 50 failed, 22 skipped
```

The 50 failures are **pre-existing, not introduced by this session**. They fall into known categories:
- `test_task_model_contract.py` — `INSPECTOR` role rename vs `CHECKOUT` alias mismatch
- `test_task_router_contract.py` — tenant isolation mock mismatch
- `test_wave4_problem_reporting_contract.py` — E2E stub integration gap
- `test_wave6/wave7_*` — Task opt-out logic contract drift
- `test_whatsapp_escalation_contract.py` — Per-worker channel routing spec mismatch

None are related to Phase 866 work. All pre-existed before this session.

---

## 5. Deployment State

| Layer | Status | Commit / URL |
|-------|--------|-------------|
| GitHub | ✅ Clean, fully pushed | `7edb7b8` on `checkpoint/supabase-single-write-20260305-1747` |
| Railway (Backend) | ✅ Auto-deployed from push | `https://ihouse-core-production.up.railway.app` |
| Vercel (Frontend) | ✅ Manually deployed | `https://domaniqo-staging.vercel.app` |

---

## 6. Suggested First Actions in Next Chat

1. **Read** `docs/core/BOOT.md` → `current-snapshot.md` → `work-context.md`
2. **Confirm** current phase = 867
3. **Close the Acknowledge audit** from Item 3 above — this is the immediate open thread
4. **Fix the bug:** `cleaner/page.tsx` line 317 — change `/tasks/{id}/status` → `/worker/tasks/{id}/acknowledge`
5. **Continue the worker UI audit** (the user's stated intent was to go button by button across all worker roles, starting with Cleaning, then Check-in, Check-out, Maintenance)

---

## 7. Key Files to Know

| File | Purpose |
|------|---------|
| `src/api/act_as_router.py` | Act As backend — concurrent sessions, JWT-scoped status |
| `src/api/worker_router.py` | Worker task CRUD — acknowledge, start, complete |
| `src/tasks/task_model.py` | Canonical lifecycle, VALID_TASK_TRANSITIONS, SLA times |
| `ihouse-ui/lib/tokenStore.ts` | Canonical token storage (sessionStorage for Act As) |
| `ihouse-ui/lib/ActAsContext.tsx` | Act As tab lifecycle, cleanup must never touch localStorage |
| `ihouse-ui/components/ActAsSelector.tsx` | Admin role switcher — synchronous popup opener pattern |
| `ihouse-ui/components/WorkerTaskCard.tsx` | Shared task card — Acknowledge/Start/Navigate buttons |
| `ihouse-ui/app/(app)/ops/cleaner/page.tsx` | Cleaner UI — **has the wrong API path bug on line 317** |

---

## 8. Current Docs/Core Summary

- **Phase:** 867 (next, not started)
- **Last closed:** 866 — Model B Concurrent Act As
- **Branding:** External = Domaniqo, Internal = iHouse Core — do not mix
- **Git branch:** `checkpoint/supabase-single-write-20260305-1747`
- **Working directory:** `/Users/clawadmin/Antigravity Proj/ihouse-core`

---

*Handoff created at session end: 2026-03-25T22:15 ICT*
