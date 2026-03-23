---
description: Session initialization protocol V2 — how to start every new work session on iHouse Core. Invoke with /session-start.
---

# Session Start Protocol

When the user invokes `/session-start`, follow **every step below in order** before writing any code.

## Language Rules (always active)

- **Chat:** Always respond in **Hebrew only**.
- **Code:** All code, comments, docstrings, variable names, log messages, and error messages must be in **English only**.
- **Never** put Hebrew inside code. Code must stay clean and English-only.

---

## Step 0 — Versioning This Protocol First

Before anything else:

1. Go to the `workflows/` directory.
2. If the previous protocol file currently exists as `session start.md`, rename it to:
   - `session start V1.md`
3. Save the new protocol from this session as:
   - `session start V2.md`
4. Do **not** overwrite the previous version.
5. Going forward, preserve old weekly protocol versions instead of replacing them.

## Step 1 — Read the Latest Handoff First

1. Scan `releases/handoffs/` and find the handoff file with the **highest phase number** in its name.
2. Report to the user which handoff you found.
3. Read the handoff fully and extract:
   - what was built
   - what was verified
   - what is still open
   - what is risky
   - what was deferred
   - what the recommended next step was

## Step 2 — Read BOOT Protocol

4. Read `docs/core/BOOT.md`.
5. Internalize all working rules, naming conventions, documentation requirements, audit expectations, and compliance rules.

## Step 3 — Read the Canonical System State

Do NOT jump into implementation yet.

6. Read all canonical core documents:
   - `docs/core/current-snapshot.md`
   - `docs/core/phase-timeline.md`
   - `docs/core/construction-log.md`
   - `docs/core/roadmap.md`
   - `docs/core/work-context.md`
   - `docs/core/live-system.md`

7. Build a full architect-level understanding of the current system:
   - what truly exists
   - what is surfaced in UI
   - what is only partially built
   - what is documented but not yet surfaced
   - what is inconsistent across code, docs, DB, and UI

## Step 4 — Read the Identity / Role / Surface Model

8. Before proposing phases, read all current canonical product and architecture materials relevant to identity, roles, permissions, and surfaces.
9. Internalize the current system model:
   - Public / Identity-only
   - Submitter / Prospect / Intake
   - Worker roles
   - Operational Manager
   - Owner
   - Admin
   - Super Admin
   - Guest / Stay portal
10. Treat routing as:
   `Identity -> Context / Membership -> Role -> Permissions -> UI Surface`
11. Never reason about access based on login method alone.

## Step 5 — Full Surface Review Before Planning

12. Review the actual product surfaces before proposing the next phases.
13. Build a system-wide surface map covering all relevant user types and their current pages, including where applicable:
   - Public landing and auth entry
   - Get Started / intake flow
   - My Properties
   - My Profile / Settings
   - My Pocket
   - Worker mobile surfaces
   - Cleaner
   - Maintenance
   - Check-in
   - Check-out
   - Combined Check-in + Check-out
   - Operational Manager
   - Owner portal
   - Admin surfaces
   - Guest / Current Stay portal

14. For each surface, identify:
   - what already exists
   - what is missing
   - what is stubbed
   - what is inconsistent
   - what is duplicated
   - what should be reused instead of rebuilt
   - what depends on another unfinished surface or permission rule

15. Report these gaps clearly to the user before execution, especially anything important that appears forgotten, inconsistent, or still unresolved.

## Step 6 — Cross-Check Docs vs Code vs DB vs UI

16. Cross-check the documents against the actual codebase, DB schema, Supabase state, and current UI.
17. Verify that existing work is:
   - documented correctly
   - historically accurate
   - architecturally coherent
   - connected end-to-end
   - surfaced to the right user type

18. Explicitly call out:
   - built but not surfaced
   - surfaced but not connected
   - documented but not built
   - built in one surface but missing in sibling surfaces
   - permission logic that does not match the product model

## Step 7 — Propose the Next 10 Phases

19. Based on the full system review, propose the next **10 phases**.
20. The proposed phases must follow the real product logic and existing architecture, not just the next unused number.
21. For each phase include:
   - phase number
   - phase name
   - one-line scope
   - why it comes in this order
   - which surface / user type it serves
   - what dependency it closes

22. Prefer ordering phases by real product flow and dependency chain, especially across user surfaces.
23. Present the 10 phases to the user for approval.
24. Do NOT begin execution until the user approves the plan.

> [!IMPORTANT]
> If the correct order differs from what the user or previous notes implied, explain why and propose the better order.

---

## Ongoing Rules (apply throughout the entire session)

### Rule 1 — Quick Summary Every 5 Phases

