# Phase 169 — Admin Settings UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 15 contract tests  
**Total after phase:** 4420 passing

## Goal

Build the Admin Settings Next.js screen and add the `PATCH /admin/registry/providers/{provider}` endpoint for live provider capability toggling.

## Deliverables

### New Files
- `ihouse-ui/app/admin/page.tsx` — Admin Settings page: (1) Provider Registry section — live toggle for `supports_api_write` and `supports_ical_push`, rate limit and tier display, auth_method badge; (2) User Permissions section — list of users with role chips, grant/revoke capability buttons; (3) DLQ alert section — pending count with link to DLQ inspector
- `tests/test_admin_settings_contract.py` — 15 contract tests

### Modified Files
- `src/api/capability_registry_router.py` — `PATCH /admin/registry/providers/{provider}` added: partial update (no tier required), validates auth_method + tier (optional) + boolean fields + rate_limit_per_min. 404 if provider not registered. Only known patchable fields accepted. [Phase 173 backfill: `write_audit_event()` wired here]
- `ihouse-ui/lib/api.ts` — `Provider`, `ProviderListResponse`, `Permission`, `PermissionListResponse` types; `getProviders()`, `getPermissions()`, `patchProvider()` API methods added

## Key Design Decisions
- PATCH endpoint is partial — supports individual field updates without requiring full provider object
- Live toggle calls `patchProvider()` immediately on checkbox change (optimistic update with rollback on error)
- 404 guard prevents patching providers that were never registered in the capability registry
- Only known fields accepted: prevents accidental capability additions via PATCH body injection

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Provider registry PATCH is metadata only — never touches booking state ✅
