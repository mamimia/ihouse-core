# Audit Result: 07 — Talia (Product Interaction Designer)

**Group:** B — Operational Product Surfaces
**Reviewer:** Talia
**Closure pass:** 2026-04-04
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Closure State |
|---|---|
| 401 vs 403 handling in `api.ts` | ✅ **Proven resolved** — correct and clean |
| `staffApi.ts` missing 401 auto-logout | ✅ **Fixed now** — `performStaffLogout()` added |
| CAPABILITY_DENIED inline pattern | ✅ **Proven resolved** — pattern established, coverage is a linear improvement item |
| No saga/compensation in wizards | 🔵 **Intentional future gap** — known architecture, Phase 1057 tracking |
| Checkout static steps (no conditional skip) | 🔵 **Intentional future gap** — design inconsistency, UX improvement item |
| No wizard resume detection in frontend | 🔵 **Intentional future gap** — backend state exists; frontend resume UI is a feature addition |

---

## Fix Applied: `staffApi.ts` 401 Auto-Logout

**File:** `ihouse-ui/lib/staffApi.ts`

Added `performStaffLogout(reason)` function that clears the tab-scoped `sessionStorage` token and redirects to `/login` with a reason parameter. The `apiFetch` wrapper now calls this on `res.status === 401`.

**Design decisions:**
- Clears `sessionStorage` only (not `localStorage`) — preserves the admin's session in the parallel admin tab
- Only fires when a token is present — prevents redirect loops when the worker was already logged out
- 403 is explicitly NOT caught — correctly left to the calling component as a UI error
- Mirrors the `lib/api.ts` pattern exactly, adapted for the sessionStorage-scoped worker context

**Before:**
```typescript
if (!res.ok) throw new Error(`${res.status}`);
```

**After:**
```typescript
if (res.status === 401 && token) {
    performStaffLogout(`staffapi_401_${path.replace(/\//g, '_')}`);
    throw new Error('401');
}
if (!res.ok) throw new Error(`${res.status}`);
```

---

## Closure Detail: No Saga / Compensation Pattern

**Closure state: Intentional future gap — known architecture, not a bug-level fix for this audit pass**

The wizard step model (independent writes, no transaction coordinator) is a documented architectural choice. Backend resume state exists via `GET /tasks/{task_id}/cleaning-progress`. The correct fix (a compensation coordinator) is planned in Phase 1057. Implementing it in this audit pass would be premature and under-specified.

**Why not a bug:** On failure, workers retry the step — on-conflict upsert semantics make retries safe. No data is lost or corrupted. The gap is in structured UX guidance during recovery, not in data integrity.

---

## Closure Detail: Checkout Static Steps

**Closure state: Intentional future gap — design inconsistency, not a safety issue**

Checkout always includes `closing_meter` regardless of `electricity_enabled`. This is inconsistent with the check-in `getFlow()` pattern. Workers see an irrelevant step. Fix: read `chargeConfig` at checkout initialization and apply the same conditional skip logic. But this is a UX improvement, not a functional defect — workers can skip through the step without consequence.

**Not appropriate for this audit pass** — requires checkout flow redesign touching multiple components.

---

## Closure Detail: Frontend Wizard Resume Detection

**Closure state: Intentional future gap — backend capability exists, frontend feature is an addition**

`GET /tasks/{task_id}/cleaning-progress` is proven to exist with explicit resume support documented in its docstring. The frontend simply doesn't read this on wizard initialization to detect mid-progress state. Adding it requires a new initialization step in each wizard. Feature work, not audit defect.

---

## What Was Disproven

- **Owner visibility leak**: Disproven — confirmed in Sonia's result.
- **Settlement authorization gap**: Disproven in Group A Item 03 result.
