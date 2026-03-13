# Phase 428 — Environment Configuration Hardening

**Status:** Closed
**Prerequisite:** Phase 427 (Supabase Live Connection Verification)
**Date Closed:** 2026-03-13

## Goal

Ensure `.env.production.example` covers every env var documented in `current-snapshot.md`. Scan the codebase for hardcoded secrets.

## Invariant (if applicable)

No new invariants. All existing invariants preserved.

## Design / Files

| File | Change |
|------|--------|
| `.env.production.example` | MODIFIED — Added 12 missing env vars (token secrets, CORS, rate limiting, LINE, WhatsApp, Twilio, SendGrid) |

## Result

**12 missing env vars added. Zero hardcoded secrets found. All documented env vars now have production examples.**

Added vars: IHOUSE_GUEST_TOKEN_SECRET, IHOUSE_ACCESS_TOKEN_SECRET, IHOUSE_CORS_ORIGINS, IHOUSE_RATE_LIMIT_RPM, IHOUSE_LINE_SECRET, IHOUSE_WHATSAPP_PHONE_NUMBER_ID, IHOUSE_WHATSAPP_APP_SECRET, IHOUSE_WHATSAPP_VERIFY_TOKEN, IHOUSE_TWILIO_SID, IHOUSE_TWILIO_TOKEN, IHOUSE_TWILIO_FROM, IHOUSE_SENDGRID_KEY, IHOUSE_SENDGRID_FROM.
