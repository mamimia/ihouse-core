## Current Active Phase

Phase 227 — Guest Messaging Copilot v1 (closed)

## Last Closed Phase

Phase 218 — Platform Checkpoint IV (closed) — full audit, docs sync, handoff. 0 new code files.

## Current Objective

Phase 227 closed. Next: Phase 228 (TBD).

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only — no updates, no deletes ever
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical (Phase 36)
- `reservation_ref` normalized by `normalize_reservation_ref()` before use (Phase 68)
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `apply_envelope`
- `tenant_id` from verified JWT `sub` claim only — NEVER from payload body (Phase 61+)
- `booking_state` is a read model ONLY — must NEVER contain financial calculations
- All financial read endpoints query `booking_financial_facts` ONLY — never `booking_state`
- Deduplication rule: most-recent `recorded_at` per `booking_id`
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated endpoints.
- Management fee applied AFTER OTA commission on net_to_property (Phase 121)
- OTA_COLLECTING net NEVER included in owner_net_total — honesty invariant (Phase 121)
- External channels (LINE, WhatsApp, Telegram) are escalation fallbacks ONLY — never source of truth
- **No global fallback chain**: each worker has their preferred `channel_type` in `notification_channels`
- CRITICAL_ACK_SLA_MINUTES = 5 (locked)

## Key Files — Channel Layer (Phases 124, 168, 177, 196, 203)

| File | Role |
|------|------|
| `src/channels/line_escalation.py` | LINE pure module — should_escalate, build_line_message, HMAC-SHA256 verify |
| `src/api/line_webhook_router.py` | GET+POST /line/webhook |
| `src/channels/whatsapp_escalation.py` | WhatsApp pure module — same pattern as LINE |
| `src/api/whatsapp_router.py` | GET+POST /whatsapp/webhook |
| `src/channels/telegram_escalation.py` | Telegram pure module — should_escalate, build_telegram_message (Phase 203) |
| `src/channels/notification_dispatcher.py` | Core dispatcher — routes by worker's channel_type. No global chain. |
| `src/channels/sla_dispatch_bridge.py` | SLA → dispatcher bridge. Per-worker routing. |
| `src/channels/notification_delivery_writer.py` | Best-effort delivery log writer |

## Key Files — Financial API Layer (Phases 116–122)

| File | Role |
|------|›----|
| `src/api/financial_aggregation_router.py` | Ring 1: summary / by-provider / by-property / lifecycle-distribution / multi-currency-overview |
| `src/api/financial_dashboard_router.py` | Ring 2–3: status card, revpar, lifecycle-by-property |
| `src/api/reconciliation_router.py` | Ring 3: Exception-first reconciliation inbox |
| `src/api/cashflow_router.py` | Ring 3: Weekly inflow buckets, 30/60/90-day projection |
| `src/api/owner_statement_router.py` | Ring 4: Per-booking line items + PDF export (Phase 188) |
| `src/api/ota_comparison_router.py` | Ring 3: Per-OTA commission rate, net-to-gross, revenue share |
| `src/api/revenue_report_router.py` | Phase 215: GET /revenue-report/portfolio + GET /revenue-report/{id} |
| `src/api/portfolio_dashboard_router.py` | Phase 216: GET /portfolio/dashboard — occupancy+revenue+tasks+sync per property |
| `src/api/integration_management_router.py` | Phase 217: GET /admin/integrations + /admin/integrations/summary |

## Key Files — Task Layer (Phases 111–117, 206–207)

| File | Role |
|------|›----|
| `src/tasks/task_model.py` | TaskKind (6 kinds incl GUEST_WELCOME), TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / canceled / amended |
| `src/tasks/pre_arrival_tasks.py` | Pure tasks_for_pre_arrival — GUEST_WELCOME + enriched CHECKIN_PREP (Phase 206) |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule — wired into service.py |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status, POST /tasks/pre-arrival/{booking_id} |
| `src/tasks/sla_engine.py` | evaluate() — ACK_SLA_BREACH + COMPLETION_SLA_BREACH. CRITICAL_ACK_SLA_MINUTES=5. |
| `src/api/worker_router.py` | GET /worker/tasks, PATCH /acknowledge, PATCH /complete |
| `src/services/conflict_auto_resolver.py` | Phase 207 — run_auto_check() — auto-conflict on BOOKING_CREATED/AMENDED |

## Key Files — Communication Channels (Phases 212, 213)

| File | Role |
|------|›----|
| `src/channels/sms_escalation.py` | SMS pure module — mirrors LINE/WhatsApp/Telegram pattern (Phase 212) |
| `src/api/sms_router.py` | GET challenge + POST inbound ACK via Twilio form fields |
| `src/channels/email_escalation.py` | Email pure module — one-click ACK token flow (Phase 213) |
| `src/api/email_router.py` | GET /email/webhook health + GET /email/ack token ACK |

## Key Files — Onboarding + Product Surfaces (Phases 214–217)

| File | Role |
|------|›----|
| `src/api/onboarding_router.py` | Phase 214: 4-step wizard — POST /onboarding/start, /{id}/channels, /{id}/workers, GET /{id}/status |
| `src/api/revenue_report_router.py` | Phase 215: GET /revenue-report/portfolio + /revenue-report/{id} |
| `src/api/portfolio_dashboard_router.py` | Phase 216: GET /portfolio/dashboard — occupancy+revenue+tasks+sync health per property |
| `src/api/integration_management_router.py` | Phase 217: GET /admin/integrations (OTA connection view) + /admin/integrations/summary |

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
| `SUPABASE_URL` | required | Supabase URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | required | Used by all financial/admin routers (Phases 116+) |
| `IHOUSE_LINE_SECRET` | unset | dev-mode LINE sig skip |
| `IHOUSE_WHATSAPP_TOKEN` | unset | production WhatsApp dispatch |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | unset | Meta Cloud API phone ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | unset | HMAC sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook challenge token |
| `IHOUSE_TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `IHOUSE_DRY_RUN` | unset | skip real outbound API calls |
| `IHOUSE_THROTTLE_DISABLED` | unset | skip rate limiting in outbound |
| `IHOUSE_RETRY_DISABLED` | unset | skip exponential backoff |
| `IHOUSE_SYNC_LOG_DISABLED` | unset | skip persistence of sync results |
| `IHOUSE_SYNC_CALLBACK_URL` | unset | webhook URL for sync.ok events |
| `PORT` | 8000 | uvicorn port |

## Tests

**5,179 collected. 5,179 passing. 0 failures. Exit 0.**
