# iHouse Core — Work Context

## Current Active Phase

Phase 126 — Multi-Projection Read Models: Availability Projection (closed)

## Last Closed Phase

Phase 126 — Availability Projection: GET /availability/{property_id}

## Current Objective

**Phase 127 — (next — see roadmap)**
See `docs/core/roadmap.md` for forward plan.

## What Was Done in This Session (Phases 118–122)

| Phase | Feature | Files |
|-------|---------|-------|
| 118 | Financial Dashboard API | `src/api/financial_dashboard_router.py`, `tests/test_financial_dashboard_router_contract.py` |
| 119 | Reconciliation Inbox API | `src/api/reconciliation_router.py`, `tests/test_reconciliation_router_contract.py` |
| 120 | Cashflow / Payout Timeline | `src/api/cashflow_router.py`, `tests/test_cashflow_router_contract.py` |
| 121 | Owner Statement Generator (Ring 4) | `src/api/owner_statement_router.py`, `tests/test_owner_statement_phase121_contract.py` |
| 122 | OTA Financial Health Comparison | `src/api/ota_comparison_router.py`, `tests/test_ota_comparison_router_contract.py` |
| 123 | Worker-Facing Task Surface | `src/api/worker_router.py`, `tests/test_worker_router_contract.py` |
| 124 | LINE Escalation Channel | `src/channels/line_escalation.py`, `src/api/line_webhook_router.py`, `tests/test_line_*` |
| 125 | Hotelbeds Adapter (Tier 3 B2B) | `src/adapters/ota/hotelbeds.py`, `tests/test_hotelbeds_adapter_contract.py` |
| 126 | Availability Projection | `src/api/availability_router.py`, `tests/test_availability_router_contract.py` |
| docs | Contextual Help Layer spec | `docs/future/contextual-help-layer.md`, appended to `future-improvements.md` |

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical (Phase 36)
- `reservation_ref` is normalized by `normalize_reservation_ref()` before use (Phase 68)
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `IngestAPI.append_event` → `CoreExecutor.execute` → `apply_envelope`
- `tenant_id` comes from verified JWT `sub` claim, NOT from payload body (Phase 61+)
- `booking_state` is an operational read model ONLY — must never contain financial calculations (Phase 62+ invariant)
- All financial read endpoints query `booking_financial_facts` ONLY — never `booking_state`
- Deduplication rule: most-recent `recorded_at` per `booking_id` (shared across Phase 116–121)
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated endpoints.
- Management fee is applied AFTER OTA commission on the aggregated net_to_property (Phase 121)
- OTA_COLLECTING net is NEVER included in owner_net_total — honesty invariant (Phase 121)

## Key Files — Financial API Layer (Phases 116–121)

| File | Role |
|------|------|
| `src/api/financial_aggregation_router.py` | Ring 1: summary/by-provider/by-property/lifecycle-distribution. Shared helpers: `_fetch_period_rows`, `_dedup_latest`, `_validate_period`, `_fmt`, `_to_decimal` |
| `src/api/financial_dashboard_router.py` | Ring 2–3: GET /financial/status/{id}, /revpar, /lifecycle-by-property. Exports: `_tier`, `_worst_tier`, `_monetary`, `_project_lifecycle_status` |
| `src/api/reconciliation_router.py` | Ring 3: GET /admin/reconciliation — exception-first inbox |
| `src/api/cashflow_router.py` | Ring 3: GET /financial/cashflow — weekly inflow buckets, confirmed released, overdue, 30/60/90-day projection |
| `src/api/owner_statement_router.py` | Ring 4: GET /owner-statement/{property_id} — per-booking line items, epistemic tier, management fee, PDF export |
| `src/api/ota_comparison_router.py` | Ring 3: GET /financial/ota-comparison — per-OTA commission rate, net-to-gross, revenue share, lifecycle distribution |
| `src/api/worker_router.py` | Phase 123: GET /worker/tasks, PATCH /worker/tasks/{id}/acknowledge, PATCH /worker/tasks/{id}/complete |
| `src/channels/line_escalation.py` | Phase 124: pure LINE module — should_escalate, build_line_message, format_line_text, is_priority_eligible |
| `src/api/line_webhook_router.py` | Phase 124: POST /line/webhook — LINE ack callback → PENDING→ACKNOWLEDGED, dev/prod sig validation |
| `src/adapters/ota/hotelbeds.py` | Phase 125: Tier 3 B2B bedbank adapter — voucher_ref, hotel_code, net_rate/contract_price/markup_amount |
| `src/api/availability_router.py` | Phase 126: GET /availability/{property_id}?from=&to= — per-date occupancy from booking_state, CONFLICT detection, zero write-path |

## Key Files — Task Layer (Phases 111–115)

| File | Role |
|------|------|
| `src/tasks/task_model.py` | TaskKind, TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / actions_for_booking_canceled / amended |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule — wired into service.py |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status |
| `src/tasks/sla_engine.py` | evaluate() — pure SLA escalation logic, ACK_SLA_BREACH + COMPLETION_SLA_BREACH |

## Key Files — Booking Identity Layer (Phase 68)

| File | Role |
|------|------|
| `src/adapters/ota/booking_identity.py` | `normalize_reservation_ref(provider, raw_ref)` + `build_booking_id(source, ref)` |

## Key Files — HTTP API Layer (Phases 58–64)

| File | Role |
|------|------|
| `src/main.py` | FastAPI app entrypoint (all routers registered here) |
| `src/api/webhooks.py` | `POST /webhooks/{provider}` |
| `src/api/auth.py` | JWT auth dependency |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |
| `src/api/health.py` | Dependency health checks (Phase 64) |
| `src/api/financial_router.py` | `GET /financial/{booking_id}` (Phase 67) |
| `src/schemas/responses.py` | OpenAPI Pydantic response models (Phase 63) |

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | dev-mode sig skip |
| `IHOUSE_JWT_SECRET` | unset | dev-mode JWT skip → "dev-tenant" |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `PORT` | 8000 | uvicorn port |

## Tests

**3129 passing** (2 pre-existing SQLite skips in `tests/invariants/test_invariant_suite.py` — unrelated to financial layer)

