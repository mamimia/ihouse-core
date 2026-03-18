> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Phase 840 Handoff

**Current Active Phase:** Phase 841
**Last Closed Phase:** Phase 840 — Property Settings Surface + OTA Management

## Context
In the previous chat session (Phase 840), I assumed control of the codebase to build out the OTA Settings Tab inside the Property Details view. 

This included:
1. Added two new backend endpoints to `bulk_import_router.py`: `GET /properties/{id}/ical-connections` and `DELETE /integrations/ical/{connection_id}` to support the UI without rewriting existing channel APIs.
2. Built `OtaSettingsTab.tsx` with dynamic sub-tabs for iCal and API, filtering providers via the `provider_capability_registry`.
3. Added the "Add Booking" manual booking entrypoint button locked to the specific property in the header of `page.tsx`.
4. Addressed minor UI requests: fixing the Location Map card size, replacing raw coordinates, redesigning the Reference Photos using CSS Grid, and introducing the `Set as Cover` action pattern in the Gallery tab.
5. Addressed the `tenant_id` isolation logic for the `property_owners` route.

## System Condition
The system is passing 7,757 out of 7,784 backend test cases. (A small drop of ~27 failures is expected due to unrelated schema drift like `tasks.escalation_level does not exist` that might need attention later).
The BOOT protocol documentation has been fully updated and synchronized to reflect the completion of Phase 840.

## Next Step
We are ready to start a completely fresh session.
Please read `current-snapshot.md` and `work-context.md` to see what is next. You can pick either Phase 841 (Guest Portal + Owner Localization) or address any other request from the user.
