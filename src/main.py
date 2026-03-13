"""
iHouse Core — FastAPI Application Entrypoint
===============================================

This is the unified production entrypoint for the OTA webhook ingestion stack.

Routes:
    GET  /health                — liveness check (no auth)
    POST /webhooks/{provider}  — OTA webhook ingestion (Phase 58)

Middleware:
    Phase 60 — Structured request logging  ✅
    Phase 61 — JWT auth (tenant_id from token)
    Phase 62 — Per-tenant rate limiting

Run locally:
    PYTHONPATH=src uvicorn main:app --reload --port 8000

Or via this file directly:
    PYTHONPATH=src python src/main.py
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.webhooks import router as webhooks_router
from api.health import run_health_checks
from schemas.responses import ErrorResponse, HealthResponse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ihouse-core")

# ---------------------------------------------------------------------------
# Phase 466 — Startup env validation (replaces Phase 359 inline checks)
# ---------------------------------------------------------------------------

_BUILD_VERSION = os.getenv("BUILD_VERSION", "0.1.0")

from services.env_validator import validate_production_env  # noqa: E402
_env_warnings = validate_production_env()

# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

_ENV = os.getenv("IHOUSE_ENV", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN001
    logger.info("iHouse Core API starting — env=%s version=%s", _ENV, app.version)
    from services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("iHouse Core API shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_DESCRIPTION = """
## iHouse Core — Hospitality Operations API

Full-stack property management and operations platform.

### Core Capabilities

| Area | Description |
|------|-------------|
| **Webhooks** | OTA ingestion (Booking.com, Expedia, Airbnb, Agoda, Trip.com) |
| **Bookings** | State management, conflict resolution, calendar views |
| **Financial** | Revenue extraction, reconciliation, owner statements, cashflow |
| **Tasks** | Auto-generation, SLA enforcement, worker assignment |
| **Guests** | Portal, messaging copilot, feedback collection |
| **Operations** | Pre-arrival scan, check-in/out readiness, daily ops |
| **Export** | CSV downloads for bookings, financials, feedback, audit |
| **Monitoring** | Request metrics, latency tracking, health dashboard |

### Authentication

All endpoints require a valid **Bearer JWT** token (except `/health`).
The `sub` claim is used as `tenant_id`.

### Response Format (Phase 542)

Standardized envelope: `{"ok": true/false, "data": ..., "error": ..., "meta": ...}`

### API Version

