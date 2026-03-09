# Worker Communication & Escalation Layer — Forward Planning Note

**Status:** Planning Only — Not Active
**Created:** 2026-03-09
**Author:** Product Direction (via user)
**Category:** System Architecture Direction

---

## Context

This document records an important architectural direction for future planning.
It is **not** a request to implement immediately.
It exists so that future decisions leave the correct room for this layer and do not make it harder to add later.

---

## What the System Already Has (the Right Backbone)

The current iHouse Core architecture already contains the necessary foundations:

| Existing Component | Role in Future Worker Layer |
|---|---|
| `event_log` | Append-only audit trail — already correct |
| Task system | The primary work assignment surface |
| Roles & permissions | Role-aware routing already exists |
| SLA escalation engine | Graded escalation already conceptualized |
| Skill-based automation | Operational routing already correct |
| Admin surfaces | Internal dashboard backbone |

**Conclusion:** This is not about inventing a new system. It is about connecting what already exists to a worker-facing surface and graded external notification layer.

---

## Core Direction

The system should eventually support **worker-facing operational communication** for roles including:

- Cleaner
- Check-in / check-out staff
- Operations manager
- Maintenance worker
- Garden / pool / repair worker
- And similar operational roles

These workers should have their own surfaces inside the system:
- Dashboard or mobile view
- Assigned work queue
- Status updates
- Acknowledgement
- Completion logging
- History / audit log of actions

---

## The Single Most Important Design Rule

> **The application is the primary system of record and the primary first notification surface.**

| What lives in iHouse Core | What external channels are |
|---|---|
| Task creation | Fallback only |
| Task status | Escalation only |
| Acknowledgement | Never the source of truth |
| Completion | Supplementary delivery mechanism |
| Escalation state | Triggered by the core — not determined by external |
| Full audit trail | Not replicated externally |

LINE / WhatsApp / Telegram / SMS must **never** become the source of truth.

---

## Preferred External Channel Priority

When the time comes to add external fallback channels, the preferred order is:

| Priority | Channel | Use case |
|---|---|---|
| 1 | **LINE** | Primary external fallback (regional fit) |
| 2 | **WhatsApp** | Secondary external fallback |
| 3 | **Telegram** | Tertiary option |
| 4 | **SMS** | Final critical fallback only |

**The app itself is always first.** External channels trigger only when in-app acknowledgement has not happened within the SLA window.

---

## Graded Escalation Model

> **Not every task needs the same escalation behavior.**
> Escalation must be intelligent, not noisy.

Escalation behavior should depend on:

- Task urgency level
- Time until work is due
- Time until acknowledgement is required
- Role type
- Task type

### Behavior by Urgency

| Urgency Level | In-App | External Escalation | Notes |
|---|---|---|---|
| **Low** | In-app notification, long SLA window | None, or delayed significantly | e.g. task due next week |
| **Medium** | In-app first | Trigger external after delay if no ack | e.g. cleaning task for tomorrow |
| **High** | In-app + fast external fallback | Short window before external triggers | e.g. same-day operational task |
| **Critical** | In-app + immediate external | Escalate to manager + SMS fallback | e.g. unacknowledged missed task |

### Intended Flow

```
1. Task created in the system
2. In-app notification sent first
3. System waits for acknowledgement based on SLA / urgency
   ├── Acknowledgement received → marked complete → no further escalation
   └── No acknowledgement in required time →
       4. Escalation engine triggers external channel (LINE → WhatsApp → Telegram)
       5. If still no acknowledgement → escalate to manager + SMS fallback
6. All events and acknowledgements recorded in the core system
```

---

## What Is Explicitly Not Wanted

| ❌ Do Not Build | Reason |
|---|---|
| LINE / WhatsApp as source of truth | Core must own state |
| External messaging replacing task system | Task system must remain primary |
| All tasks with same escalation speed | Intelligent grading is required |
| Aggressive external notification for non-urgent work | Would be noisy and counter-productive |
| Worker communication as a separate product | Must sit on top of existing architecture |

---

## What Is Wanted

| ✅ Build Toward | Notes |
|---|---|
| Role-aware task assignment | Already partially in place |
| Urgency-aware acknowledgement rules | Needs formalization in task schema |
| Graded escalation timing | SLA escalation engine is the right foundation |
| External channels as fallback only | Integration must respect the core-first rule |
| Clear audit trail for all worker actions | `event_log` is already the correct surface |
| Worker-facing surfaces fitting the existing architecture | Not a separate product |

---

## Architecture Fit Assessment

### What could be introduced earlier (foundations that help later):

1. **Task urgency field** — If the task schema gains an `urgency` field (low/medium/high/critical), the escalation engine can use it without a schema migration later. **Low cost, high future value.**

2. **Worker role type on tasks** — If the task system records which worker *role* a task is for (not just which user), role-aware escalation becomes much easier. **Worth considering in any upcoming task schema work.**

3. **Acknowledgement SLA model** — The SLA escalation engine already handles escalation based on timers. Ensuring `task_id` is associated with escalation events early will make the full worker communication layer a natural extension, not a retrofit.

### What should NOT be built yet:
- External channel integrations (LINE / WhatsApp / etc.)
- Mobile-specific UI surfaces
- Push notification infrastructure

---

## Planning Guidance for Future Phases

When making decisions about:

- Task schema changes → leave room for `urgency`, `worker_role`, `ack_sla_minutes`
- Escalation engine → design triggers to accept task-level context, not just fixed timers
- Worker surfaces → treat as first-class access points, not secondary admin views
- Notification infrastructure → architect as pluggable channels, with in-app always the first slot

**This direction is load-bearing for the operational product. Keep it in mind even when building unrelated phases.**

---

## Summary

| Question | Answer |
|---|---|
| Is this urgent? | No — forward planning only |
| Does it require new infrastructure? | Not yet — existing backbone is correct |
| What foundations help most? | Task urgency field, worker role on tasks, SLA per task |
| What must never happen? | External channels becoming source of truth |
| When should external channels be added? | Only after in-app + ack model is mature |
| What makes this safe to defer? | The event log, task system, and escalation engine are already the right architecture |
