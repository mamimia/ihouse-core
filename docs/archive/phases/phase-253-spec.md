# Phase 253 — Staff Performance Dashboard API

**Status:** Closed
**Date Closed:** 2026-03-11

## Goal
Worker performance metrics for operations managers — completion rate, ACK time, SLA compliance, tasks/day, preferred channel.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/admin/staff/performance` | All workers aggregated |
| GET | `/admin/staff/performance/{worker_id}` | Individual drill-down |

## Metrics
completion_rate, avg_ack_minutes, sla_compliance_pct (5-min critical ACK), tasks_per_day, preferred_channel, kind_breakdown

## Files

| File | Change |
|------|--------|
| `src/api/staff_performance_router.py` | NEW |
| `src/main.py` | MODIFIED |
| `tests/test_staff_performance_contract.py` | NEW — 24 tests (7 groups) |

## Result
**24/24 tests pass. Full suite Exit 0.**
