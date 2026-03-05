# iHouse Core — System Architecture

This document explains the full architecture of the iHouse system.

It is an explanatory document only.  
Canonical rules remain defined in:

docs/core/vision.md  
docs/core/system-identity.md  
docs/core/canonical-event-architecture.md  

---

# High Level Model

The system follows a layered architecture.

Event Core  
Domain State  
Automation Skills  
User Interfaces

In simplified form:

event ledger → projections → automation → UI

---

# 1 Event Core

The event core is the operating system of iHouse.

Core principles:

- event_log is the canonical ledger
- apply_envelope is the single write gate
- projections derive state from events
- deterministic rebuild is guaranteed

Primary tables:

event_log  
booking_state

All writes must pass through apply_envelope.

---

# 2 Domain System

Domain architecture is documented under:

.agent/architecture

These files describe functional areas of the product.

Examples:

admin-dashboard.md  
ops-dashboard.md  
property-detail.md  
mobile-checkin.md  
mobile-cleaner.md  
mobile-maintenance.md  

These describe the user facing product model.

---

# 3 Status Model

The system operates using a controlled state model.

Document:

status-model.md

State transitions are protected by the state transition guard skill.

---

# 4 Task System

Tasks represent operational work in the property lifecycle.

Document:

task-chain.md

Tasks drive work for cleaners, maintenance teams, and operations.

---

# 5 Permissions System

Access control is defined by roles and permissions.

Document:

roles-permissions.md

Used by dashboards and mobile clients.

---

# 6 Booking Synchronization

Bookings are ingested from external systems.

Document:

booking-sync.md

External data enters the system as events through apply_envelope.

---

# 7 Automation Skills

Automation logic runs through skills.

Skills live in two locations.

Specification:

.agent/skills

Implementation:

src/core/skills

Skills include:

booking-sync-ingest  
booking-conflict-resolver  
sla-escalation-engine  
state-transition-guard  
task-completion-validator  

Skills react to events and enforce system invariants.

---

# 8 User Interfaces

User interfaces consume projections and APIs.

Examples:

admin dashboard  
operations dashboard  
mobile cleaner app  
mobile maintenance app  
mobile check-in

Dashboards visualize operational state.

---

# 9 Escalation Engine

The SLA escalation engine ensures operational deadlines are met.

Document:

escalation-engine.md

Escalations are triggered automatically by skills.

---

# 10 System Flow

End to end flow:

1 External event arrives  
2 Envelope enters apply_envelope  
3 Event stored in event_log  
4 Projection updates booking_state  
5 Skills evaluate new state  
6 Tasks or escalations are triggered  
7 UI reflects updated state

---

# 11 Architecture Stability Rules

The following components must remain stable:

Event ledger model  
Write gate apply_envelope  
Projection rebuild capability  
Skill based automation model

New features should extend the system without breaking these principles.

---

# 12 Future Evolution

Possible expansions:

additional projections  
analytics layer  
AI decision modules  
workflow orchestration

All new modules must respect the canonical event architecture.

