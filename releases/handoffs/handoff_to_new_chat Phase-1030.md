> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff to New Chat — Phase 1030 (In Progress)

**Date:** 2026-03-31
**Last Commit:** `7732ab4` on branch `checkpoint/supabase-single-write-20260305-1747`
**Current Phase:** 1030 — Task Lifecycle & Assignment Hardening
**Last Closed Phase:** 1029 — Default Worker Task Filter

---

## Context

Phase 1030 was opened to harden the Primary/Backup worker assignment model. All code changes are complete and deployed. Staging proofs are partially complete — the admin pending view was confirmed, but the baton-transfer, promotion banner, backfill, and amendment healing proofs were blocked by a terminal/network issue in the previous session.

**Do not re-open old code discussions. Resume from staging proofs.**

---

## What Was Done This Session (Code Complete)

All code changes below are committed and auto-deployed to Railway.

| File | Change |
|------|--------|
| `src/tasks/task_writer.py` | Amendment reschedule healing — unassigned tasks inherit Priority 1 worker on date shift |
| `src/tasks/task_router.py` | Ad-hoc cleaning `POST /tasks/cleaning/adhoc` — `ORDER BY priority ASC` ensures Primary selected over Backup |
| `src/api/permissions_router.py` | Baton-transfer is lane-aware (filters by `worker_roles`); promotion notice writes directly to `tenant_permissions.comm_preference` JSONB (dead RPC removed) |
| `src/api/worker_router.py` | Default status filter excludes COMPLETED + CANCELED (not just CANCELED) |
| `src/api/early_checkout_router.py` | Early-checkout rescheduling heals unassigned CLEANING tasks to current Primary |
| `tests/test_worker_router_contract.py` | Regression test A8: default GET /worker/tasks excludes COMPLETED and CANCELED |
| `scripts/cleanup_probe_tasks.sql` | Staging hygiene — deletes ZTEST- prefixed rows |

---

## What Was Staging-Proven

| Item | Evidence |
|------|----------|
| ✅ Admin Pending view excludes COMPLETED tasks | Browser recording `admin_pending_view_proof_1774937997797.webp`. Pending tab shows only PENDING/ACKNOWLEDGED. Done tab shows COMPLETED. Segregation confirmed. |

---

## What Is NOT Yet Staging-Proven (Next Session Priority)

Execute these in order. Each is a browser or API proof, not a code change.

### 1. Lane-aware baton-transfer
- Find a property with one cleaner at priority=1 (Primary) and another at priority=2 (Backup)
- Remove the Primary via the admin UI Manage Staff → Role & Assignment → remove from property
- Check: PENDING tasks on that property now show the Backup as `assigned_to`
- Check: ACKNOWLEDGED tasks are untouched
- Test task ID convention: `ZTEST-baton-tf-001`

### 2. Worker promotion banner
- After baton-transfer above: log in as the newly promoted Backup worker
- Confirm the promotion banner is visible on the worker home screen
- Screenshot the banner
- Dismiss it and confirm it is gone

### 3. `POST /staff/assignments` backfill
- Assign a new worker to a property that already has future PENDING CLEANING tasks
- Confirm in the DB (or via `/worker/tasks`) that those tasks now show `assigned_to = new_worker_id`
- This validates INV-1011 in the backfill direction

### 4. Amendment reschedule healing (smoke test)
- Trigger a booking amendment on a property that has an **unassigned** PENDING CLEANING task
- Confirm the rescheduled task is now `assigned_to = Primary cleaner`
- Use the Bookings admin UI → amend date → check tasks

### 5. Ad-hoc cleaning Primary selection (smoke test)
- Create an ad-hoc cleaning via admin Tasks page → "Add Cleaning"
- For a property that has a Primary and Backup cleaner
- Confirm the created task's `assigned_to` in DB matches the Primary (priority=1), not the Backup

---

## Staging Topology

| Component | URL |
|-----------|-----|
| Frontend | `https://domaniqo-staging.vercel.app` |
| Backend | `https://ihouse-core-production.up.railway.app` |
| DB | Supabase project `reykggmlcehswrxjviup` |

**Deploy rules:**
- Backend: `git push origin HEAD:checkpoint/supabase-single-write-20260305-1747` (auto-deploys)
- Frontend: `cd ihouse-ui && npx vercel --prod --yes` (manual CLI only)

---

## Technical Blocker Note

In the previous session, direct `curl` and `supabase-py` calls to Supabase REST started hanging (16+ minutes). Per BOOT.md tool pivot rule:
- Do NOT retry curl to Supabase as the proof method
- Use **browser automation** (browser subagent on the staging UI) as the primary proof method
- Use `curl --max-time 10` with an explicit timeout if API calls are needed
- Use Supabase Dashboard SQL Editor for any DB inspection that requires direct queries

---

## Phase 1030 Closure Checklist (What's Still Needed to Close)

- [ ] Complete the 5 staging proofs above
- [ ] Create `docs/archive/phases/phase-1030-spec.md`
- [ ] Append to `docs/core/phase-timeline.md`
- [ ] Update `docs/core/current-snapshot.md`
- [ ] Update `docs/core/work-context.md` (set Last Closed Phase = 1030)
- [ ] Create `releases/phase-zips/iHouse-Core-Docs-Phase-1030.zip`
- [ ] Git commit + push all closure artifacts

---

## Key Invariants Added This Phase

- **INV-1010 (extended):** All CLEANING task creation paths (auto, early-checkout, amendment, ad-hoc) must resolve the Primary cleaner and assign if available. Silent `assigned_to = NULL` is a bug, not a valid state.
- **INV-1011 (extended):** Assignment healing is required in all task rescheduling paths (early-checkout ✅, amendment reschedule ✅).
- **INV-1012 (new):** Baton-transfer is lane-aware. Backup promotion must match the departing Primary's `worker_roles` lane. A checkout worker cannot inherit a cleaning task.
