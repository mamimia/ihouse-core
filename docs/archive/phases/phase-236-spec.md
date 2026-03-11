# Phase 236 — Guest Communication History

**Status:** Closed
**Prerequisite:** Phase 235 — Multi-Property Conflict Dashboard
**Date Closed:** 2026-03-11

## Goal

Phase 227 drafts guest messages but never persists what was actually sent. This phase closes the guest messaging lifecycle by adding a log table and two endpoints: one to record a sent/received message, and one to retrieve the full chronological timeline for any booking.

## Invariant (Phase 236)

`POST /guest-messages/{booking_id}` writes only to `guest_messages_log`. It never writes to `booking_state`, `event_log`, or `tasks`. `GET` is read-only.

## Design / Files

| File | Change |
|------|--------|
| `supabase/migrations/20260311152100_phase236_guest_messages_log.sql` | NEW — `guest_messages_log` table |
| `src/api/guest_messages_router.py` | NEW — POST + GET `/guest-messages/{booking_id}` |
| `src/main.py` | MODIFIED — `guest_messages_router` registered |
| `tests/test_guest_messages_contract.py` | NEW — 19 contract tests |
| `docs/archive/phases/phase-236-spec.md` | NEW — this file |

## Key Design Choices

- `content_preview` capped at 300 chars server-side
- `draft_id` optional — links to Phase 227 copilot draft when applicable
- `direction`: `OUTBOUND` | `INBOUND`
- `channel`: `email | whatsapp | sms | line | telegram | manual`
- No LLM dependency

## Result

**19 tests pass.**
No writes to core tables. Tenant-isolated.
