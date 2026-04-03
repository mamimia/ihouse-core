# Group A Audit Result: Nadia — Chief Product Integrator

**Audit date:** 2026-04-04
**Auditor:** Antigravity (session 627e84a9)

---

## Verdict: NOT REAL

The core integration concern — that check-in and checkout deposit flows may write and read from different tables, causing data to not connect — is **disproven** by the current code.

---

## Evidence Basis

### Deposit table connectivity (primary concern)

**Code evidence:**
- `checkin_settlement_router.py` line 331: `db.table("cash_deposits").insert(...)`
- `deposit_settlement_router.py` line 116: `db.table("cash_deposits").insert(...)`
- `checkout_settlement_router.py` lines 1194–1205: `UPDATE cash_deposits ... WHERE booking_id=... AND tenant_id=...`

All three routers use `cash_deposits` as the single table. The join key is `booking_id + tenant_id`. Money collected at check-in is locatable and settleable at checkout. The integration path is intact.

### Token isolation (api.ts vs staffApi.ts)

**Confirmed correct.** `api.ts` reads from localStorage. `staffApi.ts` uses `getTabToken()` which reads sessionStorage first (Act As isolation), falling back to localStorage. Explicit guard comment in `staffApi.ts`: "NEVER mix with admin api.ts." This is a clean, correctly implemented boundary.

### 401/403 distinction

**Confirmed correct.** `api.ts` auto-logs out on 401 only, not 403. 403 errors (`CAPABILITY_DENIED`, `PREVIEW_READ_ONLY`) display error state — correct behavior.

### Envelope standard

**Confirmed correct.** `envelope.py` defines `ok()` and `err()` helpers. All routers use them. Frontend `api.ts` unwraps `{ok, data}` uniformly.

### Financial response key mismatch hypothesis

**Status: Unverified hypothesis from an old SYSTEM_MAP note.** No current code evidence supports it. The backend uses `ok(data=...)` consistently. This claim originated from a pre-code-read concern and was never validated against the actual frontend Page component. It is **not confirmed as a real issue** and is not being treated as one.

### staffApi.ts type coverage gap

**Acknowledged but not actionable.** `staffApi.ts` has fewer typed methods than `api.ts`. This is a code quality concern, not a functional correctness issue. Worker-facing flows function — they are just less type-safe. No canonical change required.

---

## Fix Needed

**No fix triggered.**

---

## Why Not Fixed

The primary integration concern is disproven. Remaining items (key mismatch hypothesis, staffApi.ts type coverage) are either unconfirmed or quality-level concerns that don't require canonical changes in this audit pass.
