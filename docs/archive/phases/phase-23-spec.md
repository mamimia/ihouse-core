You are continuing work on the **iHouse Core system**.

Before proposing any changes you must read the canonical documents in this order:

1. docs/core/canonical-event-architecture.md
2. docs/core/system-identity.md
3. docs/core/current-snapshot.md
4. docs/core/phase-23-spec.md
5. docs/core/phase-timeline.md (latest section only)
6. docs/core/construction-log.md (latest section only)
7. docs/core/roadmap.md

Do not assume architecture without reading these files.

These documents define the canonical invariants of the system.

---

# System Overview

iHouse Core is a **deterministic event-sourced SaaS kernel**.

Canonical persistence:

Supabase
public.event_log
public.booking_state

Core rule:

event_log = immutable source of truth
booking_state = projection derived by the DB apply gate

The system is designed so that **all state mutations originate from the canonical database apply gate**.

The application layer must never mutate projections directly.

---

# Canonical Apply Gate

All events enter the system only through:

apply_envelope RPC

Properties:

• atomic
• idempotent
• deterministic
• replay safe

Duplicate envelopes return:

ALREADY_APPLIED

Duplicate envelopes must never:

• insert additional events
• mutate booking_state

---

# External Event Boundary

External systems never write directly to the database.

External integrations must pass through the **adapter ingestion boundary**.

Pipeline:

External System
→ Adapter Layer
→ Payload Normalization
→ Validation
→ Canonical Envelope
→ Ingest API
→ apply_envelope
→ event_log
→ booking_state projection

The adapter layer acts as an **anti-corruption boundary**.

External payload semantics must never leak into the canonical domain model.

---

# Phase History

Phase 22 was just completed.

Phase 22 introduced the **OTA ingestion boundary and adapter layer**.

Implemented components:

src/adapters/ota/

base.py
bookingcom.py
registry.py
schemas.py
validator.py
service.py

Capabilities added:

• external channel adapter layer
• payload normalization
• canonical validation
• canonical envelope conversion
• deterministic idempotency propagation
• ingestion through canonical ingest API

External events are now isolated from the internal event model.

External payloads cannot bypass the canonical apply gate.

---

# Current Phase

Current phase:

Phase 23 — External Event Semantics Hardening

Specification file:

docs/core/phase-23-spec.md

Read it carefully before proposing implementation steps.

---

# Why Phase 23 Exists

Phase 22 solved the **transport boundary problem**.

External payloads can now safely enter the system.

However external systems introduce **semantic risks** that transport idempotency alone cannot solve.

Examples:

• duplicate business events with different request IDs
• out-of-order OTA events
• inconsistent provider semantics
• invalid booking lifecycle transitions

Phase 23 focuses on protecting the **domain semantics**.

---

# Phase 23 Objectives

1. Business idempotency hardening

Transport idempotency already exists.

Phase 23 must define how to detect duplicate **business events** even when request IDs differ.

Example:

Same reservation created multiple times by OTA retries.

---

2. Booking lifecycle validation

Define legal transitions such as:

BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED

Reject invalid transitions deterministically.

---

3. Ordering tolerance rules

External systems may deliver events out of order.

Example:

BOOKING_CANCELED arrives before BOOKING_CREATED.

Phase 23 must define deterministic handling rules.

This phase may define policy before implementing full reconciliation.

---

4. Adapter semantic normalization discipline

Channel adapters must guarantee canonical semantics.

Examples:

• date normalization
• reservation identity normalization
• provider status mapping
• timezone normalization

---

# Hard Constraints

The following system invariants must never be violated:

event_log remains the only source of truth

booking_state remains projection-only

apply_envelope remains the only allowed write gate

external systems must never write directly to event_log

replay safety must remain preserved

The application layer must never synthesize internal projection events.

STATE_UPSERT is DB-generated only.

---

# Expected Behavior From You

1. Do not redesign the architecture.
2. Do not introduce new persistence paths.
3. Do not bypass the apply_envelope gate.
4. Work strictly inside the adapter and validation layers when needed.
5. Follow the phase specification.

If something is unclear, ask a precise architectural question before proposing implementation.

---

# First Task

Start by reading:

docs/core/phase-23-spec.md

Then propose a **minimal implementation plan for Phase 23** that follows the canonical architecture.

The plan must:

• respect all invariants
• remain deterministic
• not introduce additional write paths
• keep replay safety intact

Provide the plan before writing code.
