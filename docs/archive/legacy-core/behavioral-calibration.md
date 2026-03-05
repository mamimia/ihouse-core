# iHouse Core — Behavioral Calibration

## Working Profile
Owner preferences:
fast iteration
no repetition
no wandering
deterministic progression
clarity over cleverness
minimal steps with maximum structural gain
no architectural drift

## Execution Expectations
Always state current Phase and sub block.
Commands first.
Short explanation after commands.
Wait for output before proceeding.
Never assume structure without inspecting the repo.
Protect system integrity before feature expansion.

## Structural Expectations
No hidden refactors.
No boundary mixing.
Engine first.
Docs evolve with architecture.
Backups and git sync are mandatory.

## Canonical Execution Mindset
Treat the database as the mutation authority.
Do not invent truth in the application layer.
Prefer live verification:
event_log rows
booking_state rows
apply_envelope status codes

## Closure Discipline
A Phase is not closed until:
phase timeline is appended
core docs are updated to match the locked behavior
no code-doc semantic drift remains

## Locked Semantic Rule (Phase 18)
Canonical availability predicate:
A booking is considered active for overlap checks iff status IS DISTINCT FROM 'canceled'.
NULL is intentionally treated as active for legacy rows (forward-only, no backfill).

Forward-only writes:
BOOKING_CREATED always writes status = 'active'
BOOKING_CANCELED sets status = 'canceled' and bumps version under row lock
