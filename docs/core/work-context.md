## Current Active Phase

Phase 309 — Owner Portal Frontend

## Last Closed Phase

Phase 308 — Frontend Real Data Integration (closed) — Financial + Tasks SSE. All 4 main pages have real-time connectivity.

## Current Objective

Build the owner-facing portal page with property performance summaries, owner statements, and booking revenue visibility.

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
- External channels (LINE, WhatsApp, Telegram, SMS, Email) are escalation fallbacks ONLY — never source of truth
- **No global fallback chain**: each worker has their preferred `channel_type` in `notification_channels`
- CRITICAL_ACK_SLA_MINUTES = 5 (locked)

## Key Files — Channel Layer (Phases 124, 168, 177, 196, 203, 212, 213)

| File | Role |
|------|------|
| `src/channels/line_escalation.py` | LINE pure module — should_escalate, build_line_message, HMAC-SHA256 verify |
| `src/api/line_webhook_router.py` | GET+POST /line/webhook |
| `src/channels/whatsapp_escalation.py` | WhatsApp pure module — same pattern as LINE |
| `src/api/whatsapp_router.py` | GET+POST /whatsapp/webhook |
| `src/channels/telegram_escalation.py` | Telegram pure module — should_escalate, build_telegram_message (Phase 203) |
| `src/channels/sms_escalation.py` | SMS pure module — mirrors LINE/WhatsApp/Telegram pattern (Phase 212) |
| `src/api/sms_router.py` | GET challenge + POST inbound ACK via Twilio form fields |
| `src/channels/email_escalation.py` | Email pure module — one-click ACK token flow (Phase 213) |
| `src/api/email_router.py` | GET /email/webhook health + GET /email/ack token ACK |
| `src/channels/notification_dispatcher.py` | Core dispatcher — routes by worker's channel_type. No global chain. |
| `src/channels/sla_dispatch_bridge.py` | SLA → dispatcher bridge. Per-worker routing. |
| `src/channels/notification_delivery_writer.py` | Best-effort delivery log writer |

## Key Files — Financial API Layer (Phases 116–122, 191)

| File | Role |
|------|------|
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
|------|------|
| `src/tasks/task_model.py` | TaskKind (6 kinds incl GUEST_WELCOME), TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / canceled / amended |
| `src/tasks/pre_arrival_tasks.py` | Pure tasks_for_pre_arrival — GUEST_WELCOME + enriched CHECKIN_PREP (Phase 206) |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule — wired into service.py |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status, POST /tasks/pre-arrival/{booking_id} |
| `src/tasks/sla_engine.py` | evaluate() — ACK_SLA_BREACH + COMPLETION_SLA_BREACH. CRITICAL_ACK_SLA_MINUTES=5. |
| `src/api/worker_router.py` | GET /worker/tasks, PATCH /acknowledge, PATCH /complete |
| `src/services/conflict_auto_resolver.py` | Phase 207 — run_auto_check() — auto-conflict on BOOKING_CREATED/AMENDED |

## Key Files — AI Copilot Layer (Phases 222–227, 230–231)

| File | Role |
|------|------|
| `src/api/ai_context_router.py` | GET /ai/context/property/{id} + GET /ai/context/operations-day |
| `src/api/manager_copilot_router.py` | POST /ai/copilot/morning-briefing — 5 languages, LLM + heuristic |
| `src/api/financial_explainer_router.py` | GET /ai/copilot/financial/explain/{booking_id} + reconciliation-summary |
| `src/api/task_recommendation_router.py` | POST /ai/copilot/task-recommendations — deterministic scoring |
| `src/api/anomaly_alert_broadcaster.py` | POST /ai/copilot/anomaly-alerts — 3-domain health scanner |
| `src/api/guest_messaging_copilot.py` | POST /ai/copilot/guest-message-draft — 6 intents, 5 langs, 3 tones |
| `src/api/ai_audit_log_router.py` | Phase 230: GET /ai/audit-log — AI decision audit trail |
| `src/api/worker_copilot_router.py` | Phase 231: POST /ai/copilot/worker-assist — mobile contextual assists |
| `src/services/llm_client.py` | Provider-agnostic LLM client (OpenAI) |
| `src/services/ai_audit_log.py` | AI audit log writer |

## Key Files — Recent Additions (Phases 232–238)

