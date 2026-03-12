# Phase 350 — API Smoke Tests

**Closed:** 2026-03-12
**Category:** 🔍 Testing / API Coverage
**Test file:** `tests/test_api_smoke_p350.py`

## Summary

Comprehensive API smoke tests exercising all critical endpoint groups.
Verifies route existence, HTTP methods, response shapes, health checks,
and route count invariants. Covers 167+ registered routes via TestClient.

## Tests Added: 30

### Group A — Health + Readiness (5 tests)
- /health 200|503, version+env fields, /readiness, /integration-health, /openapi.json

### Group B — Core API Smoke (6 tests)
- /bookings, /tasks, /financial, /properties, /conflicts, /permissions

### Group C — Admin Endpoints (6 tests)
- /admin/summary, /admin/dlq, /admin/webhook-log (+stats), /admin/org, /docs

### Group D — Webhook + Notification (4 tests)
- Route checks: webhooks/{provider}, line/webhook, notifications/send-sms, /notifications/log

### Group E — Auth + Worker (4 tests)
- /auth/me, /auth/token validation, /worker/tasks, /guest/verify-token

### Group F — Route Discovery (5 tests)
- ≥100 routes, critical paths exist, ≥20 admin routes, ≥5 AI routes, portal routes

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 6,970 | 7,000 |
| Test files | 233 | 234 |
| New tests | — | 30 |
