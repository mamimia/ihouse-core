# Phase 396 — Property Admin Approval Dashboard

Category: Admin / Property Management
Depends on: Phase 395 (Property Onboarding QuickStart)

## Summary

Admin endpoints and UI for managing properties submitted through the onboarding wizard (Phase 395). Properties flow through a lifecycle: pending → approved/rejected, approved → archived. All state transitions are audit-logged.

## Backend — property_admin_router.py

5 new endpoints:

| Method | Path | Description |
|--------|------|-------------|
| GET | /admin/properties | List all properties with status filters, search, pagination |
| GET | /admin/properties/{id} | Property detail with channel_map entries |
| POST | /admin/properties/{id}/approve | pending → approved (sets approved_at, approved_by) |
| POST | /admin/properties/{id}/reject | pending → rejected |
| POST | /admin/properties/{id}/archive | approved → archived (sets archived_at, archived_by) |

All endpoints:
- JWT auth required (tenant_id from `sub` claim)
- Tenant-scoped queries
- Invalid state transitions return 409
- Missing properties return 404
- Audit-logged to admin_audit_log

Registered in main.py after onboarding_router.

## Frontend — admin/properties/page.tsx

- Status filter cards (All / Pending / Approved / Rejected / Archived) with live counts
- Property list table: name, city, type, platform, status badge, created date, capacity
- Inline approve/reject/archive buttons with loading state
- Toast notifications on success/failure
- Empty state with onboarding wizard reference
- Follows existing admin page patterns (SectionCard, Chip, design tokens)

## Tests — test_property_admin.py

21 contract tests across 5 test classes:
- TestListProperties (6 tests): empty list, populated list, invalid status filter, valid filter, status summary, dev-tenant
- TestPropertyDetail (3 tests): with channels, 404, lifecycle fields
- TestApproveProperty (5 tests): pending→approved, already approved 409, rejected 409, unknown 404, detail object
- TestRejectProperty (3 tests): pending→rejected, approved 409, unknown 404
- TestArchiveProperty (4 tests): approved→archived, pending 409, already archived 409, unknown 404

## Verification

- pytest: 21/21 passed
- tsc --noEmit: 0 errors
- No new backend regressions

## Files

### New
- src/api/property_admin_router.py
- tests/test_property_admin.py
- ihouse-ui/app/(app)/admin/properties/page.tsx

### Modified
- src/main.py (router registration)
- docs/core/phase-timeline.md
- docs/core/construction-log.md
- docs/core/current-snapshot.md
- docs/core/work-context.md