After every 5 completed phases, pause and give the user a short in-chat summary:
- what was built
- what changed
- what was closed
- what remains open
- what the next phases are

This is not a phase. It is a checkpoint message.

### Rule 2 — Phase 10 Is Always the Final Audit Phase

The last planned phase in the current work batch is always the final audit phase.

It must include:
- run the full relevant test suite
- verify code ↔ documentation alignment
- verify product model ↔ permissions ↔ surfaces alignment
- align canonical documents
- align protocols
- verify BOOT compliance
- update the handoff in `releases/handoffs/`

The final phase never closes code only.
It closes code, UI truth, docs, protocols, tests, and handoff.

### Rule 3 — UI Proof Every 1–3 Phases (MANDATORY)

After every phase, or at most every 2–3 phases:
- stop coding
- open the affected application surface in a browser
- navigate through the changed flow
- capture proof that the change is visible and working

If the work is schema-only or API-only, explicitly state:
`No UI surface yet — schema/API only.`

Do not declare a phase complete without either UI proof or an explicit explanation why UI proof does not apply.

### Rule 4 — Architecture-Aware Build Process

Before building any new feature, flow, or surface:
1. check `.agent/architecture/` for existing specs
2. check `docs/vision/product_vision.md`
3. check `docs/vision/master_roadmap.md`
4. extract existing definitions first
5. reuse existing built flows and components wherever possible

Build from the existing architecture and surfaced product reality.
Do not reinvent what already exists.

### Rule 5 — Surface-First Gap Analysis Before Major Direction Changes

Before starting a new wave or changing direction:
1. review all relevant architecture docs
2. review all affected UI surfaces
3. compare docs vs code vs DB vs UI
4. present a gap analysis to the user
5. get approval before proceeding

No major wave starts without a full picture.

### Rule 6 — Gap Prevention Checklist

At every major audit, and before any major surface wave, run this checklist:

- [ ] every relevant file in `.agent/architecture/` reviewed
- [ ] every relevant table checked for real usage, API connection, and UI presence
- [ ] every relevant frontend page checked for real data vs placeholder/stub
- [ ] every user type checked against its intended surface model
- [ ] sibling surfaces checked for missing parity
- [ ] deferred items in `work-context.md` reviewed and updated

### Rule 7 — Identity and Surface Continuity Rules

Never break these product rules:

- access is determined by identity, context, role, permissions, and surface
- login method is not permission
- the same person must remain the same identity across linked auth methods
- Submitter → Owner must preserve identity continuity
- Operational Manager is not just another worker
- Owner is a distinct surface, not a hidden Admin or an extended Submitter
- Guest is a temporary stay context, not a standard business user
- profile/settings must remain a shared identity/account layer across main user types

### Rule 8 — Current Priority Focus

The current focus is not broad PMS expansion.

The current focus is:
- system-wide review of user surfaces
- closing UI and routing gaps across all main user types
- verifying role → permission → surface correctness
- reusing and reconnecting existing flows instead of rebuilding
- moving through the product in a logical end-to-end order

Priority user/surface areas currently include:
- Public
- Submitter
- My Properties
- My Profile / Settings
- My Pocket
- Worker roles
- Operational Manager
- Owner
- Admin
- Guest / Current Stay portal

### Rule 9 — Booking Source Reality: iCal First, PMS/BMS Later

The PMS / Channel Manager / BMS layer is deferred, not discarded.

Current booking-source truth:
- the system is currently operating in **iCal-first mode**
- booking ingestion and booking identity currently come primarily from **iCal**
- until deeper PMS/BMS integrations are completed, treat iCal as the active operational booking source
- do not plan new flows as if Guesty / Hostaway / PMS adapters are already the live booking truth
- any guest, stay, check-in, portal, or operational booking surface must respect this current iCal-first reality

PMS / BMS rules:
- keep PMS/BMS code, schemas, and docs
- do not delete or rewrite them unnecessarily
- do not treat them as the current main wave
- resume PMS/BMS expansion after the current operational and user-surface priorities are stable
- when PMS/BMS work resumes, verify how it will coexist with or replace the current iCal-first flow

---

## Summary

```text
/session-start flow:
  1. Version the protocol in workflows (preserve old version, save new one as V2)
  2. Read latest handoff
  3. Read BOOT
  4. Read canonical core docs
  5. Read identity / role / surface model
  6. Review all existing user surfaces
  7. Cross-check docs vs code vs DB vs UI
  8. Report gaps and unresolved risks
  9. Propose 10 phases
  10. Get user approval
  11. Execute with UI proof checkpoints
  12. Final phase = audit + alignment of all protocols and docs + and ask user if he like to get the handoff now
```