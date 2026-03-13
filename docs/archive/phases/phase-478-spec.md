# Phase 478 — Backup & Recovery Protocol

**Status:** Closed  **Date:** 2026-03-13

## Goal
Document and verify backup and recovery procedures for production.

## Protocol

### Supabase Automated Backups
- **Free/Pro:** Daily automatic backups (7-day retention)
- **Pro+:** Point-in-time recovery (PITR) available
- **Access:** Supabase Dashboard → Project Settings → Database → Backups

### Application-Level Recovery
- **Event Log:** Append-only `event_log` table — source of truth. All state is re-derivable from events.
- **booking_state:** Projection table — can be reconstructed from `event_log` replay.
- **booking_financial_facts:** Append-only — no mutation, safe to restore from backup.
- **DLQ:** `ota_dead_letter` has `replayed_at` column — safe to replay unreplayed events.

### Disaster Recovery Steps
1. Restore Supabase DB from backup (Dashboard → Backups)
2. Verify `event_log` integrity: `SELECT count(*) FROM event_log`
3. If booking_state inconsistent: trigger re-projection from event_log
4. Verify health: `GET /health` → status=ok

## Result
**Backup protocol documented. Supabase handles DB backups. Event-sourced architecture enables state reconstruction from event_log.**
