# Phase 358 — Outbound Sync Interface Hardening (Closed) — 2026-03-12

## Category
🏗️ Architecture / Interface Contract

## Changes

### `src/adapters/outbound/__init__.py` — OutboundAdapter base class
- Added formal `cancel()` stub: returns `dry_run` (unsupported) by default
- Added formal `amend()` stub: returns `dry_run` (unsupported) by default
- Updated base class docstring: Tier A implements send/cancel/amend; Tier B/C implements push/cancel
- Updated `push()` signature to include `check_in`/`check_out` kwargs (alignment with ical_push_adapter)
- Updated `send()` error message to reference method name explicitly

### `src/services/outbound_executor.py` — Event-type routing
- Removed `hasattr(adapter, 'cancel')` and `hasattr(adapter, 'amend')` duck-typing guards
- Routing now purely based on `event_type` string — cleaner and more predictable
- Added Phase 358 attribution comments

### `tests/test_executor_event_type_routing.py` — Backward-compat tests
- Updated `test_c2` and `test_c3` to test the new base-class contract (dry_run instead of send fallback)

## Before vs After

| Before | After |
|--------|-------|
| Executor: `hasattr(adapter, 'cancel')` duck-typed | Executor: always calls `.cancel()` / `.amend()` |
| Base: no cancel/amend → `hasattr()` → fallback to send | Base: cancel/amend return dry_run |
| Interface: implicit (runtime duck-typing) | Interface: explicit (formal method stubs) |

## Tests
- 63 tested (event_type routing + cancel contract + amend contract): all pass ✅
- Full suite: 7,043 passed, 9 failed (infra/Supabase only), 17 skipped
