# iHouse Core Event Examples

## STATE_TRANSITION
{
  "kind": "STATE_TRANSITION",
  "idempotency": { "request_id": "ex_state_transition_001" },
  "actor": { "actor_id": "admin_1", "role": "admin" },
  "payload": {
    "actor": { "actor_id": "admin_1", "role": "admin" },
    "entity": { "entity_type": "booking", "entity_id": "booking_123" },
    "current": { "current_state": "PENDING", "current_version": 1 },
    "requested": {
      "requested_state": "CONFIRMED",
      "reason_code": "MANUAL",
      "request_id": "ex_state_transition_001"
    },
    "context": {
      "priority_stack": [
        {
          "rules": [
            {
              "id": "allow_pending_to_confirmed",
              "match": { "from": "PENDING", "to": "CONFIRMED" },
              "effect": { "action": "allow", "terminal": true }
            }
          ]
        }
      ],
      "invariants": []
    },
    "time": { "now_utc": "2026-02-26T13:45:00Z" }
  }
}

## BOOKING_CONFLICT
{
  "kind": "BOOKING_CONFLICT",
  "idempotency": { "request_id": "ex_booking_conflict_001" },
  "actor": { "actor_id": "admin_1", "role": "admin" },
  "payload": {
    "idempotency": { "request_id": "ex_booking_conflict_001" },
    "actor": { "actor_id": "admin_1", "role": "admin" },
    "time": { "now_utc": "2026-02-26T13:45:00Z" },
    "policy": {
      "statuses_blocking": ["CONFIRMED", "CHECKED_IN"],
      "conflict_task_type_id": "conflict_task_default",
      "override_request_type_id": "override_request_default",
      "allow_admin_override": true
    },
    "booking_candidate": {
      "booking_id": "b_new_001",
      "property_id": "villa_7",
      "start_utc": "2026-03-03T00:00:00Z",
      "end_utc": "2026-03-06T00:00:00Z",
      "requested_status": "CONFIRMED"
    },
    "existing_bookings": [
      {
        "booking_id": "b_existing_001",
        "property_id": "villa_7",
        "start_utc": "2026-03-02T00:00:00Z",
        "end_utc": "2026-03-04T00:00:00Z",
        "status": "CONFIRMED"
      }
    ]
  }
}

## TASK_COMPLETION
{
  "kind": "TASK_COMPLETION",
  "idempotency": { "request_id": "ex_task_completion_001" },
  "actor": { "actor_id": "ops_1", "role": "ops" },
  "payload": {
    "idempotency": { "request_id": "ex_task_completion_001" },
    "actor": { "actor_id": "ops_1", "role": "ops" },
    "context": {
      "run_id": "ex_run_001",
      "timers_utc": {
        "now_utc": "2026-02-26T13:45:00Z",
        "task_ack_due_utc": "2026-02-26T13:00:00Z",
        "task_completed_due_utc": "2026-02-26T13:30:00Z"
      }
    },
    "task": {
      "task_id": "t_clean_001",
      "property_id": "villa_7",
      "task_type": "cleaning",
      "state": "InProgress",
      "priority": "High",
      "ack_state": "Unacked"
    },
    "policy": {
      "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
      "notify_admin_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"]
    }
  }
}

## SLA_ESCALATION
{
  "kind": "SLA_ESCALATION",
  "idempotency": { "request_id": "ex_sla_escalation_001" },
  "actor": { "actor_id": "ops_1", "role": "ops" },
  "payload": {
    "idempotency": { "request_id": "ex_sla_escalation_001" },
    "actor": { "actor_id": "ops_1", "role": "ops" },
    "context": {
      "run_id": "ex_run_002",
      "timers_utc": {
        "now_utc": "2026-02-26T13:45:00Z",
        "task_ack_due_utc": "2026-02-26T13:40:00Z",
        "task_completed_due_utc": "2026-02-26T13:44:00Z"
      }
    },
    "task": {
      "task_id": "t_maint_001",
      "property_id": "villa_9",
      "task_type": "maintenance",
      "state": "InProgress",
      "priority": "High",
      "ack_state": "Unacked"
    },
    "policy": {
      "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
      "notify_admin_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"]
    }
  }
}
