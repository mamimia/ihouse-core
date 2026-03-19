> ⚠️ FIRST: Read `docs/core/BOOT.md` before doing anything else.

# Handoff from Phase 842

- **Current Phase Target:** Phase 843 (Next iteration for SLA Escalation Triggers or Mobile Checks)
- **Last Closed Phase:** Phase 842 (Staff Management UX & Telegram Dispatch Verification)

## What was completed in the previous chat:
1. Revamped the Staff Profile UI at `/admin/staff/[userId]` and `/new`.
    - Added comprehensive country code (`phoneCode`) logic, separating the primary dial code from the local part.
    - Added similar structured data for `Emergency Contact`.
    - Implemented smart state auto-sync for `SMS` and `WhatsApp` settings when the primary phone changes.
    - Replaced the simple language dropdown with a fully mapped set of globally relevant language preferences (TH, HE, EN, etc).
2. Proved the physical Dispatcher Adapter!
    - We wrote a Python script (`run_trigger.py`) that executes `_default_telegram_adapter`.
    - The dispatcher dynamically reads the `tenant_integrations` table for the bot token, pulls the user's `comm_preference` settings and `language`, translates the alert, and uses `httpx` to ping the Telegram API.
    - User (Elad Mami) successfully received multi-lingual alerts to his physical device!
3. Enforced the "Domaniqo vs iHouse Core" brand separation. The system sends alerts using the external brand name "Domaniqo_bot".

## Immediate Next Steps (Infer from conversation context):
1. Review the SLA Engine and `booking_checkin_router.py` to auto-trigger these beautiful notification payloads when actual tasks change state or when 5 minutes expire without an ACK.
2. The user has demonstrated that the Notification Dispatch mechanics are fully verified. The next challenge is writing the background triggers or closing out remaining Admin UI capabilities.

## Helpful Pointers:
- Check `docs/core/current-snapshot.md` for overall coverage.
- The `tenant_integrations` and `tenant_permissions` JSON structures are proven. Do not break their JSON schemas.
- Run `npm run dev` in the `/ihouse-ui` folder. Backend uvicorn running on port 8000.
