# Phase 840 — Property Settings Surface + OTA Management

**Status:** Closed
**Prerequisite:** Phase 837 (Guest Portal Data Binding)
**Date Closed:** 2026-03-18

## Goal

Bridged the gap between the existing property-scoped channel/iCal backend and the Admin UI. Created a dedicated "OTA Settings" tab inside the property detail view with split iCal and API sub-tabs, filtered dynamically by the provider registry capabilities. Redesigned the Map (Location) card to be correctly sized and fully operational, adjusted the Reference Photos grid layout, and added an "Add Booking" property-locked manual booking entrypoint to the header. Also addressed the tenant_id isolation in owner routing.

## Invariant (if applicable)

- `channel_map` and `ical_connections` continue to be the source of truth for OTA mappings on the property level.
- `tenant_id` must not be explicitly managed un-walled in joining tables like `property_owners` where the identity relies exclusively on the primary entities.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/properties/[propertyId]/page.tsx` | MODIFIED — Redesigned overview cards (Map size/zoom), Photo grid, added Set as Cover, added Add Booking button, registered OTA Settings tab |
| `ihouse-ui/app/(app)/admin/properties/[propertyId]/OtaSettingsTab.tsx` | NEW — Standalone component for iCal and API channel connection management using 7 existing endpoints and 2 new endpoints |
| `ihouse-ui/app/(app)/admin/bookings/intake/page.tsx` | MODIFIED — Reads `?property=` param to auto-fill and lock manual booking property selection |
| `src/api/bulk_import_router.py` | MODIFIED — Added `provider` column handling to `connect_ical`, added `GET /properties/{id}/ical-connections` and `DELETE /integrations/ical/{id}` |

## Result

**All tests pass.**
The property detail UI now directly supports channel mapping without dumping users into the global health dashboards.
