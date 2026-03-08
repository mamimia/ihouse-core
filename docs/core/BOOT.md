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
4. docs/core/work-context.md (if present)
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
4. docs/core/work-context.md (if present)
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
3. Update docs/core/current-snapshot.md
4. docs/core/work-context.md (if present):
   - set Current Phase
   - set Last Closed Phase
   - update only the minimal invariants / pointers that actually changed
4. If there was any phase spec file, move it to docs/archive/phases/phase-X-spec.md

## Safety rails

- Never invent repository state.
- Never rewrite old history lines.
- Never downgrade invariants already declared as canonical.
- If anything is ambiguous, ask one concrete question, then proceed.

## Operational discipline — enforced every phase, no exceptions

### Git push cadence
- Push to GitHub after every meaningful change.
- Do not accumulate more than one phase worth of work without pushing.
- Ideal cadence: every few minutes during active work, or after every significant file change.

### Spec file protocol

- Every phase must have a spec file: `docs/archive/phases/phase-X-spec.md`
- The spec is created at the start of the phase (or reconstructed at closure if the phase was discovery-only).
- When a phase closes, the spec must already exist in the archive. Do not close a phase without it.
- **Note:** Phase specs before Phase 65 use an older, shorter format. Do not rewrite them. History is read-only.

#### Canonical phase spec template (Phase 65+)

```markdown
# Phase N — Short Title

**Status:** Closed
**Prerequisite:** Phase N-1 (Short Title)
**Date Closed:** YYYY-MM-DD

## Goal

One paragraph. What this phase accomplishes and why.

## Invariant (if applicable)

Any new or pre-existing invariants that this phase enforces.

## Design / Files

| File | Change |
|------|--------|
| `path/to/file.py` | NEW / MODIFIED — one-line description |

## Result

**N tests pass, M skipped.**
Any side-effects or non-changes explicitly noted.
```


### ZIP protocol
- At the end of every closed phase, create: `releases/phase-zips/iHouse-Core-Docs-Phase-<N>.zip`
- The ZIP must include the entire `docs/core/` tree — no selective inclusion.
- Naming is always: `iHouse-Core-Docs-Phase-<N>.zip` (exact casing, no variation).
- **Location: always `releases/phase-zips/` — never the repo root.**
- The ZIP is committed and pushed as part of the phase closure commit.

### Tool pivot rule
- If a tool or approach fails twice, stop immediately.
- Do not retry the same approach a third time.
- List all available alternatives (CLI, MCP, REST, Python, browser) and pick the next best one.
- `supabase CLI` is always checked before browser automation for any DB operation.

### Context limit — handoff protocol
- When approaching ~80% of context window capacity, STOP all work immediately.
- Write a handoff file into `releases/handoffs/` with name: `handoff_to_new_chat Phase-<N>.md`
- **Location: always `releases/handoffs/` — never the repo root.**
- The handoff must include: current phase, last closed phase, next objective, key files, and any in-progress state.
- Notify the user explicitly: "Context at ~80% — writing handoff now."
- Do NOT wait until context is exhausted. Early handoff preserves quality.

### Read before edit
- For every EXISTING file: always view_file the full content before making any changes.
- Never overwrite blindly. Understand what is currently there, then make the minimal correct change.
- New files (create from scratch) are exempt from this rule.
