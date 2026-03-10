# Phase 182 — Outbound Sync Auto-Trigger for BOOKING_CANCELED + BOOKING_AMENDED

**Status:** Open  
**Prerequisite:** Phase 176 (BOOKING_CREATED auto-trigger), Phase 181 (SSE)  
**Date Opened:** 2026-03-10

## Problem

Phase 176 wired `build_sync_plan → execute_sync_plan` for BOOKING_CREATED — giving it:
- Rate-limit enforcement (Phase 141)
- Exponential backoff retry (Phase 142)
- Idempotency key (Phase 143)
- Sync log persistence (Phase 144)

BOOKING_CANCELED and BOOKING_AMENDED use `cancel_sync_trigger.py` / `amend_sync_trigger.py`
which call adapters **directly** — bypassing all Phase 141-144 guarantees.

## Goal

Build `outbound_canceled_sync.py` and `outbound_amended_sync.py` following the exact
pattern of `outbound_created_sync.py`. Wire them into `service.py` after the existing
direct-adapter triggers (additive, not replacing).

## Files

```
NEW:  src/services/outbound_canceled_sync.py  — fire_canceled_sync()
NEW:  src/services/outbound_amended_sync.py   — fire_amended_sync()
MOD:  src/adapters/ota/service.py             — wire both into CANCELED + AMENDED blocks
NEW:  tests/test_outbound_lifecycle_sync_contract.py  — contract tests
```

## Result

**TBD.**
