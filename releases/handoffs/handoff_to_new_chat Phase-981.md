> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 981 → Phase 982

**Date:** 2026-03-29
**From:** Phase 981 — Test Suite Full Green
**Into:** Phase 982 — Next (TBD)

---

## Current Phase

**Phase 982** — Active. No objective set yet.

## Last Closed Phase

**Phase 981** — Test Suite Full Green.
Achieved **7,975 passed, 0 failed, 22 skipped** — first fully-green backend test suite in the project's history.

---

## What Was Accomplished This Session

### Phase 979 (prior session)
Worker Mobile Experience Hardening:
- Full Guest Dossier system: `/guests/{guest_id}` backend + tabbed frontend (Current Stay, Activity, Contact)
- Worker check-in task lifecycle self-healing: orphaned ACKNOWLEDGED tasks auto-completed via `forceCompleteTask()` when booking already `checked_in`
- MobileStaffShell horizontal gutter (`paddingInline: var(--space-4)`)
- LiveCountdown human-readable tiered format: `>48h→13d`, `24-48h→1d 6h`, `<24h→18h 20m`
- Worker Home broken modal removed — Next Up cards navigate to role-specific flows directly
- Breadcrumb navigation leak suppressed on all mobile staff routes

### Phase 981 (this session) — Test Suite Full Green
Resolved all 95 pre-existing test failures. Root causes:
1. Phase 862 signup contract: identity-only (no `tenant_id`/`role` in response) → `test_auth_flow_e2e.py`
2. Provider listing now returns `[{provider, email}]` dicts → `test_identity_linking_proof.py`
3. Guest portal enriched lookup chain (queries `booking_state` + `cash_deposits`) → `test_guest_portal_token.py`
4. Expired token returns generic `TOKEN_INVALID` → `test_guest_portal_token.py`
5. Whitespace property_id triggers auto-gen 201 → `test_properties_router_contract.py`
6. `<PasswordInput>` component vs raw `type="password"` → `test_invite_flow_e2e.py`
7. AdminNav group codes (`ops`, `finance`) vs display labels → `test_phases_525_541.py`
8. Login page moved to `(auth)` route group → `test_e2e_smoke.py`
9. Empty role string returns 422 (strict validation) → `test_jwt_role_enforcement.py`
10. Bookings router `SUPABASE_URL` injection → `test_audit_events_contract.py`
11. Name-based table routing in checkout deposit tests → `test_wave6_checkout_deposit_contract.py`

---

## Deployment Status

| Component | Platform | Status |
|-----------|----------|--------|
| Backend | Railway | ✅ Live |
| Frontend | Vercel (`domaniqo-staging.vercel.app`) | ✅ Live |
| Database | Supabase (`reykggmlcehswrxjviup`) | ✅ Connected |

---

## What to Do Next (Phase 982)

The system is now at a high-quality baseline. Possible next directions (ask user to confirm priority):

### Option A — Operational Gaps (D-series)
The worker check-in flow has known gaps from the Phase D audit:
- **D-1**: Passport capture: `DEV_PASSPORT_BYPASS=true` — needs camera + storage wiring
- **D-2**: Deposit handling: no persistence/audit trail for cash deposits collected
- **D-5**: Property state not updated to `Occupied` on check-in completion
- **D-6**: No audit event written on check-in completion
- **D-7**: Check-out flow not built (4-step flow entirely missing)

### Option B — Staging Verification
With Full Green suite, run a final E2E staging proof across all three worker roles:
- Check-in worker: complete flow end-to-end with real task lifecycle
- Cleaning worker: assign → acknowledge → complete
- Checkout worker: inspection → deposit resolution → complete

### Option C — Next Feature Wave
Refer to `docs/core/roadmap.md` for planned phases beyond 981.

---

## Key Files for Next Session

| File | Purpose |
|------|---------|
| `docs/core/BOOT.md` | Session startup protocol — read first |
| `docs/core/current-snapshot.md` | Full system status (Phase 982 active) |
| `docs/core/work-context.md` | Current objective + invariants |
| `docs/core/roadmap.md` | Planned phases |
| `ihouse-ui/app/(worker)/ops/checkin/page.tsx` | Worker check-in flow |
| `src/api/booking_checkin_router.py` | Backend check-in endpoints |
| `src/api/guest_router.py` | Guest Dossier endpoint |
| `ihouse-ui/app/guests/[id]/page.tsx` | Guest Dossier frontend |

---

## Test Suite State

```
7,975 passed
    0 failed   ← FULL GREEN
   22 skipped  ← all legitimate (staging-only / live-Supabase / BASE_URL required)
```

The 22 skips are correct. They run in staging CI. No action needed.

---

## Invariants (Never Change)

- `apply_envelope` is sole write authority — no adapter touches `booking_state` directly
- `event_log` is append-only — no updates, no deletes
- `booking_id = "{source}_{reservation_ref}"` — deterministic, normalized (Phase 68)
- `tenant_id` from verified JWT `sub` only — never from request body
- `booking_state` is read model ONLY — no financial calculations
- CRITICAL_ACK_SLA_MINUTES = 5 (locked)
- Phase 862: `/auth/signup` is identity-only — no tenant provisioning, no `tenant_id`/`role` in response
