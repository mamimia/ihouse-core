# iHouse Core — BOOT

This file is the only context you should need at the start of a new chat.

## Non negotiable authority rules

1. Repo docs win. If any message conflicts with these files, these files are the source of truth.
2. Do not edit immutable core docs unless the user explicitly asks for a tiny wording change.
3. Some docs are append only. Never rewrite past history.

## Document authority layers

### Layer A — Immutable Core (never edit)
- docs/core/vision.md
- docs/core/system-identity.md
- docs/core/canonical-event-architecture.md

### Layer B — Governance (editable, but only when explicitly requested)
- docs/core/governance.md

### Layer C — Current State (editable, tightly scoped)
- docs/core/current-snapshot.md
- docs/core/live-system.md
- docs/core/roadmap.md

### Layer D — History (append only, never rewrite)
- docs/core/phase-timeline.md
- docs/core/construction-log.md

## What to read first in this chat

Always read in this order:
1. Layer A (Immutable Core)
2. docs/core/governance.md
3. docs/core/current-snapshot.md
4. docs/core/live-system.md
5. docs/core/phase-timeline.md (only the latest section)
6. docs/core/construction-log.md (only the latest section)
7. docs/core/roadmap.md (only if planning is needed)

## How to behave in this chat

- Start by stating: current phase, last closed phase, and the single next objective you infer from current-snapshot.
- Ask only the minimum clarifying questions needed to execute the next objective.
- Prefer small, reversible steps.
- When proposing doc edits, always specify:
  file path
  exact change
  why it is allowed under authority rules

## Phase closure protocol (when user says a phase is closed)

Do these in order:
1. Append a new "Phase X — Closed" section to docs/core/phase-timeline.md (append only).
2. Append a short "Phase X closure" entry to docs/core/construction-log.md (append only).
3. Update docs/core/current-snapshot.md:
   - set Current Phase
   - set Last Closed Phase
   - update only the minimal invariants / pointers that actually changed
4. If there was any phase spec file, move it to docs/archive/phases/phase-X-spec.md

## Safety rails

- Never invent repository state.
- Never rewrite old history lines.
- Never downgrade invariants already declared as canonical.
- If anything is ambiguous, ask one concrete question, then proceed.
