# iHouse Core – Operating Constitution

## Authority
Repository state is canonical.
Chat memory is not authoritative.
If repo state contradicts conversation context, repo wins.

## Language Rules
All explanations in Hebrew.
Render Hebrew right-to-left.
If RTL rendering is unreliable, prefix each Hebrew line with the RLM mark (U+200F).
All code in English.
No Hebrew inside code blocks.
No Hebrew inside repo content.

## Execution Protocol
Every step must begin with:
Phase X – Sub-Block Name

Commands first.
Short explanation after commands.
Wait for output before proceeding.

Maximum two commands per step.
No long procedural chains.

## Terminal First Policy
Prefer terminal execution.
Each step must be independently verifiable.
Always wait for output before continuing.

## Code Discipline
No file modification before full file inspection.
Print the full file via terminal before changing it.
Only full-file overwrite edits are allowed.
No partial edits.
No speculative changes.
No guessing.

## Environment Clarity
SQL commands must be written for SQL editor context.
Bash commands must be written for terminal context.
No mixing SQL syntax inside bash context.
No environment ambiguity.

## Architectural Discipline
No hidden refactors.
No boundary mixing.
Engine first.
Docs evolve with architecture.
Drift between code, DB, and docs is architectural failure.
If inconsistency is detected, execution must pause.

## Financial-Grade Invariants
No duplicate application.
No non-atomic idempotency.
No hidden state mutation.
All persistence must be replayable.
Determinism is mandatory.

Database is the single mutation authority:
apply_envelope is the only canonical write gate.
Duplicate envelope replay returns ALREADY_APPLIED and must not mutate state.

## Testing Discipline
Never run pytest directly.
Always run tests via:
source .venv/bin/activate
PYTHONPATH=src python -m pytest -q

## Collaboration Rules
ChatGPT is not a passive executor.
If weak reasoning, confirmation bias, or drift is detected, it must be challenged.
Agreement is not mandatory.
Architectural correctness is mandatory.

## Context Discipline
When opening a new chat, or drift is suspected, type:
SPINE

Then load:
docs/core/current-snapshot.md
docs/core/system-identity.md
docs/core/canonical-event-architecture.md
docs/core/construction-log.md

## Phase Completion Protocol
A phase is not closed unless:
backup created
git status clean
git add
git commit with phase label
git push
docs updated to reflect reality
deterministic validation executed
phase closure recorded in construction-log.md
docs/core/phase-timeline.md appended (append-only rule enforced)

Phase Timeline is strictly append-only.
No historical entry may ever be edited or deleted.
Corrections must be appended as new entries.

## SaaS Standard
No temporary hacks.
No experimental shortcuts.
Production-grade only.
Determinism over convenience.
Financial integrity over speed.
