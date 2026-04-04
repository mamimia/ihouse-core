> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff — Phase 1067 (Session End 2026-04-04)

**Written:** 2026-04-04T23:59 ICT  
**Last Closed Phase:** Phase 1067 — Guest Checkout Wizard: Completion Fix + Property Name + Copy Polish  
**Current Phase:** Phase 1068 — Next (TBD)  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`  
**Supabase project:** `reykggmlcehswrxjviup`

---

## What was completed this session

### Guest Self-Checkout Flow — Full E2E (Phases 1063–1067)

The complete guest-side self-checkout flow is now working end-to-end and proven on
the real Amuna Villa case (ICAL-36ff7d9905e0, original checkout Apr 7, approved early
checkout Apr 5).

| Phase | Delivered |
|-------|-----------|
| 1063 | Worker checkout wizard: dynamic `computeStepFlow(baseline)` — 3–5 steps based on property config |
| 1064 | Guest portal: empty state guards across all sections. No more floating orphaned headers |
| 1065 | Guest portal: Early Check-Out request CTA + Self Check-Out CTA (24h window). `GET /guest/{token}/checkout-status` |
| 1066 | Three-bug fix for "Link unavailable": `useParams()`, DB migration (3 missing columns), booking lookup key |
| 1067 | Completion fix: `ready` step now maps to `confirm_departure` backend key. Property name fix. `SummaryScreen` added |

### Operational / Admin Early Checkout (pre-existing, confirmed working)
- Admin early checkout approval pipeline: ✅ Already existed (Phase 998)
- Guest early checkout _request_ (Phase 1065): ✅ Now exists

### Deferred Items Documented (not bugs, intentional deferrals)

| Item | Status | Location |
|------|--------|----------|
| Item 9 — Guest Pre-Arrival Form | Deferred | `docs/future/guest-pre-arrival-form.md` |
| Item 10 — Data Retention Policy | Audit complete, enforcement deferred | `docs/future/data-retention-policy-audit.md` |

---

## Current system state

### Staging (live, verified)

| Surface | URL / Platform | State |
|---------|----------------|-------|
| Frontend | `https://domaniqo-staging.vercel.app` (Vercel) | ✅ Live (Phase 1067 deployed) |
| Backend | Railway — `checkpoint/supabase-single-write-20260305-1747` | ✅ Live (Phase 1067 deployed) |
| Database | Supabase `reykggmlcehswrxjviup` | ✅ Connected. DB migration applied. |

### Test state
8,138 passed, 52 failed (pre-existing mock stubs — not introduced by this session), 22 skipped. TypeScript 0 errors.

---

## Open items (not bugs — documented future work)

| Item | Notes |
|------|-------|
| Phase 1053 — manual portal thread view proof | Deployed, awaiting human confirmation |
| `assigned_om_id` long-term ownership model | Routing scaffold only. Final ownership model deferred |
| Host photo end-to-end portal render proof | Photo upload built, render proof OPEN |
| Saga/compensation model for checkout wizard | Check-in covered, checkout wizard cross-step rollback OPEN |
| Item 9 — Guest Pre-Arrival Form | DEFERRED — iCal-first constraint. See `docs/future/guest-pre-arrival-form.md` |
| Item 10 — Data Retention Policy | DEFERRED — Thailand PDPA + TM.30 legal review needed. See `docs/future/data-retention-policy-audit.md` |
| 52 pre-existing test failures | Legacy mock mismatches. Tracked for dedicated test hardening pass |

---

## Key files changed this session

### Backend
- `src/api/guest_portal_router.py` — `GET /guest/{token}/checkout-status`, early checkout request endpoint
- `src/api/guest_checkout_router.py` — property name fix (4 locations: `display_name` not `name`), step completion logic

### Frontend
- `ihouse-ui/app/(public)/guest/[token]/page.tsx` — Self Check-Out CTA, Early Check-Out request, `useParams()` fix, empty state guards
- `ihouse-ui/app/(public)/guest-checkout/[token]/page.tsx` — `ready` → `confirm_departure` step mapping, `SummaryScreen`, disabled buttons during submit, `useParams()` fix

### DB Migration
- `add_checkout_portal_missing_columns` — added `deposit_status`, `opening_meter`, `property_id` to `guest_checkout` table

### Documentation
- `docs/future/guest-pre-arrival-form.md` — Item 9 spec (deferred)
- `docs/future/data-retention-policy-audit.md` — Item 10 full audit (deferred)
- `docs/archive/improvements/future-improvements.md` — both deferred entries added
- `docs/archive/phases/phase-1059-spec.md` through `phase-1067-spec.md` — all archived
- `docs/core/phase-timeline.md` — Phases 1059, 1063–1067 + Items 9 & 10 appended
- `docs/core/construction-log.md` — same closures appended
- `docs/core/current-snapshot.md` — Current Phase → 1068, Last Closed → 1067
- `docs/core/work-context.md` — phase pointers updated, sequence extended

---

## What to do next in a new chat

### What to read first
1. `docs/core/BOOT.md` — mandatory first read
2. `docs/core/current-snapshot.md` — phase state, invariants
3. `docs/core/work-context.md` — open items, deferred registry

### Reasonable next directions (not yet decided)

| Option | Notes |
|--------|-------|
| Item 11 — next product item | Open to user direction |
| Guest portal proof pass | Verify Phase 1053 thread view + host photo |
| Saga/compensation model | Checkout wizard wizard_draft, multi-device resume |
| Test hardening | 52 pre-existing mock failures — dedicated pass |
| Property Settings update | Guest portal checkout status data needs some properties to be configured |

---

## Key invariants — do not change

- `apply_envelope` is the single write authority — no adapter writes `booking_state` directly
- `event_log` is append-only — no updates, no deletes ever
- `booking_state` is a read model ONLY — must NEVER contain financial calculations
- All financial read endpoints query `booking_financial_facts` ONLY — never `booking_state`
- `portal_host_*` columns on `properties` are presentation-only — never routing, audit, or owner truth
- `sender_id` in `guest_chat_messages` = the real user UUID, NEVER `tenant_id`
- No internal identifier (property code, user UUID, etc.) ever appears on any guest-facing surface
- INV-STORAGE-01: Guest identity docs — 90-day auto-delete after checkout. Staff employment docs — retained while employed + 12 months, never auto-deleted.
- INV-1058-ADMIN-AUTH: All admin-namespace and DLQ endpoints require `role=admin` — enforced by `admin_only_auth` FastAPI dependency

---

## Anti-Gravity workspace note (important)

> If Anti-Gravity becomes silent/unresponsive inside this repo, check `.git/config` for `extensions.worktreeconfig=true`.
> Fix: `git config --local --unset extensions.worktreeconfig`
> This was the root cause of the 2026-04-02 workspace freeze.
