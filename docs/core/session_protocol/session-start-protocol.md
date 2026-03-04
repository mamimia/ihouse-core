# iHouse Core — Session Start Protocol

This document defines the mandatory procedure when a new chat session begins.

It prevents architectural drift and guarantees deterministic continuation.

--------------------------------------------------
SECTION 1 — AUTHORITY LOCK
--------------------------------------------------

Repository state is authoritative.

Chat memory is not authoritative.

If conversation context contradicts repository documents,
repository documents must be treated as the source of truth.

Never redesign architecture.

Never restart system design discussion.

Continue execution from the latest locked Phase.

--------------------------------------------------
SECTION 2 — RELOAD TRIGGER
--------------------------------------------------

If context is unclear, or a new chat is opened,
the user may type:

SPINE

When SPINE appears, the assistant must immediately reload system context.

--------------------------------------------------
SECTION 3 — MANDATORY FILE LOAD
--------------------------------------------------

The assistant must load and read the following files:

docs/core/current-snapshot.md
docs/core/system-identity.md
docs/core/canonical-event-architecture.md
docs/core/construction-log.md
docs/core/phase-timeline/phase-timeline.md

These files define the real system state.

No reasoning may occur before reading them.

--------------------------------------------------
SECTION 4 — PHASE DETECTION
--------------------------------------------------

After reading the files, the assistant must determine:

1) The last closed Phase
2) The currently open Phase (if any)
3) The architectural invariants already locked

Execution must resume strictly from this boundary.

--------------------------------------------------
SECTION 5 — EXECUTION RULES
--------------------------------------------------

Commands first.

Short explanation after commands.

Maximum two commands per step.

Wait for terminal output before continuing.

Never run pytest directly.

Tests must be executed via:

source .venv/bin/activate
PYTHONPATH=src python -m pytest -q

--------------------------------------------------
SECTION 6 — ARCHITECTURAL DISCIPLINE
--------------------------------------------------

The assistant must not:

introduce new architecture
rename canonical interfaces
change persistence authority
modify canonical invariants

If an inconsistency between code and docs is detected,
execution must stop immediately.

--------------------------------------------------
SECTION 7 — CONTINUATION MODE
--------------------------------------------------

After context reload,
execution continues strictly in deterministic implementation mode.

Allowed actions:

bug fixes
phase tasks
documentation alignment
verification commands

Disallowed actions:

architecture redesign
system rewrites
schema resets

--------------------------------------------------
END OF SESSION START PROTOCOL
--------------------------------------------------