| File | Role |
|------|------|
| `src/services/pre_arrival_scanner.py` | Phase 232: Guest pre-arrival automation chain |
| `src/api/revenue_forecast_router.py` | Phase 233: Revenue forecast engine |
| `src/api/worker_availability_router.py` | Phase 234: Shift & Availability Scheduler — worker_shifts table |
| `src/api/conflicts_router.py` | Phase 235: Enhanced — GET /admin/conflicts/dashboard |
| `src/api/guest_messages_router.py` | Phase 236: POST+GET /guest-messages/{booking_id} |
| `docker-compose.staging.yml` | Phase 237: Staging environment |
| `src/adapters/ota/tripcom.py` | Phase 238: Ctrip/Trip.com enhanced adapter |

## Key Files — Recent Additions (Phases 246–304)

| File | Role |
|------|------|
| `src/api/rate_card_router.py` | Phase 246: GET/POST /properties/{id}/rate-cards |
| `src/api/guest_feedback_router.py` | Phase 247: GET/POST/DELETE /admin/guest-feedback |
| `src/api/task_template_router.py` | Phase 248: GET/POST/DELETE /admin/task-templates |
| `src/adapters/outbound/bookingcom_content.py` | Phase 250: Booking.com content push builder |
| `src/api/content_push_router.py` | Phase 250: POST /admin/content/push/{property_id} |
| `src/services/pricing_engine.py` | Phase 251: Pure suggest_prices() + PriceSuggestion |
| `src/api/pricing_suggestion_router.py` | Phase 251: GET /pricing/suggestion/{property_id} |
| `src/api/owner_financial_report_v2_router.py` | Phase 252: GET /owner/financial-report |
| `src/api/staff_performance_router.py` | Phase 253: GET /admin/staff/performance + /{worker_id} |
| `src/services/bulk_operations.py` | Phase 255: bulk_cancel_bookings, bulk_assign_tasks, bulk_trigger_sync |
| `src/api/bulk_operations_router.py` | Phase 255: POST /admin/bulk/cancel, /tasks/assign, /sync/trigger |
| `src/services/webhook_event_log.py` | Phase 261: append-only event log, no PII, max 5000 entries |
| `src/api/webhook_event_log_router.py` | Phase 261: GET /admin/webhook-log, /stats; POST /test |
| `src/services/guest_portal.py` | Phase 262: GuestBookingView, token validation, stub_lookup |
| `src/api/guest_portal_router.py` | Phase 262: GET /guest/booking/{ref}, /wifi, /rules |
| `src/services/monitoring.py` | Phase 263: record_request(), latency histogram, health metrics |
| `src/api/monitoring_router.py` | Phase 263: GET /admin/monitor, /health, /latency |
| `src/services/analytics.py` | Phase 264: top_properties(), ota_mix(), revenue_summary() |
| `src/api/analytics_router.py` | Phase 264: GET /admin/analytics/top-properties, /ota-mix, /revenue-summary |
| `tests/conftest.py` | Phase 283: Session-scoped env var management, rate limiter reset |
| `deploy_checklist.sh` | Phase 286: Production Docker hardening validation script |
| `src/api/org_router.py` | Phase 296: GET/POST /org endpoints |
| `src/api/auth_router.py` | Phase 297: POST /auth/login, /auth/refresh, /auth/logout |
| `src/api/session_router.py` | Phase 297: GET /session/me, session validation |
| `src/api/guest_token_router.py` | Phase 298: POST /guest/verify-token, issue/verify HMAC tokens |
| `src/api/notification_router.py` | Phase 299: POST /notifications/send-sms, /send-email, /guest-token-send, GET /notifications/log |
| `src/services/owner_portal_data.py` | Phase 301: 6 functions for owner portal rich summary |
| `tests/test_guest_token_e2e.py` | Phase 302: 7 test suites, real HMAC crypto, live Supabase integration |
| `src/scripts/seed_owner_portal.py` | Phase 303: deterministic booking seeder (20 bookings, 3 properties) |

## Key Files — Frontend (ihouse-ui/, Phases 287–291)

