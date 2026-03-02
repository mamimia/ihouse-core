# Project Spine Protocol

## Trigger Word

The canonical session trigger is:

SPINE

If context is unclear or drift is suspected, type SPINE and reload context from the repository.

---

## Goal

Build projects with a single source of truth, zero drift, and deterministic context loading for any new chat session.

---

## Core Rules

1. Repo is the only source of truth.
2. Docs evolve with architecture.
3. Terminal-first workflow.
4. Read full file before modifying.
5. Overwrite full files, never patch blindly.
6. Limit commands per step.
7. Backup and Git sync before structural changes.
8. Every session must be reloadable deterministically.

---

## Required Core Documents

vision.md
system-identity.md
live-system.md
current-snapshot.md
construction-log.md
canonical-event-architecture.md
collaboration-rules.md
behavioral-calibration.md
session-anchor.md
project-spine-protocol.md

---

## Phase Completion Protocol

A phase is not closed unless:

1. Backup created
2. git status clean
3. git add .
4. git commit with phase label
5. git push
6. Docs updated to reflect reality
7. Deterministic validation executed
8. Phase closure written in construction-log.md

---

## SPINE Session Reload Procedure

Run:

sed -n '1,200p' docs/core/current-snapshot.md
sed -n '1,200p' docs/core/system-identity.md
sed -n '1,200p' docs/core/canonical-event-architecture.md
sed -n '1,200p' docs/core/construction-log.md

Then continue from the latest locked Phase.

---

## Operating Principle

Chat memory is not authoritative.
Repository state is canonical.
