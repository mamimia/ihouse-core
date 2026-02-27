---
name: escalating-task-slas
description: Consumes explicit timers and task states to deterministically emit escalation actions and audit events, including a fixed critical acknowledgement SLA of 5 minutes. Use when the user mentions SLA, escalation, acknowledgements, timers, or notifications.
---

# SLA Escalation Engine

## When to use this skill
1. Caller provides explicit timers and task state
2. Need deterministic escalation decisions and audit output
3. Critical acknowledgement SLA is fixed at 5 minutes

## Contract
### Inputs
1. actor
   • actor_id
   • role
2. context
   • run_id
   • timers_utc
     • now_utc
     • task_ack_due_utc (string or empty)
     • task_completed_due_utc (string or empty)
3. task
   • task_id
   • property_id
   • task_type
   • state: Open | InProgress | Completed | Cancelled
   • priority: Normal | High | Critical
   • ack_state: Unacked | Acked
4. policy
   • notify_ops_on: list of triggers
   • notify_admin_on: list of triggers
5. idempotency
   • request_id

### Outputs
1. actions
   • list of {action_type, target, reason, task_id, property_id, request_id}
2. events_to_emit
   • AuditEvent exactly one
3. side_effects
   • empty list

## Core rules
1. No implicit time. Caller must supply now_utc and due timestamps
2. Terminal states Completed or Cancelled emit audit only
3. If ack_state Unacked and now_utc >= task_ack_due_utc then trigger ACK_SLA_BREACH
4. If now_utc >= task_completed_due_utc and state not Completed then trigger COMPLETION_SLA_BREACH
5. Routing is policy driven by notify_ops_on and notify_admin_on

## Fixed SLA note
Critical ack SLA is fixed at 5 minutes.
The engine does not compute timestamps.
Caller must provide task_ack_due_utc accordingly.

## Determinism constraints
1. No storage reads
2. No network calls
3. No randomness
4. Output depends only on explicit input

## Resources
1. scripts/sla_escalation_engine.py