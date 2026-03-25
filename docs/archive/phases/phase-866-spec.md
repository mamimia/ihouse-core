# Phase 866 — Model B Concurrent Act As Sessions

**Status:** Closed
**Prerequisite:** Phase 865 (Storage Isolation Audit)
**Date Closed:** 2026-03-25

## Goal

Transition the "Act As" impersonation feature from a single-session policy to a concurrent Model B architecture. This involves allowing multiple isolated worker tabs to coexist safely without polluting the main Admin's `localStorage` token, preventing global logouts when worker sessions end, and finally proving robust cross-browser (Chrome/Safari) support for pop-ups. 

## Invariant

- **Tab Sovereignty:** Each Act As worker tab is perfectly isolated via `sessionStorage`. Ending an Act As session must NEVER mutate or read the root `ihouse_token` in `localStorage`.
- **Concurrency Support:** The backend `/status` API is strictly scoped to `acting_session_id` directly parsed from the JWT, rather than relying on a global "most recent session" DB query.
- **Safari Opening Safety:** Async `window.open` flows must pre-claim the user-gesture by synchronously opening a placeholder popup inside the direct click handler before yielding to network operations.

## Design / Files

| File | Change |
|------|--------|
| `src/api/act_as_router.py` | MODIFIED — Removed global 409 limit to support concurrent sessions. Modified `/status` to validate exactly against `acting_session_id`. Fixed `db` reference bug. |
| `ihouse-ui/lib/ActAsContext.tsx` | MODIFIED — Changed cleanup logic to prevent saving `__new_tab__` back to `localStorage`, protecting the Admin session from being destroyed. |
| `ihouse-ui/components/ActAsSelector.tsx` | MODIFIED — Restructured the `↗` click handler to open a blank `window.open` placeholder synchronously before `await`-ing the API fetch, preventing Safari's "Pop-up window blocked" error. |
| `ihouse-ui/e2e/multi_tab_safari.spec.ts` | NEW — Added WebKit execution script to explicitly test concurrent Act As session logic and end-session boundaries. |

## Result

**All tests pass.** Chrome architecture and interaction proven. WebKit architecture proven. Manual Safari interaction proven. Multi-tab token isolation proven. Admin protection during worker cleanup proven. Safari was blocking Act As because `window.open` happened only after an async wait, breaking direct user-gesture eligibility; fixed by opening a synchronous placeholder immediately on click.
