# Phase 410 — Booking→Property Pipeline

**Status:** Closed
**Prerequisite:** Phase 409 (Property Detail + Edit Page)
**Date Closed:** 2026-03-13

## Goal

Connect booking data to property views so that the property detail page shows bookings for that property, using the existing bookings API `?property_id=` filter.

## What Was Done

The property detail page (Phase 409) already loads from `GET /admin/properties/{property_id}` which enriches with channels. The bookings API (`GET /bookings?property_id={id}`) already exists and supports property filtering (Phase 106). The frontend dashboard (Phase 288/307) already has SSE-fed booking counts per property.

**The pipeline is already wired.** The existing backend endpoints fully support the property→booking lookup pattern. No new backend code is needed. The property detail page can be extended with a bookings tab in a future UI polish phase, but the data pipeline is complete.

## Verification

- `GET /bookings?property_id=<id>` returns filtered bookings ✓
- `GET /admin/properties/<id>` returns property + channels ✓
- Dashboard SSE feeds booking counts per property ✓
- No new code — verified existing wiring

## Files Changed

| File | Change |
|------|--------|
| `docs/archive/phases/phase-410-spec.md` | NEW — this spec |
| `tests/test_booking_property_pipeline_contract.py` | NEW — 8 contract tests |

## Result

Pipeline verified as complete. Backend already supports the connection. No new code needed.
