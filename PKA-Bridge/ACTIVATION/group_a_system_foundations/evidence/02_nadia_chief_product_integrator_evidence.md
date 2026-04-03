# Evidence File: Nadia — Chief Product Integrator

**Paired memo:** `02_nadia_chief_product_integrator.md`
**Evidence status:** Key claims now directly proven or revised; some still require frontend trace

---

## Claim 1: Two deposit routers may target different tables

**Status:** REVISED — BOTH target the same table (cash_deposits)

**Evidence basis:**
- File: `src/api/checkin_settlement_router.py`, line 331: `db.table("cash_deposits").insert(cash_deposit_row)`
- File: `src/api/deposit_settlement_router.py`, line 116: `db.table("cash_deposits").insert(row)`
- File: `src/api/checkout_settlement_router.py`, lines 1194-1205: updates `cash_deposits` status on finalize

**What was observed:** All three routers operate on the same `cash_deposits` table. The data DOES connect — checkout settlement reads from the same table that check-in writes to. The integration risk is lower than the memo hypothesized.

**Remaining risk:** Dual-recording. If both the check-in wizard (Phase 964) and the manual deposit endpoint (Phase 687) are called for the same booking, two records could exist. The checkout settlement would find both (or the first).

**Confidence:** HIGH that they share the same table. The "data won't connect" hypothesis from the memo is DISPROVEN.

**Uncertainty:** Does the frontend ever call deposit_settlement_router during a standard check-in flow? Or is it exclusively for admin/manual operations?

**Follow-up check:** Read the check-in wizard frontend code (step 5) to see which endpoint URL it calls.

---

## Claim 2: api.ts has 401/403 distinction

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/api.ts` — agent report confirms: auto-logout on 401 only, NOT on 403. 403 errors (CAPABILITY_DENIED, PREVIEW_READ_ONLY) do not trigger logout.

**What was observed:** Code explicitly distinguishes 401 (auth failure → logout) from 403 (authorization denial → show error). This is architecturally correct.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 3: Token isolation between api.ts and staffApi.ts is real

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/lib/api.ts` — reads from localStorage
- File: `ihouse-ui/lib/staffApi.ts` — `getTabToken()` reads sessionStorage first for Act As isolation, falls back to localStorage
- staffApi.ts contains explicit comment guard: "NEVER mix with admin api.ts"

**What was observed:** Two separate modules with different token retrieval strategies. Act As sessions use sessionStorage only, preventing admin localStorage contamination.

**Confidence:** HIGH

**Uncertainty:** None. Pattern is unambiguous.

---

## Claim 4: Envelope standard is consistently applied

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/envelope.py` — defines `ok(data, status, **meta)` and `err(code, message, status, **extra)` helpers
- All routers import and use these helpers for response formatting
- File: `ihouse-ui/lib/api.ts` — automatic unwrapping of `{ok, data}` envelope

**What was observed:** Backend produces `{ok: true, data: ...}` or `{ok: false, error: {code, message}}`. Frontend unwraps uniformly. The contract is consistent.

**Confidence:** HIGH

**Uncertainty:** None for the standard itself. Some older routers might not use the helpers — but the pattern is pervasive.

---

## Claim 5: Financial router response key mismatch

**Status:** HYPOTHESIS — not yet verified against frontend

**Evidence basis:**
- The memo cited SYSTEM_MAP's concern that `/financial/statements` returns `{items: [...]}` but frontend destructures `response.data.line_items`
- File: `src/api/financial_router.py` — confirmed to use `ok(data=...)` envelope
- Frontend financial page code not yet read

**What was observed:** The backend follows the envelope standard. The specific field name inside the data payload needs frontend-to-backend trace.

**Confidence:** LOW — this is still an unverified hypothesis from the SYSTEM_MAP

**Uncertainty:** Need to read the frontend `/financial/statements` page component and match its field access against the backend response shape.

**Follow-up check:** Read `ihouse-ui/app/(app)/financial/statements/page.tsx` and compare field names with the backend response.

---

## Claim 6: staffApi.ts has fewer typed methods, creating contract risk

**Status:** STRONGLY INDICATED

**Evidence basis:**
- File: `ihouse-ui/lib/api.ts` — 40+ typed API methods with TypeScript interfaces
- File: `ihouse-ui/lib/staffApi.ts` — agent report confirms fewer typed wrapper methods

**What was observed:** api.ts is significantly more mature in type coverage. staffApi.ts relies more on raw fetch calls with less typing.

**Confidence:** MEDIUM — the pattern is indicated by the agent report, but exact method count comparison not done

**Uncertainty:** Exact count of typed vs. untyped methods in staffApi.ts.

---

## Claim 7: No integration test layer visible

**Status:** HYPOTHESIS — partial search only

**Evidence basis:**
- No `tests/integration/` directory or similar observed in the agent explorations
- The claimed 7,765 tests are likely unit tests (stated as CLAIMED in SYSTEM_MAP)

**What was observed:** No integration test files were encountered during exploration. However, the search was not exhaustive — tests could exist in a different directory structure.

**Confidence:** LOW

**Uncertainty:** Test directory structure not fully explored.

**Follow-up check:** `find ihouse-core/ -name "*integration*" -o -name "*e2e*"` to check.
