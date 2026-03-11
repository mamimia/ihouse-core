# iHouse Core — Governance

## Purpose

This document defines how humans and AI collaborate on iHouse Core without causing architectural drift.

## Authority

- This file is governance, not product truth.
- Immutable core docs are never edited unless the user explicitly requests a tiny wording change:
  - docs/core/vision.md
  - docs/core/system-identity.md
  - docs/core/canonical-event-architecture.md
- History docs are append only:
  - docs/core/phase-timeline.md
  - docs/core/construction-log.md

## Session start protocol

At the start of each chat, the user provides docs/core/BOOT.md only.

The assistant must:
1. Read the docs listed in BOOT in the declared order.
2. State:
   - Current Phase
   - Last Closed Phase
   - Single next objective
3. Propose an execution plan in small steps.

## Execution discipline

- Prefer explicit commands and deterministic steps.
- Avoid large, sweeping refactors without a verification gate.
- When changing code, prefer a restart or reload to avoid stale code effects.
- When proposing changes, provide:
  - scope
  - expected impact
  - verification method

## Master reload rule

Reload is the act of re establishing correct context for the current work session.

Reload sources are limited to:
- docs/core/BOOT.md
- docs/core/current-snapshot.md
- latest sections of phase-timeline and construction-log

Do not reload by pasting many documents. If more context is needed, the assistant must request specific files by path.

## Continuity directive

Continuity means:
- keep working from the current phase objective
- do not reopen closed phases unless the user explicitly requests it
- do not change immutable core docs
- do not rewrite history

If the user opens a new chat mid work, the assistant must:
- restate objective
- restate last verified checkpoint
- propose the next smallest action

## Project spine protocol

The project spine is the stable mental model:
- canonical invariants
- canonical write gate
- canonical read model
- deterministic rebuild guarantees

If a proposal violates the spine, reject it and propose an alternative.

## Behavioral calibration

The assistant must:
- be direct
- avoid confirmation bias
- challenge assumptions
- prefer truth over agreement
- keep explanations short and operational

## AI governance

The assistant must:
- never hallucinate repo state
- never claim tests passed unless shown output
- never create new authority sources that conflict with docs
- always treat docs as authoritative

## End of phase checklist

When the user declares a phase closed:
1. Append to phase-timeline (append only)
2. Append to construction-log (append only)
3. Update current-snapshot (minimal updates only)
4. Archive any phase spec docs under docs/archive/phases

## Phase 20 Stabilization Directive (Supabase Truth Protocol)

Supabase is the canonical source of truth.

Before any architectural documentation is edited, a Supabase Truth Pack MUST be produced and committed under artifacts/supabase/.

The Truth Pack includes:
1) schema.sql (public schema)
2) functions.sql (public functions)
3) registries export (event_kind_registry and event_kind_versions)
4) policies snapshot (RLS or policy definitions if present)

Documentation edits must be minimal and scoped:

- phase-timeline.md is append-only
- construction-log.md is append-only
- immutable core docs must never be rewritten
- no full-file overwrites unless the file is explicitly marked as overwrite-safe

Phase 20 objective:

Eliminate drift between documentation and the live Supabase system.

All architectural reasoning must be verified against the Supabase schema and registry state before being accepted as system truth.

This phase establishes a repeatable extraction workflow so that future AI collaboration cannot hallucinate architecture that does not exist in the database.


## Supabase artifacts refresh rule

If a phase includes any change to the Supabase database schema or functions, refresh Supabase artifacts before closing the phase:

./scripts/update_supabase_artifacts.sh

This must update:
- artifacts/supabase/schema.sql
- artifacts/supabase/schema.hash.txt
- artifacts/supabase/registries.sql (if registry tables exist)


## Work Context Protocol

The file `docs/core/work-context.md` captures the current active work state
inside an open phase.

Rules:

- It is **not** an architectural document.
- It represents temporary execution context for the current phase.
- It may be overwritten during the phase.
- When a phase is closed, the file must be reset.

The purpose of this file is to allow a new chat session to resume work
without reconstructing the entire conversation history.

Authority:

work-context.md never overrides canonical documents.

Canonical authority remains:

vision.md  
system-identity.md  
canonical-event-architecture.md  
current-snapshot.md

---

## Branding Boundary — Irrevocable

**inside = iHouse Core** — all internal system names, file names, module names, env vars, loggers, OpenAPI metadata, router names, test files, technical documentation, archives.

**outside = Domaniqo** — all user-facing surfaces: UI, login, sidebar, PDFs, emails, marketing, graphics, guest-facing portals.

No internal system artifact may be renamed to Domaniqo. This rule is non-negotiable.

See `docs/core/brand-handoff.md` § Hard Branding Boundary for the full policy.

