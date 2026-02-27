---
name: resolving-booking-conflicts
description: Validates booking overlaps, enforces PendingResolution, and deterministically returns ConflictTask or OverrideRequest plus audit event payloads. Use when the user mentions booking overlaps, double booking, conflict resolution, overrides, or pending resolution.
---

# Booking Conflict Resolver

## When to use this skill
1. Booking create or update can overlap existing bookings for the same property
2. Caller needs deterministic conflict handling without hidden side effects
3. System must enforce PendingResolution when overlap exists

## Contract
### Inputs
1. actor
   • actor_id
   • role
2. booking_candidate
   • booking_id
   • property_id
   • start_utc
   • end_utc
   • requested_status (optional)
3. existing_bookings
   • list of {booking_id, property_id, start_utc, end_utc, status}
4. policy
   • statuses_blocking (list)
   • allow_admin_override (bool)
   • conflict_task_type_id
   • override_request_type_id
5. idempotency
   • request_id
6. time
   • now_utc

### Outputs
1. decision
   • allowed (bool)
   • enforced_status (string or empty string)
   • conflicts_found (list of booking_ids)
   • denial_code (string or empty string)
2. artifacts_to_create
   • ConflictTask (0 or 1)
   • OverrideRequest (0 or 1)
3. events_to_emit
   • AuditEvent (exactly one)
4. side_effects
   • none

## Workflow
1. Validate candidate window start_utc < end_utc
2. Filter existing_bookings by same property_id and blocking statuses
3. Compute overlaps deterministically
4. If no conflicts
   • allowed=true
   • enforced_status=requested_status or empty
   • no artifacts
5. If conflicts exist
   • allowed=true
   • enforced_status="PendingResolution"
   • emit ConflictTask
   • emit OverrideRequest only if allow_admin_override and actor.role in {"admin","ops_admin"}
6. Emit AuditEvent payload and return

## Overlap rule
Intervals overlap if:
1. candidate.start_utc < other.end_utc
2. candidate.end_utc > other.start_utc
End equals start is not overlap.

## Artifact outputs
### ConflictTask
Fields:
1. artifact_type: ConflictTask
2. type_id: policy.conflict_task_type_id
3. status: Open
4. priority: High
5. property_id
6. booking_id
7. conflicts_found
8. request_id

### OverrideRequest
Fields:
1. artifact_type: OverrideRequest
2. type_id: policy.override_request_type_id
3. status: Requested
4. required_approver_role: admin
5. property_id
6. booking_id
7. conflicts_found
8. request_id

## AuditEvent
Fields:
1. request_id
2. actor_id, role
3. booking_id, property_id
4. window start_utc, end_utc
5. conflicts_found
6. enforced_status
7. artifacts emitted (types only)
8. now_utc

## Determinism constraints
1. No implicit time
2. No storage reads
3. No network calls
4. Decision is function of explicit inputs only

## Resources
1. scripts/booking_conflict_resolver.py