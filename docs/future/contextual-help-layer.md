# Future UI — Contextual Help Layer for iHouse Core

**Status:** Future / Not scheduled
**Author:** Product direction note
**Category:** UI/UX Product Quality

---

## Why this matters

iHouse Core is growing into a complex product.
Financial states, confidence tiers, escalation logic, reconciliation exceptions, RevPAR computation, lifecycle projections — these are not simple concepts.

Without guidance, operators, owners, and workers will hesitate, misread, or avoid features.
The contextual help layer prevents that — without making the interface heavy.

---

## Core principle

> The UI stays clean by default. Help appears only where it is genuinely needed.

Progressive disclosure: more explanation only when requested.
No "question marks everywhere" design.

---

## Four layers of help

| Layer | Format | Use case |
|-------|--------|----------|
| 1 | **Simple tooltip** | 1 line. Icon buttons, labels, status chips, terminology |
| 2 | **Rich toggletip / popover** | 2–4 lines. Financial logic, confidence tiers, escalation, reconciliation |
| 3 | **Visible helper text** | Always visible. Forms, destructive actions, settings |
| 4 | **Global help toggle** | System-level on/off. "Show guidance" / "Hide guidance" |

The global toggle means new users can leave help on while experienced users can work clean.

---

## Where to concentrate help (priority)

**High priority** — complex interpretation needed:
- Payment lifecycle status
- Reconciliation inbox / flags
- Owner statement confidence
- RevPAR and epistemic tier A/B/C
- Financial status cards
- Conflict center
- Escalation rules and SLA logic
- Worker issue flow / acknowledgement
- Delegated permissions
- Provider health monitor
- Operation exceptions / admin settings

**Low priority** — do not explain the obvious:
- Save, Cancel, Edit
- Simple lists
- Standard navigation
- Clearly named buttons

---

## Role-aware help depth

| Role | Help style |
|------|-----------|
| Admin | System and governance explanations |
| Manager | Operational + exception-based explanations |
| Worker | Short, action-oriented only |
| Owner | Plain business language — no technical jargon |
| Guest | Minimal or none, unless onboarding |

---

## Help copy rules

Help copy must be:
- Short
- Specific
- Action-aware
- Not academic or generic

**Good:**
- *"Reconciliation shows bookings whose local state no longer matches the provider."*
- *"Confidence C means the number is incomplete and should be reviewed before sharing."*
- *"Escalation starts only if the task is still unacknowledged after the required SLA window."*

**Bad:**
- *"This is reconciliation."*
- *"This button opens settings."*
- *"Use this feature to manage data."*

---

## Interaction rules

| Platform | Rule |
|----------|------|
| Desktop | Tooltip on hover + focus. Rich help on click. |
| Mobile | Tap-based only. No hover dependency. Short + dismissible. |

---

## Accessibility

- Works with keyboard navigation
- Available on focus, not hover only
- Dismissible
- Does not block task flow
- Does not overload the first screen
- Never repeats obvious text

---

## Implementation requirements (when UI phase opens)

When the UI phase begins, the contextual help system must be treated as a **real product capability**, not ad-hoc tooltips. That means:

1. Define a **help pattern library** (which component for which case)
2. Define where **simple tooltips** are used
3. Define where **rich popovers** are used
4. Define where **helper text must stay visible**
5. Define the **global help toggle** and persistence (user preference)
6. Define **role-aware help depth** per screen
7. Define **writing rules** for all help content

---

## Notes from engineering perspective

A few additions worth keeping in mind when this gets implemented:

- Help content should be **data-driven** where possible (not hardcoded per component).
  A central `help_registry.json` or equivalent per-route help config makes content updates safe without UI rebuilds.

- **Epistemic tier explanations** (A/B/C) are the single most important help area.
  Every screen showing confidence, RevPAR, or financial status MUST have a tooltip.
  This is where users will most need guidance.

- **SLA and escalation views** are the second most important.
  "Unacknowledged" and "Escalated" states are non-obvious to workers.

- The global help toggle state should be **persisted per user** (not device-level).
  New users = default ON. Users who disable it should not have it re-enable on every login.

- On mobile, the help layer must compete with limited space.
  Tap-to-expand is the only viable pattern. Keep tooltips under 15 words on mobile.

---

## Summary

iHouse Core should eventually include a smart contextual help system that:
- keeps the UI clean
- reduces confusion on complex financial and operational screens
- supports learning without dominating the interface
- knows who the user is and adjusts accordingly
- explains meaning, not just labels

This is a future improvement, not a scheduled task.
It should be revisited when the frontend / UI phase opens.