| File | Role |
|------|------|
| `ihouse-ui/app/layout.tsx` | Root layout — Domaniqo branding, sidebar |
| `ihouse-ui/app/dashboard/page.tsx` | Operations dashboard — portfolio grid, 60s auto-refresh |
| `ihouse-ui/app/bookings/page.tsx` | Booking management — list, filters |
| `ihouse-ui/app/bookings/[id]/page.tsx` | Booking detail view |
| `ihouse-ui/app/tasks/page.tsx` | Worker task list |
| `ihouse-ui/app/tasks/[id]/page.tsx` | Task detail view |
| `ihouse-ui/app/financial/page.tsx` | Financial dashboard — OTA donut, cashflow |
| `ihouse-ui/app/financial/statements/page.tsx` | Owner statements |
| `ihouse-ui/app/calendar/page.tsx` | Booking calendar |
| `ihouse-ui/app/guests/page.tsx` | Guest profiles |
| `ihouse-ui/app/guests/[id]/page.tsx` | Guest detail |
| `ihouse-ui/app/worker/page.tsx` | Worker mobile view |
| `ihouse-ui/app/owner/page.tsx` | Owner portal |
| `ihouse-ui/app/manager/page.tsx` | Manager activity feed |
| `ihouse-ui/app/admin/page.tsx` | Admin settings |
| `ihouse-ui/app/admin/dlq/page.tsx` | DLQ replay UI |
| `ihouse-ui/app/login/page.tsx` | Login page |

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
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | sig verification skipped when unset |
| `IHOUSE_JWT_SECRET` | unset | 503 if unset and IHOUSE_DEV_MODE≠true |
| `IHOUSE_API_KEY` | unset | API key for external integrations |
| `IHOUSE_DEV_MODE` | unset | "true" = skip JWT auth, return dev-tenant. MUST be false in production (Phase 276) |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `IHOUSE_TENANT_ID` | unset | production tenant UUID |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | required | Used by all financial/admin routers (Phases 116+) |
| `IHOUSE_LINE_SECRET` | unset | LINE channel secret (sig verify) |
| `IHOUSE_LINE_CHANNEL_TOKEN` | unset | LINE channel access token |
| `IHOUSE_WHATSAPP_TOKEN` | unset | production WhatsApp dispatch |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | unset | Meta Cloud API phone ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | unset | HMAC sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook challenge token |
| `IHOUSE_TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `IHOUSE_SMS_TOKEN` | unset | SMS provider API token (Phase 212) |
| `IHOUSE_EMAIL_TOKEN` | unset | Email provider API token (Phase 213) |
| `IHOUSE_DRY_RUN` | unset | skip real outbound API calls |
| `IHOUSE_THROTTLE_DISABLED` | unset | skip rate limiting in outbound |
| `IHOUSE_RETRY_DISABLED` | unset | skip exponential backoff |
| `IHOUSE_SYNC_LOG_DISABLED` | unset | skip persistence of sync results |
| `IHOUSE_SYNC_CALLBACK_URL` | unset | webhook URL for sync.ok events |
| `IHOUSE_SCHEDULER_ENABLED` | unset | enable APScheduler jobs (Phase 221) |
| `IHOUSE_SLA_SWEEP_INTERVAL` | 120 | SLA sweep interval in seconds |
| `IHOUSE_DLQ_ALERT_INTERVAL` | 600 | DLQ alert check interval in seconds |
| `OPENAI_API_KEY` | unset | OpenAI API key for AI copilot endpoints |
| `SENTRY_DSN` | unset | Sentry error tracking DSN |
| `PORT` | 8000 | uvicorn port |
| `UVICORN_WORKERS` | 1 | number of uvicorn worker processes |
| `IHOUSE_GUEST_TOKEN_SECRET` | required | HMAC-SHA256 secret for guest portal tokens (Phase 298) |
| `IHOUSE_TWILIO_SID` | unset | Twilio Account SID (Phase 299) |
| `IHOUSE_TWILIO_TOKEN` | unset | Twilio Auth Token (Phase 299) |
| `IHOUSE_TWILIO_FROM` | unset | Sending phone number E.164 (Phase 299) |
| `IHOUSE_SENDGRID_KEY` | unset | SendGrid API key (Phase 299) |
| `IHOUSE_SENDGRID_FROM` | unset | Sending email address (Phase 299) |

## Tests

**6,406 collected. ~6,385 passing (~17 skipped). 4 pre-existing health/Supabase failures (env-dependent, not regressions). Exit 0. (Phase 304)**
