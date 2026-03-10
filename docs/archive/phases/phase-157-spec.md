# Phase 157 — Worker Task UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** ~4120 passing (unchanged)

## Goal

Build the Task Center Next.js screens: a task list page with filters and a task detail page with acknowledge/complete actions. The first interactive worker-facing UI surface.

## Deliverables

### New Files
- `ihouse-ui/app/tasks/page.tsx` — Task Center list: filter by status/kind/property; task cards showing priority colour, due date, worker role, status chip; links to task detail
- `ihouse-ui/app/tasks/[id]/page.tsx` — Task Detail: full task view with acknowledge / complete / cancel buttons; notes field on complete; SLA time remaining indicator

### Modified Files
- `ihouse-ui/lib/api.ts` — `getTasks()`, `getTask(id)`, `patchTaskStatus()` API methods added
- `ihouse-ui/app/layout.tsx` — Tasks nav link (✓) confirmed present

## Key Design Decisions
- Task list calls `GET /tasks` with query params; detail calls `GET /tasks/{id}`
- Status transitions call `PATCH /tasks/{id}/status` — enforces `VALID_TASK_TRANSITIONS` server-side
- Priority colours: CRITICAL=red, HIGH=orange, MEDIUM=yellow, LOW=grey
- No Supabase client in any component — all data via FastAPI ✅

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- Task status writes go through the API transition endpoint (not direct DB) ✅
