# PKA-Bridge

## What This Is

PKA-Bridge is a read-only analytical workspace created during the initial system audit of the iHouseCore repository.

Its purpose is to hold findings, maps, questions, and role analyses derived from reading the real repository — not from summaries, handoffs, or latest-state documents.

All content here was produced by direct inspection of source code, migration files, router definitions, service logic, UI pages, and documentation.

## What This Is Not

- It is not part of the product.
- It is not an implementation plan.
- It is not a work log or phase tracker.
- It does not replace or supersede any existing documentation.
- Nothing in this folder affects the running system.

## Structure

```
PKA-Bridge/
  README.md            — This file
  READING_LOG.md       — Ordered record of what was read and when
  SYSTEM_MAP.md        — Truthful map of the repository as it exists today
  QUESTIONS_FOR_OWNER.md — Only questions that require owner input to resolve
  ROLES/               — One file per proven or strongly inferred role
  Owner_Inbox/         — Messages or findings directed to the repository owner
  Team_Inbox/          — Messages or findings directed to the wider team
```

## Boundary Rule

Writing is permitted only inside PKA-Bridge.
Reading is permitted across the entire repository.
No product files are modified.
No implementation work is started here.
