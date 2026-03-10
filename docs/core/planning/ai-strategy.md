# iHouse Core — AI Strategy

**Status:** Planning — Approved Direction
**Created:** 2026-03-11
**Author:** Product Direction (via user) + Architecture Assessment (Antigravity)
**Category:** System Architecture Direction

---

## Core Principle

> **The deterministic core is truth. AI is explanation, prioritization, recommendation, and drafting.**

iHouse Core is a deterministic property operations platform.
AI sits on top of it as an assistive layer — never replacing the canonical backbone.

| What the deterministic core owns | What AI provides |
|---|---|
| Booking state, event log, financial truth | Explanation of complex state |
| Permissions, availability, reconciliation | Prioritization of operator attention |
| Task lifecycle, SLA enforcement | Recommendations for next actions |
| Outbound sync, audit trail | Drafting of communications |

---

## What AI Should Do

### 1. Explain the system
Turn complex internal state into clear human explanations.
- Why this booking is risky
- Why this sync failed
- Why this statement has confidence B or C
- Why this provider is unhealthy
- What changed in an amendment history

### 2. Prioritize work
Help decide what deserves attention first.
- Top 5 urgent issues for the manager this morning
- Which failed syncs are most important
- Which financial exceptions should be reviewed first

### 3. Recommend actions
Suggest next-best actions — never silently take control.
- Suggest replaying a failed sync
- Suggest escalating a worker issue
- Suggest creating a maintenance task
- Suggest reviewing a partial-confidence financial item

### 4. Draft communication
Help write messages — never become the authority.
- Guest reply drafts
- Owner explanation drafts
- Worker instruction simplification
- Translation and tone adjustment

### 5. Summarize operations
Create fast, decision-ready briefings.
- 7AM manager briefing
- Property risk summary
- Sync health summary

---

## What AI Must Never Own

- Canonical booking state (`booking_state`, `event_log`)
- Financial truth (`booking_financial_facts`)
- Permissions or role assignments
- Availability blocking / unblocking
- Owner statement finalization without rule-based gates
- Outbound sync execution decisions

---

## AI Context Objects — Already Available

The system already exposes structured data that serves as AI context:

| Context Object | Existing API Surfaces |
|---|---|
| **Booking snapshot** | `GET /bookings/{id}` + `GET /financial/{id}` + `GET /amendments/{id}` + `GET /admin/outbound-log?booking_id=` |
| **Property snapshot** | `GET /properties/{id}` + `GET /availability/{property_id}` + `GET /properties/{id}/channels` |
| **Task snapshot** | `GET /tasks?property_id=` + `GET /worker/tasks` |
| **Financial snapshot** | `GET /financial/summary` + `GET /financial/by-property` + `GET /financial/lifecycle-distribution` |
| **Sync health snapshot** | `GET /admin/outbound-health` + `GET /health` |
| **Operations day snapshot** | `GET /operations/today` |

No new tables or infrastructure needed — the first AI features can be built as composition layers over existing APIs.

---

## Approval Model

| Risk | Example | Behavior |
|---|---|---|
| **Zero** | Explain a confidence tier, summarize a booking | Pure read — no action needed |
| **Low** | Draft a guest reply | Draft only, human sends |
| **Medium** | Suggest replaying a failed sync | Human approves, system executes |
| **High** | Any write to booking_state or financial tables | **Never** — AI cannot touch these |

---

## AI Action Schema

When AI suggests actions, they must be expressed as structured objects:

```python
AIAction = {
    "action_type": "REPLAY_SYNC",
    "target": {"booking_id": "...", "provider": "bookingcom"},
    "confidence": 0.85,
    "explanation": "Sync failed 3 times due to rate limiting. Window has expired.",
    "approval_required": True,
    "risk_level": "medium",
}
```

This aligns with `admin_audit_log` (Phase 171) event recording patterns.

---

## Audit Model

The system must record:
- What context AI received
- What AI suggested
- Who approved
- What action was taken
- What happened next

This follows the existing `admin_audit_log` append-only pattern.

---

## Priority Sequence

| Priority | Feature | Why First |
|---|---|---|
| **1** | Manager Copilot — Morning Briefing | Highest daily value, most data already available, clearest contract |
| **2** | Financial / Reconciliation Explainer | Strongest competitive differentiator, epistemic tiers already built for this |
| **3** | Guest Messaging Copilot — Draft Replies | High value, low risk, natural fit |
| **4** | Worker Copilot | Lower priority — worker surface is action-first; AI adds complexity where simplicity wins |
| **5** | Operations / Revenue Advisor | Advanced recommendations — later wave |

---

## Prerequisites Still Needed

1. **LLM selection and cost model** — which LLM, token costs, latency requirements, fallback when LLM unavailable
2. **Context window budgets** — how much data to send per query type
3. **Multi-language support** — Thai, English, Japanese, Spanish, Korean (matching OTA market coverage)
4. **PII boundaries** — AI context objects must follow `guest_profile` PII isolation pattern

---

## Suggested Phase Mapping

| Phase | Title | Effort |
|---|---|---|
| **220** | AI Strategy Document — Canonical Placement | S (this document) |
| **221** | AI Context Aggregation Endpoints | M |
| **222** | Manager Copilot v1 — Morning Briefing | M |
| **223** | Financial Explainer — Confidence + Reconciliation | M |
| **224** | Guest Messaging Copilot v1 — Draft Replies | M |
| **225** | AI Audit Trail | S |

---

## What to Avoid

| Anti-pattern | Why |
|---|---|
| AI pricing engine | Not aligned with current product stage |
| AI authority over owner statements | Destroys trust model |
| AI-driven permission management | Security risk |
| AI replacing sync logic | Deterministic system must execute |
| Smart-home sensor analytics | Different product category |
| Energy forecasting / digital twin | Far-future, different vertical |

---

## Relationship to Existing Documents

| Document | Relationship |
|---|---|
| `docs/future/contextual-help-layer.md` | **Complementary.** Covers in-UI explanation widgets (tooltips, popovers). AI strategy covers LLM-powered reasoning. Both needed, different layers. |
| `docs/core/planning/worker-communication-layer.md` | **Aligned.** Worker Copilot extends the worker communication vision with AI-assisted task simplification. |
| `docs/core/planning/ui-architecture.md` | **Aligned.** Manager Copilot enhances the 7AM Dashboard concept with AI narration. |

---

## Summary

iHouse Core should use AI to make its deterministic backbone **more understandable, more actionable, and more useful**.

AI should help the people using the system. It should not become the system itself.

*Document created: Phase 210 (2026-03-11). Product direction + architecture assessment.*
