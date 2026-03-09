# Phase 124 — External Channel Escalation (LINE first)

**Status:** Closed
**Prerequisite:** Phase 117 (SLA Escalation Engine), Phase 123 (Worker Task Surface)
**Date Closed:** 2026-03-09

## Goal

Integrate LINE as the first external fallback channel for task escalation.
Triggered only after in-app ACK SLA is breached (Phase 117 engine emits ACK_SLA_BREACH).
iHouse Core remains the source of truth — LINE is delivery only.

## Core Rule (from worker-communication-layer.md)

> The application is the primary system of record and the primary first notification surface.
> External channels (LINE) are fallback only — never the source of truth.

## Design / Files

| File | Change |
|------|--------|
| `src/channels/line_escalation.py` | NEW — pure module: build_line_message, should_escalate, LineEscalationRequest, LineDispatchResult |
| `src/api/line_webhook_router.py` | NEW — POST /line/webhook — receives LINE ack callback → writes ACKNOWLEDGED to tasks |
| `src/main.py` | MODIFIED — register line_webhook_router |
| `tests/test_line_escalation_contract.py` | NEW — pure unit tests for line_escalation.py |
| `tests/test_line_webhook_router_contract.py` | NEW — contract tests for /line/webhook endpoint |
| `docs/archive/phases/phase-124-spec.md` | NEW (this file) |

## Architecture

```
SLA Engine (Phase 117)
  → evaluate() → EscalationResult
     ↓ ACK_SLA_BREACH triggered
  → should_escalate(result) → bool
     ↓ true
  → build_line_message(task_row) → LineEscalationRequest
     ↓ (in production: sent to LINE Messaging API)
     ↓ (in tests: stubbed)

LINE callback:
  POST /line/webhook { "task_id": ..., "acked_by": ... }
     → writes status=ACKNOWLEDGED to tasks table
```

## Invariants

- `line_escalation.py` is pure — NO network calls, NO DB reads/writes.
  Production dispatch (HTTP to LINE API) is NEVER in the pure module.
- The webhook endpoint is the ONLY writable surface receiving external input.
  It validates the LINE webhook secret (env: LINE_WEBHOOK_SECRET) in production.
  In development mode (LINE_WEBHOOK_SECRET unset), validation is skipped.
- LINE acknowledges → task transitions PENDING→ACKNOWLEDGED only if task is still PENDING.
  Idempotent: ACKNOWLEDGED task is a no-op (200, not error).
- LINE is never source of truth: /line/webhook ONLY writes to `tasks`.

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `LINE_WEBHOOK_SECRET` | unset | dev-mode: skip signature validation |
| `LINE_CHANNEL_ACCESS_TOKEN` | unset | required in production for dispatch |

## Result

**~3035 tests pass, 2 pre-existing SQLite skips.**
No DB schema changes. /line/webhook writes ONLY to `tasks`.
