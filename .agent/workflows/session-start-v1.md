---
description: Session initialization protocol — how to start every new work session on iHouse Core. Invoke with /session-start.
---

# Session Start Protocol

When the user invokes `/session-start`, follow **every step below in order** before writing any code.

## Language Rules (always active)

- **Chat:** Always respond in **Hebrew only**.
- **Code:** All code, comments, docstrings, variable names, log messages, and error messages must be in **English only**.
- **Never** put Hebrew inside code. Code must stay clean and English-only.

---

## Step 1 — Read the Handoff Document

// turbo
1. Scan `releases/handoffs/` and find the handoff file with the **highest phase number** in its name.
2. **Report to the user** which handoff you found (e.g., "Starting from handoff Phase-464") so they can confirm it's the right one.
3. Read the handoff and understand: what was built, what was verified, what is still open, what are the risks, and what is the recommended next step.

## Step 2 — Read BOOT Protocol

// turbo
4. Read `docs/core/BOOT.md`.
5. Internalize the working rules, naming conventions, documentation requirements, and compliance expectations.

## Step 3 — Full Architect-Level System Review

Do NOT jump into the next phase number. First, build a complete mental model:

// turbo
5. Read all canonical core documents:
   - `docs/core/current-snapshot.md`
   - `docs/core/phase-timeline.md`
   - `docs/core/construction-log.md`
   - `docs/core/roadmap.md`
   - `docs/core/work-context.md`
   - `docs/core/live-system.md`

// turbo
6. Cross-check the documents against the actual codebase, DB schema, and Supabase state.
7. Verify that everything already built is: documented correctly, historically accurate, and architecturally sound.

## Step 4 — Propose Next 20 Phases

8. Based on the full system understanding (NOT just the next phase number), write a concise work note proposing the next 20 phases to build.
9. For each phase include: phase number, name, one-line description, and why it comes in this order.
10. Present the 20 phases to the user for review. **Do NOT proceed to execution until the user approves.**

> [!IMPORTANT]
> If during the review you believe the order should change or different phases are needed, propose alternatives. This is a guide, not a rigid contract.

---

## Ongoing Rules (apply throughout the entire session)

### Rule 1 — Quick Summary Every 5 Phases

After every 5 completed phases, pause and give the user a **short in-chat summary**:
- What was built
- What changed
- What was closed
- What the next phases are

This is NOT a dedicated phase — just a brief checkpoint message inside the chat before continuing.

### Rule 2 — Phase 20 Is Always the Final Audit Phase

Phase 20 (the last of the 20 planned phases) is **always** dedicated to:

- [ ] Run the full test suite
- [ ] Verify code ↔ documentation alignment
- [ ] Align all canonical documents (`current-snapshot`, `phase-timeline`, `construction-log`, `roadmap`, `work-context`, `live-system`)
- [ ] Align all protocols
- [ ] Full BOOT protocol compliance check
- [ ] Update all core, state, protocol, and work documents — zero gap between built and documented
- [ ] Create a clean handoff document in `releases/handoffs/` covering:
  - What was built
  - What was verified
  - What is still open
  - What are the risks
  - Recommended next step

> [!IMPORTANT]
> Phase 20 is never just code. It closes: code, system truth, docs, protocols, tests, AND handoff.

### Rule 3 — UI Proof Every 1–3 Phases (MANDATORY)

After completing every phase, or at most every 2–3 phases:
- Stop coding.
- Open the application in a browser.
- Navigate to the affected page/surface.
- Capture a screenshot or walkthrough proving the change is visible and working.
- If the change is schema-only or API-only, explicitly state: "No UI surface yet — schema/API only."

**No more invisible progress.** If something was built, the user must SEE it.

> [!CAUTION]
> Do NOT declare a phase complete without either:
> (a) showing UI proof, or
> (b) explicitly documenting why UI proof is not applicable.

### Rule 4 — Architecture-Aware Build Process

Before building ANY new feature or surface:
1. Check `.agent/architecture/` for an existing spec
2. Check `docs/vision/product_vision.md` for product-level requirements
3. Check `docs/vision/master_roadmap.md` for DB/API definitions
4. Extract existing definitions first — do NOT reinvent what was already designed

**Build FROM the docs, not around them.**

### Rule 5 — Docs-First Alignment Before Major Wave Changes

Before starting a new wave or switching significant direction:
1. Review all architecture docs for missed requirements
2. Cross-reference against actual code/UI to identify gaps
3. Present a gap analysis to the user
4. Get explicit approval before proceeding

**No wave starts without a full picture of what exists vs. what's needed.**

### Rule 6 — Gap Prevention Checklist

At every Phase 20 audit, and before any major wave change, run this checklist:

- [ ] Every file in `.agent/architecture/` reviewed for unsurfaced requirements
- [ ] Every table in Supabase checked: has data? has API? has UI?
- [ ] Every frontend page checked: shows real data? or empty/stub?
- [ ] `docs/vision/system_vs_vision_audit.md` updated with current gap %
- [ ] Deferred items registry in `work-context.md` reviewed and updated

### Rule 7 — PMS Layer Status

The PMS / Channel Manager layer (Guesty, Hostaway adapters, PMS Connect UI) is **DEFERRED, NOT DISCARDED**.
- All PMS code, schemas, and docs remain in the codebase
- PMS is deferred behind the Operational Core wave (Property Detail → Staff → Dashboards → Check-in → Cleaner → Problem Reports)
- PMS resumes AFTER the "One Property, End-to-End" checkpoint
- Do NOT delete PMS code or docs. Do NOT deprioritize it permanently.

---

## Summary

```
/session-start flow:
  1. Read handoff → understand current state
  2. Read BOOT → internalize rules
  3. Full system review → verify docs vs reality
  4. Propose 20 phases → get user approval
  5. Build phases 1–19
  6. Quick summary every 5 phases (in-chat, not a phase)
  7. UI proof every 1–3 phases (mandatory)
  8. Architecture-first: check .agent/architecture/ before building
  9. Phase 20 = full audit + doc alignment + gap prevention checklist + handoff
```

## Permanent Project Principles

1. **Architecture-aware product build** — always check existing specs before building
2. **PMS deferred, not discarded** — resumes after Operational Core
3. **UI walkthrough checkpoints every 1–3 phases** — no invisible progress
4. **Docs-first alignment before major wave changes** — gap analysis required
5. **No more invisible progress without surfaced product proof**
