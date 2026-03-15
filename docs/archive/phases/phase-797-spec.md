# Phase 797 — First Real OTA Webhook

**Status:** Closed
**Prerequisite:** Phase 796 (Staging Deploy & Smoke Test)
**Date Closed:** 2026-03-15

## Goal

Prove the full OTA ingestion chain end-to-end: webhook POST → event_log writes → booking_state visible → financial facts recorded → tasks auto-generated.

## Invariant

OTA webhook must produce verifiable data trail: event_log rows, booking_state record, financial_facts row, and auto-generated tasks.

## Design / Files

| File | Change |
|------|--------|
| `src/api/webhooks.py` | USED — POST /webhooks/bookingcom |

## Result

Webhook: `POST /webhooks/bookingcom` → 200 ACCEPTED. event_log: 2 rows (envelope_received + STATE_UPSERT). booking_state: `bookingcom_bdc-p797-live-002` active, check-in 04/10–04/14. GET /bookings: booking visible via API. booking_financial_facts: 28,500 THB recorded. tasks: 2 auto-generated (CHECKIN_PREP HIGH + CLEANING MEDIUM).