v1.0 — Phase 543
"""


_TAGS = [
    {"name": "ops", "description": "Operational endpoints (health, status). No authentication required."},
    {"name": "webhooks", "description": "OTA provider webhook ingestion. JWT Bearer + HMAC signature required."},
    {"name": "bookings", "description": "Booking state query. JWT Bearer required. Reads from booking_state projection."},
    {"name": "financial", "description": "Financial facts query. JWT Bearer required. Reads from booking_financial_facts only."},
    {"name": "admin", "description": "Tenant operational summary. JWT Bearer required. Read-only, tenant-scoped."},
    {"name": "owner-statement", "description": "Monthly owner statement. JWT Bearer required. Aggregates booking_financial_facts per property."},
    {"name": "payment-status", "description": "Payment lifecycle projection. JWT Bearer required. Reads booking_financial_facts and projects state in-memory."},
    {"name": "amendments", "description": "Amendment history. JWT Bearer required. Returns chronological BOOKING_AMENDED financial snapshots from booking_financial_facts."},
    {"name": "financial-aggregation", "description": "Financial aggregation (Ring 1). JWT Bearer required. Aggregates booking_financial_facts by currency, provider, property, and lifecycle status."},
    {"name": "financial-dashboard", "description": "Financial dashboard (Ring 2–3). JWT Bearer required. Per-booking status card, RevPAR, lifecycle-by-property."},
    {"name": "reconciliation", "description": "Reconciliation inbox (Ring 3). JWT Bearer required. Exception-first view of bookings requiring operator attention."},
    {"name": "cashflow", "description": "Cashflow / payout timeline (Ring 3). JWT Bearer required. Weekly inflow buckets, confirmed releases, overdue, 30/60/90-day projection."},
    {"name": "ota-comparison", "description": "OTA financial health comparison (Ring 3). JWT Bearer required. Per-OTA commission, net-to-gross, revenue share, lifecycle distribution."},
    {"name": "worker", "description": "Worker-facing task surface (Phase 123). JWT Bearer required. Role-scoped task list, acknowledge, and complete endpoints."},
    {"name": "line", "description": "LINE external escalation channel (Phase 124). Receives LINE webhook ack callbacks. Writes ONLY to tasks table. LINE is fallback only."},
    {"name": "sms", "description": "SMS escalation channel (Phase 212). Tier-2 last-resort escalation via Twilio. Inbound ACK replies → task acknowledgement. IHOUSE_SMS_TOKEN required."},
    {"name": "email", "description": "Email notification channel (Phase 213). One-click task acknowledgement via email link. GET /email/ack?task_id=&token=. IHOUSE_EMAIL_TOKEN required."},
    {"name": "onboarding", "description": "Property Onboarding Wizard API (Phase 214). Guided 3-step flow: metadata → channel mappings → worker assignments. Idempotent / upsert. JWT Bearer required."},
    {"name": "revenue-report", "description": "Automated Revenue Reports (Phase 215). Per-property monthly breakdown + portfolio cross-property summary. Reads `booking_financial_facts` only. JWT Bearer required."},
    {"name": "portfolio", "description": "Portfolio Dashboard UI (Phase 216). Cross-property owner view: occupancy, revenue, pending tasks, sync health. Single aggregated endpoint. JWT Bearer required."},
    {"name": "integrations", "description": "Integration Management UI (Phase 217). Admin surface: all OTA connections per property with last sync status, stale flags, enabled/disabled. JWT Bearer required."},
    {"name": "availability", "description": "Availability projection (Phase 126). Per-date occupancy state for a property. Reads from booking_state only. Zero write-path changes."},
    {"name": "integration-health", "description": "Integration Health Dashboard (Phase 127). Per-provider health for all 13 OTA providers: lag, buffer, DLQ, stale alert. JWT required."},
    {"name": "conflicts", "description": "Conflict Center (Phase 128). Active booking overlaps (CONFLICT pairs) across all properties for a tenant. JWT required."},
    {"name": "properties", "description": "Properties Summary Dashboard (Phase 130). Per-property portfolio view: active/canceled counts, next check-in/out, conflict flag. JWT required."},
    {"name": "history", "description": "Booking Audit Trail (Phase 132). Chronological event_log trail for a single booking: CREATED, AMENDED, CANCELED, buffered, replayed. JWT required."},
    {"name": "buffer", "description": "OTA Ordering Buffer Inspector (Phase 133). Entries stuck waiting for BOOKING_CREATED — event_type, age_seconds, dlq_row_id. JWT required."},
    {"name": "channel-map", "description": "Property-Channel Mapping Foundation (Phase 135). Register/list/update/remove OTA channel mappings per property. Outbound sync foundation. JWT required."},
    {"name": "registry", "description": "Provider Capability Registry (Phase 136). OTA write capabilities, tiers (A/B/C/D), sync modes, rate limits. Global. JWT required."},
    {"name": "sync", "description": "Outbound Sync Trigger (Phase 137). Compute per-channel sync_plan (api_first|ical_fallback|skip) by joining channel map and capability registry. JWT required."},
    {"name": "outbound", "description": "Outbound Sync Log Inspector (Phase 145). Read-only audit log of all outbound sync attempts per tenant. Filters: booking_id, provider, status, limit. JWT required."},
    {"name": "ai-context", "description": "AI Context Aggregation (Phase 222). LLM-ready context bundles: property snapshot + daily operations. JWT Bearer required. Read-only. No new tables."},
    {"name": "copilot", "description": "Manager Copilot (Phase 223). AI-powered morning briefing. LLM-generated when OPENAI_API_KEY is set; deterministic heuristic fallback otherwise. POST /ai/copilot/morning-briefing. JWT required."},
    {"name": "audit", "description": "Mutation Audit Events (Phase 189). Append-only record of every booking/task mutation with actor attribution. Filters: entity_type, entity_id, actor_id. JWT required."},
]

app = FastAPI(
    title="iHouse Core",
    version=_BUILD_VERSION,
    description=_DESCRIPTION,
    contact={
        "name": "iHouse Engineering",
        "url": "https://ihouse.dev",
    },
    license_info={
        "name": "Proprietary",
    },
    openapi_tags=_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — Phase 313 Production Readiness
# ---------------------------------------------------------------------------

from starlette.middleware.cors import CORSMiddleware  # noqa: E402

_cors_origins_raw = os.getenv("IHOUSE_CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-API-Version"],
)

# ---------------------------------------------------------------------------
# Security Headers — Phase 480
# ---------------------------------------------------------------------------

from middleware.security_headers import SecurityHeadersMiddleware  # noqa: E402

app.add_middleware(SecurityHeadersMiddleware)

# ---------------------------------------------------------------------------
# Phase 570-572 — Response Envelope (Exception Handlers Only)
# Middleware removed (Phase 585) — routers use api.envelope.ok/err explicitly.
# Exception handlers kept for unhandled errors (422 validation, 500 internal).
# ---------------------------------------------------------------------------

from api.response_envelope_middleware import (  # noqa: E402
    register_exception_handlers,
)

register_exception_handlers(app)

# Routers
# ---------------------------------------------------------------------------

app.include_router(webhooks_router)

from api.financial_router import router as financial_router  # noqa: E402
app.include_router(financial_router)

from api.bookings_router import router as bookings_router  # noqa: E402
app.include_router(bookings_router)

from api.admin_router import router as admin_router  # noqa: E402
app.include_router(admin_router)

from api.owner_statement_router import router as owner_statement_router  # noqa: E402
app.include_router(owner_statement_router)

from api.payment_status_router import router as payment_status_router  # noqa: E402
app.include_router(payment_status_router)

from api.amendments_router import router as amendments_router  # noqa: E402
app.include_router(amendments_router)

from tasks.task_router import router as task_router  # noqa: E402
app.include_router(task_router)

from api.financial_aggregation_router import router as financial_aggregation_router  # noqa: E402
app.include_router(financial_aggregation_router)

from api.financial_dashboard_router import router as financial_dashboard_router  # noqa: E402
app.include_router(financial_dashboard_router)

from api.reconciliation_router import router as reconciliation_router  # noqa: E402
app.include_router(reconciliation_router)

from api.admin_reconciliation_router import router as admin_reconciliation_router  # noqa: E402  # Phase 241
app.include_router(admin_reconciliation_router)

from api.booking_lifecycle_router import router as booking_lifecycle_router  # noqa: E402  # Phase 242
app.include_router(booking_lifecycle_router)

from api.property_performance_router import router as property_performance_router  # noqa: E402  # Phase 243
app.include_router(property_performance_router)

from api.ota_revenue_mix_router import router as ota_revenue_mix_router  # noqa: E402  # Phase 244
app.include_router(ota_revenue_mix_router)

from api.rate_card_router import router as rate_card_router  # noqa: E402  # Phase 246
app.include_router(rate_card_router)

from api.guest_feedback_router import router as guest_feedback_router  # noqa: E402  # Phase 247
app.include_router(guest_feedback_router)

from api.task_template_router import router as task_template_router  # noqa: E402  # Phase 248
app.include_router(task_template_router)

from api.content_push_router import router as content_push_router  # noqa: E402  # Phase 250
app.include_router(content_push_router)

from api.pricing_suggestion_router import router as pricing_suggestion_router  # noqa: E402  # Phase 251
app.include_router(pricing_suggestion_router)

from api.owner_financial_report_v2_router import router as owner_financial_report_v2_router  # noqa: E402  # Phase 252
app.include_router(owner_financial_report_v2_router)

from api.staff_performance_router import router as staff_performance_router  # noqa: E402  # Phase 253
app.include_router(staff_performance_router)

from api.bulk_operations_router import router as bulk_operations_router  # noqa: E402  # Phase 259
app.include_router(bulk_operations_router)

from api.webhook_event_log_router import router as webhook_event_log_router  # noqa: E402  # Phase 261
app.include_router(webhook_event_log_router)

from api.guest_portal_router import router as guest_portal_router  # noqa: E402  # Phase 262
app.include_router(guest_portal_router)

from api.monitoring_router import router as monitoring_router  # noqa: E402  # Phase 263
app.include_router(monitoring_router)

from api.analytics_router import router as analytics_router  # noqa: E402  # Phase 264
app.include_router(analytics_router)

from api.org_router import router as org_router  # noqa: E402  # Phase 296
app.include_router(org_router)

from api.session_router import router as session_router  # noqa: E402  # Phase 297
app.include_router(session_router)

from api.guest_token_router import router as guest_token_router  # noqa: E402  # Phase 298
app.include_router(guest_token_router)

from api.owner_portal_router import router as owner_portal_router  # noqa: E402  # Phase 298
app.include_router(owner_portal_router)

from api.notification_router import router as notification_router  # noqa: E402  # Phase 299
app.include_router(notification_router)

from api.cashflow_router import router as cashflow_router  # noqa: E402
app.include_router(cashflow_router)

from api.ota_comparison_router import router as ota_comparison_router  # noqa: E402
app.include_router(ota_comparison_router)

from api.worker_router import router as worker_router  # noqa: E402
app.include_router(worker_router)

from api.line_webhook_router import router as line_webhook_router  # noqa: E402
app.include_router(line_webhook_router)

from api.availability_router import router as availability_router  # noqa: E402
app.include_router(availability_router)

from api.integration_health_router import router as integration_health_router  # noqa: E402
app.include_router(integration_health_router)

from api.conflicts_router import router as conflicts_router  # noqa: E402
app.include_router(conflicts_router)

from api.properties_summary_router import router as properties_summary_router  # noqa: E402
app.include_router(properties_summary_router)

from api.dlq_router import router as dlq_router  # noqa: E402
app.include_router(dlq_router)

from api.booking_history_router import router as booking_history_router  # noqa: E402
app.include_router(booking_history_router)

from api.buffer_router import router as buffer_router  # noqa: E402
app.include_router(buffer_router)

from api.channel_map_router import router as channel_map_router  # noqa: E402
app.include_router(channel_map_router)

from api.capability_registry_router import router as capability_registry_router  # noqa: E402
app.include_router(capability_registry_router)

from api.sync_trigger_router import router as sync_trigger_router  # noqa: E402
app.include_router(sync_trigger_router)

from api.outbound_executor_router import router as outbound_executor_router  # noqa: E402
app.include_router(outbound_executor_router)

from api.outbound_log_router import router as outbound_log_router  # noqa: E402  # Phase 145
app.include_router(outbound_log_router)

from api.operations_router import router as operations_router  # noqa: E402  # Phase 153
app.include_router(operations_router)

from api.properties_router import router as properties_router  # noqa: E402  # Phase 156
app.include_router(properties_router)

from api.guest_profile_router import router as guest_profile_router  # noqa: E402  # Phase 159
app.include_router(guest_profile_router)

from api.financial_correction_router import router as financial_correction_router  # noqa: E402  # Phase 162
app.include_router(financial_correction_router)

from api.permissions_router import router as permissions_router  # noqa: E402  # Phase 165
app.include_router(permissions_router)

from api.broadcaster_router import router as broadcaster_router  # noqa: E402  # Phase 173
app.include_router(broadcaster_router)

from api.auth_router import router as auth_router  # noqa: E402  # Phase 179
app.include_router(auth_router)

from api.sse_router import router as sse_router  # noqa: E402  # Phase 181
app.include_router(sse_router)

from api.audit_router import router as audit_router  # noqa: E402  # Phase 189
app.include_router(audit_router)

from api.guests_router import router as guests_router  # noqa: E402  # Phase 192
app.include_router(guests_router)

from api.booking_guest_link_router import router as booking_guest_link_router  # noqa: E402  # Phase 194
app.include_router(booking_guest_link_router)

from api.whatsapp_router import router as whatsapp_router  # noqa: E402  # Phase 196
app.include_router(whatsapp_router)

from api.sms_router import router as sms_router  # noqa: E402  # Phase 212
app.include_router(sms_router)

from api.email_router import router as email_router  # noqa: E402  # Phase 213
app.include_router(email_router)

from api.onboarding_router import router as onboarding_router  # noqa: E402  # Phase 214
app.include_router(onboarding_router)

from api.property_admin_router import router as property_admin_router  # noqa: E402  # Phase 396
app.include_router(property_admin_router)

from api.revenue_report_router import router as revenue_report_router  # noqa: E402  # Phase 215
app.include_router(revenue_report_router)

from api.portfolio_dashboard_router import router as portfolio_dashboard_router  # noqa: E402  # Phase 216
app.include_router(portfolio_dashboard_router)

from api.integration_management_router import router as integration_management_router  # noqa: E402  # Phase 217
app.include_router(integration_management_router)

from api.ai_context_router import router as ai_context_router  # noqa: E402  # Phase 222
app.include_router(ai_context_router)

from api.manager_copilot_router import router as manager_copilot_router  # noqa: E402  # Phase 223
app.include_router(manager_copilot_router)

from api.financial_explainer_router import router as financial_explainer_router  # noqa: E402  # Phase 224
app.include_router(financial_explainer_router)

from api.task_recommendation_router import router as task_recommendation_router  # noqa: E402  # Phase 225
app.include_router(task_recommendation_router)

from api.anomaly_alert_broadcaster import router as anomaly_alert_router  # noqa: E402  # Phase 226
app.include_router(anomaly_alert_router)

from api.guest_messaging_copilot import router as guest_messaging_router  # noqa: E402  # Phase 227
app.include_router(guest_messaging_router)

from api.ai_audit_log_router import router as ai_audit_log_router  # noqa: E402  # Phase 230
app.include_router(ai_audit_log_router)

from api.worker_copilot_router import router as worker_copilot_router  # noqa: E402  # Phase 231
app.include_router(worker_copilot_router)

from api.pre_arrival_router import router as pre_arrival_router  # noqa: E402  # Phase 232
app.include_router(pre_arrival_router)

from api.revenue_forecast_router import router as revenue_forecast_router  # noqa: E402  # Phase 233
app.include_router(revenue_forecast_router)

from api.worker_availability_router import router as worker_availability_router  # noqa: E402  # Phase 234
app.include_router(worker_availability_router)

from api.guest_messages_router import router as guest_messages_router  # noqa: E402  # Phase 236
app.include_router(guest_messages_router)

from api.booking_checkin_router import router as booking_checkin_router  # noqa: E402  # Phase 398
app.include_router(booking_checkin_router)

from api.access_token_router import router as access_token_router  # noqa: E402  # Phase 399
app.include_router(access_token_router)

from api.invite_router import router as invite_router  # noqa: E402  # Phase 401
app.include_router(invite_router)

from api.onboard_token_router import router as onboard_token_router  # noqa: E402  # Phase 402
app.include_router(onboard_token_router)

from api.property_dashboard_router import router as property_dashboard_api_router  # noqa: E402  # Phase 505
app.include_router(property_dashboard_api_router)

from api.financial_writer_router import router as financial_writer_router  # noqa: E402  # Phase 506
app.include_router(financial_writer_router)

from api.currency_router import router as currency_router  # noqa: E402  # Phase 507
app.include_router(currency_router)

from api.webhook_retry_router import router as webhook_retry_router  # noqa: E402  # Phase 508
app.include_router(webhook_retry_router)

from api.notification_pref_router import router as notification_pref_router  # noqa: E402  # Phase 509
app.include_router(notification_pref_router)

from api.job_runner_router import router as job_runner_router  # noqa: E402  # Phase 516
app.include_router(job_runner_router)

from api.export_router import router as export_router  # noqa: E402  # Phase 535
app.include_router(export_router)

from api.monitoring_middleware import MonitoringMiddleware  # noqa: E402  # Phase 537
app.add_middleware(MonitoringMiddleware)


# ---------------------------------------------------------------------------
# Phase 221 — Scheduler status endpoint
# ---------------------------------------------------------------------------

@app.get(
    "/admin/scheduler-status",
    tags=["admin"],
    summary="Scheduled job runner status (Phase 221)",
)
async def scheduler_status() -> JSONResponse:
    """
    GET /admin/scheduler-status

    Returns the current state of the background job scheduler:
    whether it is running, and next_run_utc for each registered job.
    JWT auth not required (ops surface, no sensitive data).
    """
    from services.scheduler import get_scheduler_status
    return JSONResponse(status_code=200, content=get_scheduler_status())


# ---------------------------------------------------------------------------
# OpenAPI — inject BearerAuth security scheme (Phase 63)
# ---------------------------------------------------------------------------

def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        contact=app.contact,
        license_info=app.license_info,
        tags=app.openapi_tags,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "HMAC-HS256 signed JWT. The `sub` claim is used as `tenant_id`. "
            "Set `IHOUSE_JWT_SECRET` to enable; omit for dev-mode bypass."
        ),
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Middleware — Structured request logging (Phase 60)
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_logging(request: Request, call_next):  # type: ignore[name-defined]
    """
    Logs every request with:
      - unique request_id (UUID4)
      - method + path
      - status_code and duration_ms on exit

    Sets X-Request-ID response header on every response.
    """
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    logger.info(
        "→ [%s] %s %s",
        request_id,
        request.method,
        request.url.path,
    )

    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception(
            "← [%s] %s %s UNHANDLED_ERROR %dms",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        from fastapi.responses import JSONResponse as _JSONResponse
        resp = _JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})
        resp.headers["X-Request-ID"] = request_id
        resp.headers["X-API-Version"] = app.version
        return resp

    duration_ms = int((time.monotonic() - start) * 1000)
    logger.info(
        "← [%s] %s %s %d %dms",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Version"] = app.version
    return response


@app.get(
    "/health",
    tags=["ops"],
    summary="Liveness + dependency check",
    response_model=HealthResponse,
    responses={
        200: {"model": HealthResponse, "description": "ok or degraded (DLQ non-empty)"},
        503: {"model": HealthResponse, "description": "Supabase unreachable"},
    },
)
async def health() -> JSONResponse:
    """
    Enhanced health check (Phase 64).

    Runs:
    - **Supabase ping** — SELECT 1 equivalent via REST API
    - **DLQ count** — unprocessed `ota_dead_letter` rows

    Status semantics:
    - `ok` — all checks pass, DLQ empty
    - `degraded` — checks pass but DLQ has unprocessed rows
    - `unhealthy` — Supabase unreachable → **503**
    """
    result = run_health_checks(version=app.version, env=_ENV)
    return JSONResponse(
        status_code=result.http_status,
        content={
            "status": result.status,
            "version": result.version,
            "env": result.env,
            "checks": result.checks,
        },
    )


@app.get(
    "/readiness",
    tags=["ops"],
    summary="Readiness probe (Supabase reachable?)",
    responses={
        200: {"description": "Ready — Supabase reachable, can serve traffic"},
        503: {"description": "Not ready — Supabase unreachable"},
    },
)
async def readiness() -> JSONResponse:
    """
    Kubernetes-style readiness probe (Phase 211).

    Unlike /health (liveness — is the process alive?), /readiness answers:
    "can this instance serve traffic right now?"

    Returns 200 if Supabase is reachable, 503 otherwise.
    Load balancers should use this to decide whether to route traffic here.

    No authentication required.
    """
    result = run_health_checks(version=app.version, env=_ENV)
    supabase_check = result.checks.get("supabase", {})
    is_ready = supabase_check.get("status") in ("ok", "skipped")

    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "ready": is_ready,
            "status": result.status,
            "version": result.version,
        },
    )


# ---------------------------------------------------------------------------
# Local dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("IHOUSE_ENV", "development") == "development",
        log_level="info",
    )
