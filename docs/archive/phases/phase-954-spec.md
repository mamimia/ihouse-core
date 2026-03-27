# Phase 954 — Check-in Completion Fixes

**Date**: 2026-03-27

## Objective
Address structural logic bugs in the Check-in operation and handoff process preventing workers from successfully generating guest QR codes and completing check-in tasks.

## Root Causes Identified
1. **QR Handoff Missing / Check-in Failing (403 Forbidden):** The endpoint `POST /bookings/{id}/checkin` guarded access using a strict role string comparison (`role in ('admin', 'manager', 'checkin')`). Check-in field workers authenticate with the role `worker` and hold their true capabilities (like `CHECKIN`) in the `tenant_permissions` DB table. Because of this architectural mismatch, the check-in call failed with `403 Forbidden`, causing the UI to abort and skip the successful "Guest QR Code" step.
2. **CHECKIN task staying active (422 Unprocessable Entity):** Even if check-in suceeded, the task completion call (`PATCH /worker/tasks/{id}/complete`) would always fail because the valid task transitions system in `task_model.py` restricted `ACKNOWLEDGED -> COMPLETED`. A task had to enter `IN_PROGRESS` first to be completed. 

## Architectural Fixes Implemented

### 1. Booking Checkin Worker Capability Guard
- Modified `_assert_checkin_role` and `_assert_checkout_role` in `src/api/booking_checkin_router.py`.
- They now intercept `role="worker"` identities and execute an explicit capability lookup against the `tenant_permissions` table (supporting both modern arrays and legacy JSONB). 
- If the worker holds the `CHECKIN` (or `CHECKOUT`) capability, the action is permitted exactly like an admin.

### 2. Direct Task Completion
- Updated `VALID_TASK_TRANSITIONS` in `src/tasks/task_model.py`.
- Modified `TaskStatus.ACKNOWLEDGED` to allow `TaskStatus.COMPLETED` as a valid next state. This permits one-shot completions (especially common in fast mobile check-ins) without forcing a synthetic `IN_PROGRESS` transition step.

## Safety & Invariants
- No DB schema changes were required.
- Standard capabilities (admin/manager) bypass the DB lookup to preserve latency and original semantics.
- Transitioning from `ACKNOWLEDGED` to `COMPLETED` writes a normal audit event log, preserving data lineage.

## Validation
These fixes enable a field worker to tap "Complete Checkin", immediately check the guest in, see the generated Guest QR handoff, and safely remove the active task from their queue in one seamless flow without silent backend failures.
