# Phase 183 — Notification Delivery Status Tracking

**Status:** Open  
**Prerequisite:** Phase 182  
**Date Opened:** 2026-03-10

## Problem

`dispatch_notification()` returns a `DispatchResult` with every `ChannelAttempt` (channel_type, success, error) — but nothing is stored to the database. If LINE fails for a user, there is no record operators can query. No observability on notification health.

## Goal

Record every dispatch attempt to a `notification_delivery_log` table. One row per `ChannelAttempt`, inserted immediately after `dispatch_notification()` returns in `sla_dispatch_bridge.py`.

## Files

```
NEW:  src/core/db/migrations/0012_notification_delivery_log.sql
NEW:  src/channels/notification_delivery_writer.py   — write_delivery_log()
MOD:  src/channels/sla_dispatch_bridge.py            — wire write_delivery_log after dispatch
NEW:  tests/test_notification_delivery_writer_contract.py
```

## Schema: notification_delivery_log

```sql
notification_delivery_id  TEXT PRIMARY KEY  -- uuid
tenant_id                 TEXT NOT NULL
user_id                   TEXT NOT NULL
task_id                   TEXT              -- nullable (not all notifications are task-related)
trigger_reason            TEXT              -- e.g. ACK_SLA_BREACH
channel_type              TEXT NOT NULL     -- line | fcm | email
channel_id                TEXT NOT NULL     -- LINE user_id / FCM token / email address
status                    TEXT NOT NULL     -- sent | failed
error_message             TEXT              -- NULL on success
dispatched_at             TIMESTAMPTZ DEFAULT now()
```

## Invariants

- Best-effort: write_delivery_log never raises, never blocks the dispatch response.
- One row per ChannelAttempt (not one per DispatchResult).
- status = "sent" if ChannelAttempt.success, else "failed".
- DB write failure is logged as warning and swallowed.
- No RLS changes required (internal service table).

## Result

**TBD.**
