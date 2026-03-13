# iHouse Core — Supabase Schema Reference

**Last updated: Phase 418 (2026-03-13)**

## Migration Files (16)

| # | File | Phase | Description |
|---|------|-------|-------------|
| 1 | `20260308174500_phase39_dlq_replay_columns.sql` | 39 | DLQ replay columns |
| 2 | `20260308184200_phase40_dlq_summary_view.sql` | 40 | DLQ summary view |
| 3 | `20260308192000_phase44_ordering_buffer.sql` | 44 | Ordering buffer table |
| 4 | `20260308210000_phase50_step2_apply_envelope_amended.sql` | 50 | apply_envelope amended support |
| 5 | `20260309180000_phase114_tasks_table.sql` | 114 | Worker tasks table |
| 6 | `20260311120000_phase230_ai_audit_log.sql` | 230 | AI audit log table |
| 7 | `20260311143000_phase232_pre_arrival_queue.sql` | 232 | Pre-arrival guest queue |
| 8 | `20260311150000_phase234_worker_availability.sql` | 234 | Worker shift availability |
| 9 | `20260311152100_phase236_guest_messages_log.sql` | 236 | Guest message history |
| 10 | `20260311164500_phase246_rate_cards.sql` | 246 | Rate cards / pricing rules |
| 11 | `20260311165100_phase247_guest_feedback.sql` | 247 | Guest feedback collection |
| 12 | `20260311165500_phase248_task_templates.sql` | 248 | Maintenance task templates |
| 13 | `20260311220000_phase274_core_schema_baseline.sql` | 274 | **Baseline** — consolidated all schemas from Phases 1-273 |
| 14 | `20260311230000_phase277_event_kind_booking_amended.sql` | 277 | Event kind for BOOKING_AMENDED |
| 15 | `20260311230100_phase277_booking_state_guest_id.sql` | 277 | guest_id column on booking_state |
| 16 | `20260313190000_phase399_access_tokens.sql` | 399 | Access token table |

## Core Tables (from baseline migration #13)

The baseline migration consolidates:
- `event_log` — append-only canonical events
- `booking_state` — read model for booking current state
- `booking_financial_facts` — financial data projection
- `property` — property metadata
- `channel_map` — OTA channel-property mappings
- `tasks` — worker task assignments
- `notification_channels` — per-worker notification preferences

## Historical Note

Early phases (1-273) used direct SQL editor changes in Supabase. Phase 274 consolidated all tables into `core_schema_baseline.sql`. From Phase 274 onward, all schema changes are tracked as individual migration files.
