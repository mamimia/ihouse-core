# Phase 262 — Guest Self-Service Portal API

**Status:** Closed
**Prerequisite:** Phase 261 (Webhook Event Logging)
**Date Closed:** 2026-03-11

## Goal

Read-only, guest-token-gated public endpoints giving guests secure access to their booking details, WiFi credentials, and house rules — without requiring an account.

## Architecture

- No JWT auth — gated via `X-Guest-Token` header
- Token validation is injectable (stub for CI, real JWT/short-link in production)
- No new DB tables — lookup_fn injectable (stub for CI)

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /guest/booking/{ref}` | Full booking overview: dates, access code, WiFi, rules, emergency contact |
| `GET /guest/booking/{ref}/wifi` | WiFi name + password only |
| `GET /guest/booking/{ref}/rules` | House rules list only |

**Error codes:** `401` bad token · `404` unknown booking

## Files

| File | Change |
|------|--------|
| `src/services/guest_portal.py` | NEW — GuestBookingView, validate_guest_token(), get_guest_booking(), stub_lookup() |
| `src/api/guest_portal_router.py` | NEW — 3 public endpoints |
| `src/main.py` | MODIFIED — guest_portal_router registered |
| `tests/test_guest_portal_contract.py` | NEW — 22 tests (5 groups) |

## Result

**~5,979 tests pass (+22), 0 failures. Exit 0.**
