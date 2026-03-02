# iHouse Core – Operating Constitution

## Language Rules

All explanations must be written in Hebrew.
All code must be written in English.
No Hebrew is ever allowed inside code blocks.

The system is built as a global SaaS product.

---

## Code Discipline

1. No file modification before full file inspection via terminal.
2. No speculative code changes.
3. Entire file must be printed before modification.
4. Only full-file overwrite edits are allowed.
5. No partial edits.
6. No guessing.

---

## Terminal First Policy

1. Prefer terminal execution.
2. Maximum two commands per step.
3. Always wait for output before proceeding.
4. No long procedural chains.
5. Each step must begin with:
   Phase X – Sub-Block Name

---

## Context Discipline

When opening a new chat, or when drift is suspected, type:

SPINE

Then load:

docs/core/current-snapshot.md
docs/core/system-identity.md
docs/core/canonical-event-architecture.md

No reliance on chat memory.

---

## Phase Discipline

A Phase cannot be closed unless:

1. Full backup created.
2. Git status verified.
3. git add .
4. git commit -m "Phase X closure"
5. git push
6. All docs/core files updated.
7. Deterministic replay validation executed.
8. Official Phase closure declared.

---

## Backup Policy

1. Automatic backup at end of every Phase.
2. Mandatory backup before structural changes.

---

## SaaS Standard

No temporary hacks.
No experimental shortcuts.
Production-grade only.
Determinism over convenience.
