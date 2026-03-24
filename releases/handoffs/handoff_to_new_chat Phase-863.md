> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff to New Chat — Phase 863 Closed / Phase 864 Active

**Date:** 2026-03-25
**Time (local):** 04:16 +07:00
**Branch:** `checkpoint/supabase-single-write-20260305-1747`
**Last commit:** `f236959`

---

## Current System State

| Field | Value |
|-------|-------|
| **Current Phase** | Phase 864 — not yet started |
| **Last Closed Phase** | Phase 863 — Media Storage Remediation + Canonical Retention Architecture |
| **System Status** | Stable. Tests: **7933 passed, 50 failed (pre-existing), 22 skipped**. 0 new failures introduced this session. |
| **Deployment** | Railway (auto via git push) ✅ · Vercel staging `domaniqo-staging.vercel.app` ✅ |
| **Build** | Next.js: 0 TypeScript errors |

---

## What Was Done This Session (summary)

### 1. Phase 863 Closed — Media Storage Remediation
Full remediation of 4 live storage violations:
- **Staff PII in public bucket** → migrated to `staff-documents` (private)
- **29 misplaced staff files** (21 onboarding, 8 avatars) → migrated to `staff-documents`
- **12 orphaned files** from deleted properties → deleted
- **32 staging temp files** → deleted
- **5 DB references** in `tenant_permissions` updated to signed URLs
- `cleaning-photos` bucket flipped to private
- `staff_onboarding_router.py` routing fixed: always writes to `staff-documents` (INV-MEDIA-02)
- `properties_router.py`: property delete now cascades to Storage cleanup
- `storage-retention.md`, `blast-constitution.md`, `gemini.md` updated with canonical invariants

### 2. Admin Tasks Page Regression Fixed (unplanned)
Commit `2d2b94a` had accidentally overwritten the admin task board (`/tasks`) with the `WorkerTaskCard` flat layout while intending to only update worker pages.

**Fix (commit `f236959`):**
- Restored `DayPropertyCard` (dense grouped board) from git history `133d75c`
- Dual-path render: `staffRole === null` → admin board; `staffRole` set → WorkerTaskCard
- Admin gets 4 tabs (All / Pending / In Progress / Done)
- Workers keep 2 tabs (Pending / Done) + WorkerTaskCard unchanged
- All `/ops/*` worker pages untouched

---

## Phase 863 Closure Artifacts Produced

| Artifact | Location | Status |
|----------|----------|--------|
| Phase spec | `docs/archive/phases/phase-863-spec.md` | ✅ |
| Phase ZIP | `releases/phase-zips/iHouse-Core-Docs-Phase-863.zip` | ✅ |
| Phase timeline | `docs/core/phase-timeline.md` (appended) | ✅ |
| Construction log | `docs/core/construction-log.md` (appended) | ✅ |
| Current snapshot | `docs/core/current-snapshot.md` — Phase 864 active | ✅ |
| Work context | `docs/core/work-context.md` — INV-MEDIA + INV-STORAGE added | ✅ |
| Git push | `c5a9f39` (Phase 863 closure commit) + `f236959` (admin tasks fix) | ✅ |

---

## Key Canonical Invariants Now Active

| ID | Rule |
|----|------|
| INV-MEDIA-01 | No binary data in Postgres. All files in Supabase Storage only. |
| INV-MEDIA-02 | Staff files always go to `staff-documents` (private). Never `property-photos` (public). Enforced in `staff_onboarding_router.py`. |
| INV-STORAGE-01 | Guest PII: 90-day auto-delete after checkout. Staff employment docs: retained while employed + 12 months, never auto-deleted. |
| INV-STORAGE-02 | `cleaning-photos` is private. Signed URLs only. |
| INV-STORAGE-03 | Archive verification required before live `event_log` deletion. |
| Storage cascade | `DELETE /properties/{id}` removes all objects under `property-photos/{id}/` in Storage. |

---

## Storage Bucket State (Final)

| Bucket | Public | Files | Notes |
|--------|--------|-------|-------|
| `property-photos` | ✅ Public | 15 | Only public bucket. Property marketing/reference photos. |
| `staff-documents` | 🔒 Private | 31 | Staff PII, onboarding, avatars. Signed URLs. |
| `cleaning-photos` | 🔒 Private | 0 | Flipped to private this session. |
| `guest-uploads` | 🔒 Private | 0 | Future guest identity docs. |
| `pii-documents` | 🔒 Private | 0 | Future check-in PII scans. |
| `exports` | 🔒 Private | 0 | Future audit exports. |

---

## Key Files Changed This Session

| File | Change |
|------|--------|
| `src/api/staff_onboarding_router.py` | Upload target: `property-photos` → `staff-documents`; returns signed URL |
| `src/api/properties_router.py` | Property delete cascades to Storage cleanup |
| `ihouse-ui/app/(app)/tasks/page.tsx` | Dual-path: admin board restored (DayPropertyCard) + worker path kept (WorkerTaskCard) |
| `.agent/architecture/storage-retention.md` | Canonical storage rules finalized |
| `.agent/system/blast-constitution.md` | INV-STORAGE-01 corrected |
| `.agent/gemini.md` | Section 13 updated |

---

## Deferred Items (Managed Open Items)

| ID | Item | Status |
|----|------|--------|
| 617 | Wire Form → Checkin Router | 🟡 Deferred — requires live booking flow |
| 618 | Wire QR → Checkin Response | 🟡 Deferred — same as 617 |
| 857-F1 | Staff photo bucket migration | ✅ Fully resolved Phase 863 |
| 857-F2 | Email click-through activation proof | 🟡 Pending — requires human inbox |
| 857-F3 | Pipeline A runtime proof | ✅ Resolved |
| 859-F1 | Property URL extraction (scraping) | 🟡 Stub — requires OTA API keys |
| 50 pre-existing backend test failures | Not introduced this session | 🟡 Known — do not fix without explicit instruction |

---

## Next Recommended Actions (Phase 864)

Phase 864 has not been scoped yet. The system is in a stable, clean state.

Suggested areas:
1. Define and scope Phase 864 with the user
2. Address any of the deferred items above if the user prioritizes them
3. The admin tasks regression is fixed — next worker/admin UI work can continue safely

---

## How to Start the Next Chat

1. Read `docs/core/BOOT.md` (required — first action)
2. Read `docs/core/current-snapshot.md`
3. Read `docs/core/work-context.md`
4. Read tail of `docs/core/phase-timeline.md` (Phase 862–863 sections)
5. State: "Current Phase: 864. Last Closed: Phase 863. System stable."
6. Ask the user what they want to tackle in Phase 864.
