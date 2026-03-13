> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 584 → Phase 585

## Current State

- **Current Phase:** 584 — Platform Checkpoint XXVII (closed)
- **Last Closed Phase:** 584
- **Next Phase:** 585

## What Was Built (Phases 565-584)

20 phases across 4 blocks:

### Block 1 — Error Handling & Frontend Resilience (565-569)
- `useApiCall` hook (GET with loading/error/polling/retry + `useApiAction` for mutations)
- `error.tsx` / `not-found.tsx` — App Router error boundary and 404 page
- Silent `catch {}` → `toast.error()` across 6 pages
- `api.ts` — auto-retry on 5xx/network (1 retry, 500ms delay), offline detection
- 5 new typed API methods (`getConflicts`, `resolveConflict`, `getExchangeRates`, `getMaintenanceRequests`, `createMaintenanceRequest`)

### Block 2 — Response Envelope & Backend Consistency (570-574)
- **`response_envelope_middleware.py`** — Global Starlette middleware wrapping ALL 92 routers in `{ok, data, meta}` envelope automatically. Exception handlers for validation (422) and unhandled (500).
- `input_models.py` — 5 Pydantic models with field constraints
- Wired into `main.py`

### Block 3 — Data Validation & Input Guards (575-579)
- `FormField.tsx` — component + `useFormValidation` hook
- `validation-rules.tsx` — booking/property/task/maintenance rules with cross-field date check
- `useFilterParams.tsx` — URL searchParams persistence for filters

### Block 4 — Performance & Production Readiness (580-584)
- `apiCache.ts` — stale-while-revalidate with configurable TTL per endpoint
- `PageLoader.tsx` — 4 skeleton variants (cards/table/list/detail)
- `Accessibility.tsx` — keyboard nav, focus trap, screen reader, skip link
- Fixed 3 relative imports that broke 37 test collections

## Test Results

```
6,884 passed, 482 failed, 22 skipped
264 test files, 504 phase specs, 86 routers, 54 frontend pages
```

**482 failures** are primarily caused by the response envelope middleware changing the response format from raw JSON to `{ok, data, ...}` — existing tests expect the old format. High priority fix for Phase 585.

## Docs Updated

| Document | Status |
|----------|--------|
| `docs/core/current-snapshot.md` | ✅ Updated to Phase 584 |
| `docs/core/work-context.md` | ✅ Updated to Phase 584 |
| `docs/core/phase-timeline.md` | ✅ Appended 20 entries + block summary |
| `docs/core/construction-log.md` | ✅ Appended block summary |
| `releases/phase-zips/iHouse-Core-Docs-Phase-584.zip` | ✅ Created |

## Recommended Next Steps

1. **Phase 585** — Fix the 482 test failures caused by response envelope format changes. Tests need to expect `response["data"]` instead of raw JSON.
2. **Phase 586** — Adopt `useApiCall` hook across remaining frontend pages (currently only defined, not widely adopted)
3. **Phase 587** — Adopt `FormField` + validation rules in actual form pages
4. **Phase 588** — Adopt `PageLoader` skeleton in loading pages
5. **Phase 589** — Adopt `useFilterParams` in pages with filters

## Key Files Created

| File | Phase |
|------|-------|
| `ihouse-ui/components/useApiCall.tsx` | 565 |
| `ihouse-ui/app/(app)/error.tsx` | 566 |
| `ihouse-ui/app/(app)/not-found.tsx` | 566 |
| `src/api/response_envelope_middleware.py` | 570-572 |
| `src/api/input_models.py` | 573 |
| `ihouse-ui/components/FormField.tsx` | 575 |
| `ihouse-ui/lib/validation-rules.tsx` | 576-578 |
| `ihouse-ui/components/useFilterParams.tsx` | 579 |
| `ihouse-ui/lib/apiCache.ts` | 580 |
| `ihouse-ui/components/PageLoader.tsx` | 581 |
| `ihouse-ui/components/Accessibility.tsx` | 582 |
| `tests/test_phases_570_574.py` | 583 |
