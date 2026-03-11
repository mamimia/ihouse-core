# Phase 246 — Rate Card & Pricing Rules Engine

**Status:** Closed
**Prerequisite:** Phase 245 (Platform Checkpoint VIII)
**Date Closed:** 2026-03-11

## Goal

Enable operators to set base rates per (property, room_type, season, currency) and automatically
detect when incoming OTA booking prices deviate by more than ±15% from those rates.

## New Table

**`rate_cards`** (migration: `20260311164500_phase246_rate_cards.sql`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| tenant_id | TEXT | RLS scoped |
| property_id | TEXT | which property |
| room_type | TEXT | e.g. "standard", "deluxe" |
| season | TEXT | e.g. "high", "low" |
| base_rate | NUMERIC(12,2) | price per night |
| currency | TEXT | default "THB" |
| created_at / updated_at | TIMESTAMPTZ | auto-managed |

Unique constraint: `(tenant_id, property_id, room_type, season)`. RLS enabled.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/properties/{id}/rate-cards` | List all rate cards for a property |
| `POST` | `/properties/{id}/rate-cards` | Create / upsert a rate card |
| `GET` | `/properties/{id}/rate-cards/check` | Check price deviation (±15% alert) |

## Files

| File | Change |
|------|--------|
| `supabase/migrations/20260311164500_phase246_rate_cards.sql` | NEW |
| `src/services/price_deviation_detector.py` | NEW — pure function, no DB writes |
| `src/api/rate_card_router.py` | NEW — GET list, POST upsert, GET /check |
| `src/main.py` | MODIFIED — registered rate_card_router |
| `tests/test_rate_card_contract.py` | NEW — 35 contract tests (10 groups) |

## Result

**~5,730 tests pass. 0 failures. Exit 0.**
35 new contract tests across 10 groups.
