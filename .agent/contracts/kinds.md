# iHouse Core Event Contracts

## Envelope (כל אירוע שמגיע ל־/event)
Required:
kind: string
idempotency:
  request_id: string
actor:
  actor_id: string
  role: string
payload: object

Notes:
event_router בוחר skill לפי kind ומעביר ל־skill_runner את payload בלבד.
כל skill מחזיר JSON תקין בלבד.

---

## STATE_TRANSITION
skill: state-transition-guard

payload required:
actor:
  actor_id: string
  role: string
entity:
  entity_type: string
  entity_id: string
current:
  current_state: string
  current_version: number|string
requested:
  requested_state: string
  reason_code: string
  request_id: string
context:
  priority_stack: list
  invariants: list
time:
  now_utc: string (ISO-8601)

skill output:
decision:
  allowed: bool
  allowed_next_state: string
  denial_code: string
  applied_rules: list
events_to_emit: list (AuditEvent)
side_effects: list

---

## BOOKING_CONFLICT
skill: booking-conflict-resolver

payload required:
idempotency:
  request_id: string
actor:
  actor_id: string
  role: string
time:
  now_utc: string (ISO-8601)
policy:
  statuses_blocking: list[string]
  conflict_task_type_id: string
  override_request_type_id: string
  allow_admin_override: bool
booking_candidate:
  booking_id: string
  property_id: string
  start_utc: string (ISO-8601)
  end_utc: string (ISO-8601)
  requested_status: string
existing_bookings: list[object]
  each:
    booking_id: string
    property_id: string
    start_utc: string
    end_utc: string
    status: string

skill output:
decision:
  allowed: bool
  enforced_status: string
  conflicts_found: list[string]
  denial_code: string
artifacts_to_create: list
events_to_emit: list (AuditEvent)
side_effects: list

---

## TASK_COMPLETION
skill: task-completion-validator

payload required:
idempotency:
  request_id: string
actor:
  actor_id: string
  role: string
context:
  run_id: string
  timers_utc:
    now_utc: string
    task_ack_due_utc: string
    task_completed_due_utc: string
task:
  task_id: string
  property_id: string
  task_type: string
  state: string
  priority: string
  ack_state: string
policy:
  notify_ops_on: list[string]
  notify_admin_on: list[string]

skill output:
actions: list
events_to_emit: list (AuditEvent)
side_effects: list

---

## SLA_ESCALATION
skill: sla-escalation-engine

payload required:
idempotency:
  request_id: string
actor:
  actor_id: string
  role: string
context:
  run_id: string
  timers_utc:
    now_utc: string
    task_ack_due_utc: string
    task_completed_due_utc: string
task:
  task_id: string
  property_id: string
  task_type: string
  state: string
  priority: string
  ack_state: string
policy:
  notify_ops_on: list[string]
  notify_admin_on: list[string]

skill output:
actions: list
events_to_emit: list (AuditEvent)
side_effects: list
