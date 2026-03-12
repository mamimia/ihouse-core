# Phase 312 — Manager Copilot UI

**Status:** Closed
**Prerequisite:** Phase 311
**Date Closed:** 2026-03-12

## Goal

Build the manager-facing AI copilot interface with morning briefing.

## Files

| File | Change |
|------|--------|
| `ihouse-ui/app/manager/page.tsx` | MODIFIED — MorningBriefingWidget |
| `ihouse-ui/lib/api.ts` | MODIFIED — `getMorningBriefing()` + types |

## Widget Features

- Briefing text display (AI-generated or heuristic fallback)
- Action items list with CRITICAL/HIGH/NORMAL priority badges
- Context signal cards: check-ins, check-outs, cleanings, open tasks
- Language selector: EN, TH, JA
- LLM vs HEURISTIC source badge
- Loading skeletons, error handling

**Build exit 0, 19 pages.**
