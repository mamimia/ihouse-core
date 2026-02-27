---
name: validating-state-transitions
description: Validates requested entity state changes using a priority stack and invariants, then emits an AuditEvent and returns the allowed next state. Use when the user mentions state transitions, guards, invariants, priority rules, or audit events.
---

# State Transition Guard

## When to use this skill
1. Any command requests a state change (task, booking, property, user, issue, override)
2. A caller needs a deterministic allowed next state computed from explicit inputs
3. The system must emit an AuditEvent for every attempted transition

## Contract
### Inputs (explicit)
1. actor
   • actor_id
   • role
   • permissions (optional, precomputed by caller)
2. entity
   • entity_type
   • entity_id
3. current
   • current_state
   • current_version (or event_cursor)
4. requested
   • requested_state
   • reason_code
   • request_id (idempotency key)
5. context
   • priority_stack (ordered list of rule sets)
   • invariants (named invariant set)
   • related_facts (any precomputed facts the caller wants the guard to use)
6. time
   • now_utc (explicit timestamp provided by caller)

### Outputs (explicit)
1. decision
   • allowed (true|false)
   • allowed_next_state (state)
   • denial_code (if denied)
   • applied_rules (ordered list)
2. events_to_emit
   • AuditEvent (exactly one per request_id)
3. side_effects
   • none (this skill never writes records, never reads implicit time)

## Workflow
### Checklist
1. Confirm input completeness (no implicit reads)
2. Build candidate transitions (current_state → requested_state)
3. Evaluate priority stack (highest to lowest)
4. Evaluate invariants (must all hold)
5. Produce deterministic decision and allowed_next_state
6. Emit AuditEvent payload (returned, not written)
7. Return result

### Plan → Validate → Execute loop
1. Plan
   • Determine transition type and applicable rule sets from priority_stack
2. Validate
   • Run rule evaluation and invariant checks in strict order
   • Verify idempotency with request_id in caller layer (skill is pure)
3. Execute
   • Return decision and AuditEvent payload

## Rules engine semantics
### Priority Stack
1. Represented as an ordered list of rule sets
2. Evaluation is deterministic and stable
3. First matching terminal rule wins
4. Non terminal rules may annotate applied_rules but cannot override a terminal decision

### Rule shape
A rule is a pure predicate plus an optional transform.
1. match(input) → true|false
2. effect(input) → DecisionDelta
   • allow or deny
   • force_next_state (optional)
   • applied_rule_id
   • denial_code (optional)

### Invariants
1. Invariants are boolean predicates evaluated after priority rules
2. Any invariant failure forces deny unless a higher priority explicit override rule allowed it and the invariant is marked overrideable in context

## AuditEvent specification
Return a single event object:
1. event_type: "AuditEvent"
2. request_id
3. actor_id, role
4. entity_type, entity_id
5. current_state, requested_state, allowed_next_state
6. decision_allowed
7. denial_code (optional)
8. applied_rules
9. now_utc

## Determinism constraints
1. No implicit time access
2. No hidden IO
3. No randomization
4. No reads from storage
5. All decisions are functions of explicit inputs

## Error handling
1. Missing required fields
   • return allowed=false, denial_code="INPUT_INVALID"
   • still return an AuditEvent payload with denial_code
2. Unknown state or transition
   • denial_code="UNKNOWN_TRANSITION"
3. Conflicting rule outputs
   • denial_code="RULE_CONFLICT"
4. Invariant evaluation error
   • denial_code="INVARIANT_ERROR"

## Resources
1. scripts/state_transition_guard.py