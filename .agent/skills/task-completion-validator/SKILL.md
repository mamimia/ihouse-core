---
name: escalating-task-slas
description: Consumes explicit timers and task states to deterministically emit escalation actions and audit events, including a fixed critical acknowledgement SLA of 5 minutes. Use when the user mentions SLA, escalation, acknowledgements, timers, or notifications.
---

# SLA Escalation Engine

## When to use this skill
1. Caller has explicit timer inputs and task states
2. System must emit escalation actions deterministically
3. Critical acknowledgement SLA is fixed at 5 minutes

## Contract
### Inputs
1. actor
   • actor_id
   • role
2. context
   • run_id
   • timers_utc
     - now_utc
     - task_created_utc (optional string allowed empty)
     - task_ack_due_utc (optional string allowed empty)
     - task_completed_due_utc (optional string allowed empty)
3. task
   • task_id
   • property_id
   • task_type
   • state: Open | InProgress | Completed | Cancelled
   • priority: Normal | High | Critical
   • ack_state: Unacked | Acked
4. policy
   • notify_ops_on (list of triggers)
   • notify_admin_on (list of triggers)
5. idempotency
   • request_id

### Outputs
1. actions
   • list of {action_type, target, reason, task_id, property_id, request_id}
2. events_to_emit
   • AuditEvent (exactly one)
3. side_effects
   • none

## Core logic
1. Determine ack_due_utc:
   • If task.priority == Critical and context.timers_utc.task_ack_due_utc is empty, caller must still provide it
   • Critical ack SLA is fixed at 5 minutes, so caller should set task_ack_due_utc = task_created_utc + 5 minutes
2. If task.state is Completed or Cancelled: no actions, audit only
3. If task.ack_state == Unacked and now_utc >= task_ack_due_utc: emit escalation trigger ACK_SLA_BREACH
   • action notify_ops if policy.notify_ops_on includes ACK_SLA_BREACH
   • action notify_admin if policy.notify_admin_on includes ACK_SLA_BREACH
4. If task.state not Completed and task_completed_due_utc not empty and now_utc >= task_completed_due_utc:
   • trigger COMPLETION_SLA_BREACH
   • apply policy routing similarly

## Determinism constraints
1. No implicit time access
2. No storage reads
3. No network calls
4. All decisions are functions of explicit inputs

## AuditEvent fields
1. request_id
2. run_id
3. task_id, property_id, task_type, state, priority, ack_state
4. now_utc, task_ack_due_utc, task_completed_due_utc
5. triggers_fired
6. actions_emitted (types + targets)

## Resources
1. scripts/sla_escalation_engine.py