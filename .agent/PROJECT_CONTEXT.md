

# iHouse Core – System Project Context v1

## Current System State

Core engine is fully operational.

Components implemented and working:

* http_adapter (ThreadingHTTPServer)
* event_router
* skill_runner
* 4 skills:

  * state-transition-guard
  * booking-conflict-resolver
  * task-completion-validator
  * sla-escalation-engine

Smoke tests: PASS (all 4 flows)
HTTP /health: OK
POST /event: OK

No UI yet.
No persistent data layer yet.
All skills are deterministic and pure.

---

## Architectural Principles

1. event_router routes by `kind` → maps to skill
2. skill_runner executes skill subprocess with payload only
3. Each skill:

   * Reads JSON from stdin
   * Returns JSON only
   * No storage
   * No network
   * No randomness
4. http_adapter:

   * GET /health
   * GET /
   * POST /event

System is currently Core v1 (stateless simulation).

---

## What Is NOT Implemented Yet

* No database
* No persistence
* No real bookings/tasks storage
* No authentication
* No RBAC enforcement
* No production logging
* No UI framework

---

## Next Phase Roadmap (Strict Order)

Phase 1 – Contracts Stability

* Envelope validation inside event_router
* Consistent error schema
* Centralized error codes

Phase 2 – Data Layer

* Introduce SQLite
* Tables:

  * properties
  * bookings
  * tasks
  * users
* Replace pure simulation with state mutation

Phase 3 – First Real Flow

* Booking create
* Conflict detection
* Status update
* Artifact creation

Phase 4 – Admin Dashboard (API-driven)

* Summary endpoint
* Property list
* Open issues list

Phase 5 – UI Application

---

## Rules For Any New Chat

Do NOT:

* Re-explain basic architecture
* Ask what kind of project this is
* Suggest frameworks randomly
* Suggest UI before data layer

Assume:

* Core works
* Smoke works
* Contracts are defined
* We are moving to Phase 1 → Phase 2

If unsure:
Continue from Data Layer implementation.

---

## Current Immediate Goal

Implement strict envelope validation inside event_router
Then introduce SQLite state layer.

---

End of context.

---