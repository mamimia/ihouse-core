> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 1058 Closed

**Date:** 2026-04-04
**Last commit:** `3e86fac` — Phase 1058 doc correction (reviewer/item mapping drift in Group B and C closure tables)
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## Current Phase

**Phase 1059 — Next (TBD)**

No work has started on Phase 1059 yet. The session ended immediately after Phase 1058 canonical documentation was fully closed and verified.

## Last Closed Phase

**Phase 1058 — Operational Audit Closure: PKA-Bridge Group B + Group C + Backend Authorization Hardening (CLOSED 2026-04-04)**

Full spec: `docs/archive/phases/phase-1058-spec.md`
ZIP: `releases/phase-zips/iHouse-Core-Docs-Phase-1058.zip`

### What was done in Phase 1058

1. **`admin_only_auth` FastAPI dependency** — `src/api/auth.py`. Reads JWT `role` claim via `get_identity()`. Any non-admin caller receives HTTP 403 `CAPABILITY_DENIED { required_role: admin, caller_role: <actual> }`. Dev-mode bypass with admin identity.

2. **All DLQ endpoints gated** — `src/api/dlq_router.py`: LIST, GET, POST /replay (3 endpoints) now require `Depends(admin_only_auth)`.

3. **All admin-namespace endpoints gated** — `src/api/admin_router.py`: summary, metrics, dlq-summary, health/providers, booking timeline, reconciliation, audit-log, integrations GET/PUT/test (11 endpoints) now require `Depends(admin_only_auth)`.

4. **Test contract corrections:**
   - `tests/test_dlq_e2e.py` — 18 calls: `tenant_id=TENANT` → `identity={"tenant_id": TENANT, "role": "admin"}`
   - `tests/test_admin_audit_log_contract.py` — endpoint helper updated to `identity=`; direct `write_audit_event()` calls retain `tenant_id=` (utility fn, not endpoint)
   - `tests/test_admin_properties_e2e.py` — admin router calls (Groups A–E) updated to `identity=`; properties_router calls (Group F) kept `tenant_id=`

5. **Audit result files corrected:**
   - `PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/evidence/result/06_sonia_result.md` — "Fully closed — both layers"
   - `PKA-Bridge/ACTIVATION/group_b_operational_product_surfaces/evidence/result/08_marco_result.md` — "Real residual risk, partially mitigated"

6. **PKA-Bridge Group B + Group C canonical closure tables** corrected (reviewer/item mapping drift was introduced in initial write and fixed in follow-up commit `3e86fac`).

### Final Group B closure state (06–10)

| Item | Reviewer | Final State |
|------|----------|-------------|
| 06 — Manager FULL_ACCESS / admin surface reachability | Sonia | ✅ Fully closed — frontend guard + backend `admin_only_auth` |
| 07 — Auth error handling, saga compensation, wizard state | Talia | ✅ Auth errors resolved; 🔵 saga/wizard resume/checkout-skip are intentional future gaps |
| 08 — Offline photo upload failure chain | Marco | ⚠️ Real residual risk, partially mitigated — photo bytes can be permanently lost |
| 09 — Deactivation auto-cleanup + session invalidation | Hana | ✅ Deactivation fixed; 🔵 session invalidation is confirmed future gap |
| 10 — Property readiness gate + cleaning completion | Claudia | ✅ Fully closed |

### Final Group C closure state (11–14)

| Item | Reviewer | Final State |
|------|----------|-------------|
| 11 — Owner portal financial data, PDF, visibility flags | Miriam | ✅ Mostly closed; 🔵 visibility flags/payout persistence/fee versioning are intentional future gaps |
| 12 — Financial lifecycle + deposit UNIQUE constraint | Victor | ✅ Fully closed |
| 13 — Storage bucket RLS + PII access model | Oren | ✅ Fully closed — all PII buckets private confirmed in live DB |
| 14 — Guest portal sections + self check-in + messaging | Yael | ✅ Mostly closed; 🔵 empty states + post-checkout are intentional future gaps |

### INV-1058-ADMIN-AUTH (locked)

All `/admin/*` and `/admin/dlq/*` endpoints require `role == 'admin'` at the backend layer. This invariant is canonical and must not be relaxed without an explicit phase that re-examines the access model.

---

## Test Status

**8,138 passed, 52 failed (all pre-existing), 22 skipped**

The 52 failures are pre-existing mock stubs — wave7 takeover, wave5/wave3 task enhancement, task model/router/system, guest portal, reconciliation auth. None were introduced by Phase 1058.

---

## Open Items (carried into Phase 1059)

These were explicitly deferred. Do not re-audit them unless the user reopens them.

| Item | Status |
|------|--------|
| Phase 1053 manual portal proof | Pending — deployed (`c2d2f55`), awaiting visual verification in live staging. Component: `ConversationThread` in `ihouse-ui/app/(public)/guest/[token]/page.tsx`. Root bug fixed: `.eq("booking_id")` vs old `.eq("booking_ref")` |
| Offline photo upload — full offline-first infra | 🔵 Future gap — Service Worker + IndexedDB. Not a current build. |
| Session invalidation on deactivation | 🔵 Future gap — auth-layer redesign (JWT blocklist / Redis revocation). Current deactivation blocks new login but live sessions run to JWT expiry. |
| `assigned_om_id` long-term ownership model | Open — currently routing scaffold only. Final ownership model deferred. |
| Host photo renders in guest portal (end-to-end) | Open — not blocking. |
| WhatsApp contact proof | Open — not blocking. |
| 52 pre-existing test mock failures | Tracked for repair in dedicated test hardening pass. |

---

## Planned Phases (queue, not yet started)

These were audited and defined in prior sessions. They are PLANNED only — no code written yet.

| Phase | Title | Status |
|-------|-------|--------|
| 1054 | `live-system.md` catch-up (docs only) | PLANNED |
| 1055 | Task cancellation scope hardening — include ACKNOWLEDGED tasks on booking cancel | PLANNED |
| 1056 | Write-gate alignment: check-in/check-out through `apply_envelope` | PLANNED (highest effort) |
| 1057 | Settlement finalize atomicity hardening — try/except compensation + repair endpoint | PLANNED |

---

## Key Files

| File | Role |
|------|------|
| `src/api/auth.py` | JWT + `admin_only_auth` dependency |
| `src/api/dlq_router.py` | DLQ endpoints (admin-gated) |
| `src/api/admin_router.py` | All admin-namespace endpoints (admin-gated) |
| `src/api/guest_portal_router.py` | Guest portal backend (Phase 1053 messaging bug fixed) |
| `ihouse-ui/app/(public)/guest/[token]/page.tsx` | Guest portal frontend (Phase 1053 `ConversationThread` added) |
| `docs/core/current-snapshot.md` | Current system state |
| `docs/core/work-context.md` | Working memory / active constraints |
| `docs/core/phase-timeline.md` | Full history — append only |
| `docs/archive/phases/phase-1058-spec.md` | Phase 1058 full spec |

---

## How to start the next session

1. Read `docs/core/BOOT.md`
2. Read `docs/core/current-snapshot.md`
3. Read `docs/core/work-context.md`
4. Check git log: `git log --oneline -5`
5. State: current phase (1059), last closed (1058), and ask the user for the next objective.

Do not assume Phase 1059 scope — wait for user direction.
