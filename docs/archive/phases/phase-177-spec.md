# Phase 177 — SLA→Dispatcher Bridge

**Status:** Closed  
**Prerequisite:** Phase 176 (Outbound Sync Auto-Trigger for BOOKING_CREATED)  
**Date Closed:** 2026-03-10

## Goal

Connect the output of `sla_engine.evaluate()` (`EscalationResult.actions`) to `notification_dispatcher.dispatch_notification()`. When an SLA breach is detected, the bridge resolves the target audience from `tenant_permissions` and fires push notifications via the existing dispatcher infrastructure.

## Invariant

- `sla_engine.py` remains **pure** — no side-effects, no DB calls.
- `notification_dispatcher.py` remains **channel-only** — no SLA knowledge.
- Bridge is **best-effort** — any exception is swallowed, never raises.
- **Tenant isolation**: only `tenant_permissions` rows matching `tenant_id` are resolved.
- A failed dispatch for one user never blocks other users.

## Design / Files

| File | Change |
|------|--------|
| `src/channels/sla_dispatch_bridge.py` | NEW — `dispatch_escalations()`, `_resolve_users()`, `_build_message()`, `BridgeResult` |
| `tests/test_sla_dispatch_bridge_contract.py` | NEW — 28 contract tests (Groups A–E) |

### Target resolution

| `action.target` | Roles queried |
|-----------------|---------------|
| `"ops"` | `worker`, `manager` |
| `"admin"` | `admin` |

## Result

**4,629 tests pass, 3 skipped.**  
`sla_engine.py` and `notification_dispatcher.py` not modified.
