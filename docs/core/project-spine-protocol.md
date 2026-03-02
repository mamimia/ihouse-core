# Project Spine Protocol

## Trigger Word
SPINE

SPINE is incomplete without terminal output confirmation.

## Authority
Repository state is canonical.
Chat memory is not authoritative.

## SPINE Reload Commands
sed -n '1,260p' docs/core/current-snapshot.md
sed -n '1,260p' docs/core/system-identity.md
sed -n '1,260p' docs/core/canonical-event-architecture.md
sed -n '1,260p' docs/core/construction-log.md

## Core Rules
Read full file before modifying.
Overwrite full files only.
Prefer terminal execution.
Backup and git sync before structural changes.
Docs must evolve with code and DB.

## Phase Completion Protocol
Backup created
git status clean
git add
git commit with phase label
git push
Docs updated
Deterministic validation executed
Phase closure recorded in construction-log.md
