# Phases 803–811 — PMS Connector Layer (Foundation + Guesty MVP)

**Status:** Closed
**Prerequisite:** Phase 802 (Operational Day Simulation)
**Date Closed:** 2026-03-15

## Goal

Build the PMS (Property Management System) connector layer: abstract adapter base, Guesty OAuth2 implementation, property discovery, booking fetch with status/financial mapping, normalization pipeline, and 5-endpoint REST API.

## Phase Breakdown

| Phase | Title |
|-------|-------|
| 803 | `pms_connections` table + guesty/hostaway in provider_capability_registry |
| 804 | PMSAdapter abstract base class + data classes (PMSProperty, PMSBooking, PMSAuthResult, PMSSyncResult) |
| 805–807 | GuestyAdapter — OAuth2 auth, property discovery (pagination), booking fetch (status mapping, financials) |
| 808–809 | pms_connect_router.py — 5 endpoints (connect, discover, map, sync, list) |
| 810 | PMS normalizer — PMSBooking → booking_state + event_log (new/update/cancel detection) |
| 811 | Full ingest pipeline wired end-to-end |

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/pms/__init__.py` | NEW — package init |
| `src/adapters/pms/base.py` | NEW — PMSAdapter ABC + data classes (141 lines) |
| `src/adapters/pms/guesty.py` | NEW — GuestyAdapter: OAuth2, property discovery, booking fetch (257 lines) |
| `src/adapters/pms/normalizer.py` | NEW — PMSBooking → booking_state + event_log (162 lines) |
| `src/api/pms_connect_router.py` | NEW — 5 REST endpoints (417 lines) |
| `src/main.py` | MODIFIED — router registration |

## Result

**979 lines of new code. Pipeline wired end-to-end.**

Endpoints:
- `POST /integrations/pms/connect` — initiate PMS connection
- `GET /integrations/pms/{id}/discover` — discover properties from PMS
- `POST /integrations/pms/{id}/map` — map PMS property to iHouse property
- `POST /integrations/pms/{id}/sync` — sync bookings from PMS
- `GET /integrations/pms` — list all PMS connections
