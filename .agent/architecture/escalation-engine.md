# Escalation Engine

## Core Principle

System enforces operational discipline.
Escalation cannot be fully disabled.
Critical protection is always active.

---

## Escalation Policy Modes

Each Company has one EscalationPolicy:

1. Strict
2. Default
3. Relaxed

Admin may switch between modes.
Critical rules are never bypassed.

---

## Mode Definitions

### Strict

Normal:
Ack SLA default: 20 minutes
Action SLA default: 60 minutes
Escalation enabled

Critical:
Ack SLA: 5 minutes (fixed)
Immediate escalation if no acknowledgement
Action SLA: 30 minutes
Escalation mandatory

---

### Default

Normal:
Ack SLA default: 20 minutes
Action SLA default: 90 minutes
Escalation enabled

Critical:
Ack SLA: 5 minutes (fixed)
Action SLA: 30 minutes
Escalation mandatory

---

### Relaxed

Normal:
Ack SLA default: 30 minutes
Action SLA default: 120 minutes
Escalation only after Action SLA

Critical:
Ack SLA: 5 minutes (fixed)
Action SLA: 30 minutes
Escalation mandatory

---

## Escalation Levels

Level 1:
Notify OperationalManager

Level 2:
If not acknowledged within SLA:
Notify Admin
Create EscalationTask
Write audit entry

Level 3:
If Critical and not acknowledged within 5 minutes:
Immediate Admin notification
Property status → AtRisk
Write audit entry

---

## Acknowledgement Logic

Ack does NOT stop Action SLA.
Only transition to InProgress stops initial timer.

If no progress change within Action SLA:
Escalate regardless of acknowledgement.

---

## Invariant

1. Critical issues always escalate after 5 minutes if not acknowledged.
2. No user may disable Critical escalation.
3. All escalations generate audit entries.
4. All SLA timers must be configurable within safe bounds for Normal tasks only.