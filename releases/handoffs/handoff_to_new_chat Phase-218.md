# iHouse Core — Handoff to New Session
**Phase 218 — Platform Checkpoint IV**
**Date:** 2026-03-11 | **Tests:** 5,179 passing, 0 failures | **Exit 0**

---

## Where We Are

Phase 218 is complete. Documentation has been fully synchronized. The system is clean and healthy.

**Last closed phase:** 217 — Integration Management UI
**Next phase:** 219 — not yet assigned (see Forward Plan below)

---

## What Was Built — Phases 210–217

| Phase | Title | Key Deliverable |
|-------|-------|-----------------|
| 210 | Roadmap & Documentation Cleanup | Full audit of canonical docs, AI strategy doc created |
| 211 | Production Deployment Foundation | Dockerfile, docker-compose, `.dockerignore`, `GET /readiness` |
| 212 | SMS Escalation Channel | `sms_escalation.py`, `sms_router.py` (Twilio form-field ACK) |
| 213 | Email Notification Channel | `email_escalation.py`, `email_router.py` (one-click token ACK) |
| 214 | Property Onboarding Wizard API | `onboarding_router.py` — 4-step stateless wizard |
| 215 | Automated Revenue Reports | `revenue_report_router.py` — portfolio + per-property monthly |
| 216 | Portfolio Dashboard UI | `portfolio_dashboard_router.py` — `GET /portfolio/dashboard` |
| 217 | Integration Management UI | `integration_management_router.py` — `GET /admin/integrations` + `/summary` |

---

## System Numbers (Phase 218)

| Metric | Value |
|--------|-------|
| OTA Adapters | **14 live** (Airbnb, Booking.com, Expedia, Agoda, Trip.com, Traveloka, Vrbo, GVR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld) |
| Escalation Channels | **5** (LINE, WhatsApp, Telegram live; SMS + Email stubbed/registered) |
| Task Kinds | **6** (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| Product Surfaces | **16** (ops, bookings, calendar, tasks, worker, financial, owner statement, portal, guests, admin settings, manager feed, admin DLQ, onboarding, revenue reports, portfolio dashboard, integration management) |
| Financial Rings | **6** (extraction → persistence → aggregation → reconciliation → cashflow → owner statement) |
| Tests | **5,179 passing / 0 failures** |

---

## Key Architecture Rules (Never Change)

- `apply_envelope` is the ONLY write authority to `booking_state`
- `event_log` is append-only — no updates, no deletes
- `booking_id = "{provider}_{normalized_ref}"` — deterministic
- `booking_state` = read model ONLY — no financial calculations ever
- All financial reads from `booking_financial_facts` only
- `tenant_id` from JWT `sub` claim only — NEVER from body
- External channels (LINE/WhatsApp/Telegram/SMS) = escalation fallback only
- Outbound sync is best-effort — never blocking `apply_envelope`
- `CRITICAL_ACK_SLA_MINUTES = 5` (locked)

---

## Key Files Added Since Phase 209

| File | Phase |
|------|-------|
| `Dockerfile`, `docker-compose.yml`, `.dockerignore` | 211 |
| `src/channels/sms_escalation.py`, `src/api/sms_router.py` | 212 |
| `src/channels/email_escalation.py`, `src/api/email_router.py` | 213 |
| `src/api/onboarding_router.py` | 214 |
| `src/api/revenue_report_router.py` | 215 |
| `src/api/portfolio_dashboard_router.py` | 216 |
| `src/api/integration_management_router.py` | 217 |

All registered in `src/main.py`.

---

## Environment Variables

| Var | Purpose |
|-----|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Used by all financial/admin routers |
| `IHOUSE_JWT_SECRET` | JWT auth (unset = dev-tenant mode) |
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | OTA sig verify (unset = dev-mode skip) |
| `IHOUSE_RATE_LIMIT_RPM` | 60 req/min per tenant |
| `IHOUSE_LINE_SECRET`, `IHOUSE_WHATSAPP_TOKEN`, `IHOUSE_TELEGRAM_BOT_TOKEN` | Channel creds |
| `IHOUSE_DRY_RUN` | Skip real outbound API calls |

---

## Forward Plan — What To Build Next

### AI Assistive Layer (Phases 220–225) — Primary Direction

Full detail in `docs/core/planning/ai-strategy.md`.

| Phase | Title | Deliverable |
|-------|-------|-------------|
| 221 | AI Context Aggregation Endpoints | Composite read endpoints: booking + property + financial + task snapshot in one call |
| 222 | Manager Copilot v1 | 7AM morning briefing — urgent items, blocked tasks, sync health, plain-language |
| 223 | Financial Explainer | Tier explanation, reconciliation narration, anomaly flagging |
| 224 | Guest Messaging Copilot v1 | Context-aware draft replies using booking + guest data |
| 225 | AI Audit Trail | Log what AI saw, suggested, what was approved |

### Alternative Next Phases

| Phase | Option |
|-------|--------|
| 219 | CI/CD pipeline foundation (GitHub Actions, staging deploy) |
| 219 | Booking Conflict Resolution UI (frontend for conflict_auto_resolver) |
| 219 | Rakuten + Hostelworld outbound sync adapters (extend outbound layer to Tier 3) |

---

## Canonical Documents

| Doc | Path |
|-----|------|
| Roadmap | `docs/core/roadmap.md` |
| Current Snapshot | `docs/core/current-snapshot.md` |
| Work Context | `docs/core/work-context.md` |
| AI Strategy | `docs/core/planning/ai-strategy.md` |
| BOOT (rules for AI) | `BOOT.md` |

---

## Quick Orientation

```
src/
├── main.py                  # FastAPI app — all routers registered here
├── api/                     # All HTTP routers
│   ├── webhooks.py          # POST /webhooks/{provider} — OTA ingestion
│   ├── channel_map_router.py # CRUD /admin/properties/{id}/channels
│   ├── portfolio_dashboard_router.py  # GET /portfolio/dashboard
│   ├── integration_management_router.py # GET /admin/integrations
│   └── ... (40+ routers)
├── tasks/                   # Task system (automator, writer, SLA engine)
├── channels/                # LINE, WhatsApp, Telegram, SMS, Email
├── services/                # conflict_auto_resolver, outbound sync
└── adapters/                # 14 OTA adapters
tests/                       # 5,179 contract tests
docs/core/                   # Canonical documentation
```

**To run tests:** `PYTHONPATH=src python -m pytest` (all passing, no external deps needed)
