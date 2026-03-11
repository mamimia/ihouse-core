# Phase 231 — Worker Task Copilot

## Goal

Extend the AI copilot layer to the worker persona. Given a `task_id`, the endpoint
assembles all context a field worker needs to execute the task: property access info,
guest details, recent task history at the property, and an AI-generated narrative.

## Invariants

- **Read-only**: Never writes to any table.
- **Best-effort context**: Booking and property lookups never raise — returns empty dict on miss.
- **Dual-path**: Heuristic structured fallback always available; LLM overlay when `OPENAI_API_KEY` set.
- **Tenant isolation**: All DB queries enforce `tenant_id` at the DB level.
- **AI audit**: `log_ai_interaction()` called (best-effort, Phase 230).
- **History cap**: At most 5 recent completed tasks returned.

## Files

### New
- `src/api/worker_copilot_router.py` — `POST /ai/copilot/worker-assist`
- `tests/test_worker_copilot_contract.py` — 20 contract tests
- `docs/archive/phases/phase-231-spec.md` — this file

### Modified
- `src/main.py` — registered `worker_copilot_router` (Phase 231)

## Endpoint

**`POST /ai/copilot/worker-assist`**

Request:
```json
{ "task_id": "a1b2c3d4e5f6a7b8" }
```

Response fields:
- `tenant_id`, `task_id`, `generated_by`
- `task_context`: title, kind, priority, urgency, due_date, status
- `property_info`: name, address, access_code, wifi_password, checkin_time, checkout_time
- `guest_context`: guest_name, language, check_in, check_out, total_nights, provider
- `recent_task_history`: last 5 COMPLETED tasks at the same property
- `priority_justification`: human-readable urgency explanation
- `assist_narrative`: heuristic bullet list or LLM natural-language overlay
- `generated_at`

## DB Sources
- `tasks` table — task row + recent history for property
- `booking_state` — guest context
- `properties` — property access info

## Heuristic Narratives (per kind)
| Kind | Intro |
|------|-------|
| CHECKIN_PREP | "Prepare the property for guest arrival." |
| CLEANING | "Complete a full cleaning of the property." |
| CHECKOUT_VERIFY | "Inspect the property after guest departure." |
| MAINTENANCE | "Carry out the required maintenance work." |
| GENERAL | "Complete the assigned general task." |
| GUEST_WELCOME | "Set up a welcome experience for the arriving guest." |
