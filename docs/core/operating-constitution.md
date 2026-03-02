# iHouse Core – Operating Constitution

---

## Language Rules

All explanations must be written in Hebrew.
All code must be written in English.
No Hebrew is ever allowed inside code blocks.

The system is built as a global SaaS product.

Clarity over verbosity.
No ambiguity.
No mixed execution environments.

---

## Architectural Discipline

1. No change without architectural awareness.
2. No local fix without systemic analysis.
3. Every technical decision must respect deterministic design.
4. Financial-grade integrity over convenience.
5. Drift between code, DB, and documentation is considered architectural failure.
6. If inconsistency is detected, execution must stop immediately.

---

## Code Discipline

1. No file modification before full file inspection via terminal.
2. Entire file must be printed before modification.
3. Only full-file overwrite edits are allowed.
4. No partial edits.
5. No speculative code.
6. No guessing.
7. No silent assumptions about DB structure.

---

## Execution Environment Clarity

1. SQL commands must be explicitly marked for SQL editor.
2. Bash commands must be explicitly marked for terminal.
3. No mixing SQL syntax inside bash context.
4. No environment ambiguity allowed.

---

## Terminal First Policy

1. Prefer terminal execution.
2. Maximum two commands per step.
3. Each step must be independently verifiable.
4. Always wait for output before proceeding.
5. No long procedural chains.
6. Each step must begin with:

Phase X – Sub-Block Name

---

## Financial-Grade Rule

1. No duplicate writes.
2. No non-atomic idempotency.
3. No hidden state mutation.
4. All persistence must be replayable.
5. Determinism is mandatory, not optional.

---

## Context Discipline

When opening a new chat, or when drift is suspected, type:

SPINE

Then load:

docs/core/current-snapshot.md
docs/core/system-identity.md
docs/core/canonical-event-architecture.md
docs/core/construction-log.md

Repository state is the single source of truth.
Chat memory is not authoritative.

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
8. Hard invariants verified.
9. Official Phase closure declared.

No architectural modification is allowed without synchronized documentation update.

---

## Collaboration Rule

ChatGPT is not a passive executor.

If architectural inconsistency, drift, or weak reasoning is detected,
execution must pause and be challenged.

Agreement is not mandatory.
Architectural correctness is mandatory.

---

## SaaS Standard

No temporary hacks.
No experimental shortcuts.
Production-grade only.
Determinism over convenience.
Financial integrity over speed.

