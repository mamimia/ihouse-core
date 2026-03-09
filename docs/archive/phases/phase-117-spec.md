# Phase 117 — SLA Escalation Engine

**Status:** Closed
**Prerequisite:** Phase 116 (Financial Aggregation API)
**Date Closed:** 2026-03-09

## Goal

Implement the SLA Escalation Engine — a pure, deterministic Python module that consumes explicit task state + timer inputs and emits escalation actions + a single AuditEvent. No storage, no network, no randomness. Based on the `.agent/skills/sla-escalation-engine/SKILL.md` contract.

## Invariants

- No implicit time — caller must supply `now_utc`, `task_ack_due_utc`, `task_completed_due_utc`
- No storage reads or writes
- No network calls
- No randomness — output is a deterministic function of input only
- Terminal states (`Completed`, `Cancelled`) → audit only, never escalation actions
- Critical ack SLA = **5 minutes** (fixed constant `CRITICAL_ACK_SLA_MINUTES`)
- `side_effects` is always `[]`

## Triggers

| Trigger | Condition |
|---------|-----------|
| `ACK_SLA_BREACH` | `ack_state == "Unacked"` AND `now_utc >= task_ack_due_utc` (non-empty) |
| `COMPLETION_SLA_BREACH` | `now_utc >= task_completed_due_utc` (non-empty) AND `state != "Completed"` |

## Policy Routing

Triggers are routed to `notify_ops` and/or `notify_admin` based on the `policy.notify_ops_on` / `policy.notify_admin_on` lists. If a trigger fires but isn't in any policy list, it appears in the audit `triggers_fired` but emits no actions.

## Files

| File | Change |
|------|--------|
| `src/tasks/sla_engine.py` | NEW — `evaluate(payload) → EscalationResult` |
| `tests/test_sla_engine_contract.py` | NEW — 38 tests, Groups A–I |
| `docs/archive/phases/phase-117-spec.md` | NEW — this file |

## Result

**2747 tests pass, 2 pre-existing SQLite skips, 3 warnings.**
No DB schema changes. Pure logic module.
