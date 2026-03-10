# Phase 190 — Manager Activity Feed UI

**Opened:** 2026-03-10  
**Closed:** 2026-03-10  
**Status:** ✅ Closed

## Goal

First read-surface consuming the Phase 189 `audit_events` table. Gives managers a live, filterable view of every operator and worker mutation that happened in the platform.

## New / modified files

| File | Change |
|------|--------|
| `ihouse-ui/app/manager/page.tsx` | NEW — full Manager Activity Feed page |
| `ihouse-ui/app/layout.tsx` | + `Manager` nav link in sidebar |
| `ihouse-ui/lib/api.ts` | + `AuditEvent`, `AuditEventListResponse` types + `api.getAuditEvents()` |

## Page features

### Activity Feed (`/manager`)
- **Stat row** — total events, task acked, task completed, flags updated
- **Live Mutations table** — 100 latest audit events, ordered newest first
  - Filter pills: All / Tasks / Bookings
  - Click any row to expand payload (from/to status, applied flags, etc.)
  - New-since-last-refresh rows highlighted with left blue border
- **Booking Audit Lookup panel** — enter any booking_id → shows its full audit trail

### Data source
- `GET /admin/audit` — Phase 189 endpoint, tenant-isolated
- Filters wired: `entity_type`, `entity_id`, `limit`

## API additions (`lib/api.ts`)

```typescript
export interface AuditEvent {
    id: number; actor_id: string; action: string;
    entity_type: string; entity_id: string;
    payload: Record<string, unknown>; occurred_at: string;
}

api.getAuditEvents({ entity_type?, entity_id?, actor_id?, limit? })
  → GET /admin/audit
```

## Build

```
✓ /manager compiled (static)
```

## Future (Phase 191+)
- Wire `actor_id` → real user name via permissions table
- Auto-refresh (30s polling)
- Export to CSV
