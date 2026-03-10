# Handoff to New Chat — Phase 208 Boundary

**Generated:** 2026-03-11
**System:** iHouse Core
**Last Phase:** 208 — Platform Checkpoint III
**Tests:** 5,049 passing. 0 failures. Exit 0.

---

## What iHouse Core Is

An event-sourced booking management kernel for short-term rental operators. Receives webhooks from 14 OTA providers, normalizes into canonical events, maintains booking state, generates operational tasks, runs SLA escalation across 3 live channels (LINE, WhatsApp, Telegram), tracks financials from ingestion to owner statements, and pushes outbound sync to connected channels.

## System Shape at Phase 208

| Layer | Key Stats |
|---|---|
| OTA Adapters | 14 live (Airbnb, Booking.com, Expedia, Agoda, Trip.com, Traveloka, Vrbo, Google VR, MakeMyTrip, Klook, Despegar, Rakuten, Hotelbeds, Hostelworld) |
| API Endpoints | ~50+ across 20 routers |
| UI Surfaces | 12 pages (ops dashboard, bookings, calendar, tasks, worker, financial, owner statement, owner portal, guests, admin settings, manager feed, admin DLQ) |
| Task Kinds | 6 (CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL, GUEST_WELCOME) |
| Channels | 3 live (LINE, WhatsApp, Telegram) + 2 stubs (SMS, Email) |
| Financial Rings | 6 (facts, aggregation, dashboard, reconciliation, cashflow, owner statements + PDF) |
| Tests | 5,049 passing, 0 failures |

## What Was Built in Phases 198–208

| Phase | Summary |
|---|---|
| 198 | Test Suite Stabilization — 4903 passing, 0 failed |
| 199 | RLS Audit — 0 security findings on 24 checked tables |
| 200 | Booking Calendar UI — /calendar month-view |
| 201 | Worker Channel Preference UI — GET/PUT/DELETE /worker/preferences |
| 202 | Notification History Inbox — GET /worker/notifications |
| 203 | Telegram Channel — telegram_escalation.py pure module |
| 204 | Docs Sync |
| 205 | DLQ Replay from UI — POST /admin/dlq/{id}/replay, /admin/dlq page |
| 206 | Pre-Arrival Guest Tasks — GUEST_WELCOME kind, pre_arrival_tasks.py, POST /tasks/pre-arrival/{booking_id} |
| 207 | Conflict Auto-Resolution — conflict_auto_resolver.py, POST /conflicts/auto-check/{booking_id}, auto-hooks in service.py |
| 208 | Platform Checkpoint III (this document) |

## Key Files to Read First

1. `docs/core/current-snapshot.md` — Full feature table + system status
2. `docs/core/work-context.md` — Key invariants, key files, env vars
3. `src/adapters/ota/service.py` — Ingestion spine (all post-APPLIED hooks)
4. `src/main.py` — All registered routers
5. `BOOT.md` — System rules, documentation authority hierarchy

## Technology Stack

- **Backend:** Python 3.14, FastAPI, Supabase (PostgreSQL + auth)
- **Frontend:** Next.js (ihouse-ui/), TypeScript
- **Tests:** pytest, ~5049 contract tests
- **Channels:** LINE Messaging API, WhatsApp Cloud API, Telegram Bot API

## Protocol for Next Chat

1. Read `BOOT.md` first — it defines documentation authority
2. Read `docs/core/current-snapshot.md` for system state
3. Read `docs/core/work-context.md` for invariants
4. **Do not auto-continue** — propose Phase 209+ based on understanding, not just incrementing
5. Run `PYTHONPATH=src .venv/bin/python -m pytest tests/ --tb=no -q` to verify baseline

## Proposed Next 10 Phases (209–218)

See the next-10-phases plan below for detailed rationale.
