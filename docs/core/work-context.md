# iHouse Core — Work Context

## Current Active Phase

Phase 197 — Platform Checkpoint II (closed)

## Last Closed Phase

Phase 197 — Platform Checkpoint II — docs sync, handoff written, ZIP created. Full audit of all canonical docs. Current snapshot rewritten to reflect true Phase 176–197 state. next-phase protocol documented in handoff.

## Current Objective

**The next conversation must follow the Phase 197 handoff protocol.**
See `releases/handoffs/handoff_to_new_chat Phase-197.md` — read it first.

## What Was Done Since Platform Checkpoint I (Phase 175)

| Phase | Feature | Key Files |
|-------|---------|-----------|
| 176 | Outbound Sync Auto-Trigger (BOOKING_CREATED) | `outbound_sync_trigger.py`, `service.py` |
| 177 | SLA→Dispatcher Bridge | `src/channels/sla_dispatch_bridge.py` |
| 178–183 | Notification Delivery Writer + Channel Infra | `src/channels/notification_delivery_writer.py` |
| 188 | PDF Owner Statements | `src/api/owner_statement_router.py` (format=pdf), `reportlab` |
| 189 | Booking Mutation Audit Events | `src/services/audit_writer.py`, `src/api/audit_router.py` |
| 190 | Manager Activity Feed UI | `ihouse-ui/app/manager/page.tsx` |
| 191 | Multi-Currency Financial Overview | `GET /financial/multi-currency-overview` |
| 192 | Guest Profile Foundation | `src/api/guests_router.py`, `guests` Supabase table |
| 193 | Guest Profile UI | `ihouse-ui/app/guests/page.tsx`, `/guests/[id]` |
| 194 | Booking→Guest Link | `src/api/booking_guest_link_router.py`, `guest_id` on `booking_state` |
| 195 | Hostelworld Adapter | `src/adapters/ota/hostelworld.py` (14th OTA adapter) |
| 196 | WhatsApp Escalation Channel | `src/channels/whatsapp_escalation.py`, `src/api/whatsapp_router.py` |
| 196-patch | Per-Worker Channel Architecture | `notification_dispatcher.py` CHANNEL_WHATSAPP/TELEGRAM/SMS. `sla_dispatch_bridge.py` global chain removed. |
| 197 | Platform Checkpoint II | All canonical docs updated, handoff written, ZIP created. |

## Roadmap Direction (Phase 198+)

The next conversation is responsible for:
1. Reading the full system (Layer A → construction-log latest)
2. Proposing 20 next phases with rationale
3. Getting user approval
4. Only then executing

See handoff for full detail on protocol.

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

## Key Files — Channel Layer (Phases 124, 168, 177, 196)

| File | Role |
|------|------|
| `src/channels/line_escalation.py` | LINE pure module — should_escalate, build_line_message, HMAC-SHA256 verify |
| `src/api/line_webhook_router.py` | GET+POST /line/webhook |
| `src/channels/whatsapp_escalation.py` | WhatsApp pure module — same pattern as LINE |
| `src/api/whatsapp_router.py` | GET+POST /whatsapp/webhook |
| `src/channels/notification_dispatcher.py` | Core dispatcher — routes by worker's channel_type. No global chain. |
| `src/channels/sla_dispatch_bridge.py` | SLA → dispatcher bridge. Per-worker routing. |
| `src/channels/notification_delivery_writer.py` | Best-effort delivery log writer |

## Key Files — Financial API Layer (Phases 116–122)

| File | Role |
|------|------|
| `src/api/financial_aggregation_router.py` | Ring 1: summary / by-provider / by-property / lifecycle-distribution / multi-currency-overview |
| `src/api/financial_dashboard_router.py` | Ring 2–3: status card, revpar, lifecycle-by-property |
| `src/api/reconciliation_router.py` | Ring 3: Exception-first reconciliation inbox |
| `src/api/cashflow_router.py` | Ring 3: Weekly inflow buckets, 30/60/90-day projection |
| `src/api/owner_statement_router.py` | Ring 4: Per-booking line items + PDF export (Phase 188) |
| `src/api/ota_comparison_router.py` | Ring 3: Per-OTA commission rate, net-to-gross, revenue share |

## Key Files — Task Layer (Phases 111–117)

| File | Role |
|------|------|
| `src/tasks/task_model.py` | TaskKind, TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / canceled / amended |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule — wired into service.py |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status |
| `src/tasks/sla_engine.py` | evaluate() — ACK_SLA_BREACH + COMPLETION_SLA_BREACH. CRITICAL_ACK_SLA_MINUTES=5. |
| `src/api/worker_router.py` | GET /worker/tasks, PATCH /acknowledge, PATCH /complete |

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
| `IHOUSE_LINE_SECRET` | unset | dev-mode LINE sig skip |
| `IHOUSE_WHATSAPP_TOKEN` | unset | production WhatsApp dispatch |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | unset | Meta Cloud API phone ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | unset | HMAC sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook challenge token |
| `IHOUSE_DRY_RUN` | unset | skip real outbound API calls |
| `IHOUSE_THROTTLE_DISABLED` | unset | skip rate limiting in outbound |
| `IHOUSE_RETRY_DISABLED` | unset | skip exponential backoff |
| `IHOUSE_SYNC_LOG_DISABLED` | unset | skip persistence of sync results |
| `IHOUSE_SYNC_CALLBACK_URL` | unset | webhook URL for sync.ok events |
| `PORT` | 8000 | uvicorn port |

## Tests

**4,906 collected. ~4,900 passing. 6 pre-existing failures (outbound / conflicts / webhook fixture providers — unrelated to core). Exit 0.**
