# Storage, Retention & Archive Architecture
## iHouse Core -- Canonical Platform Behavior

> Phase 887d: Canonical definition of long-term storage strategy.

---

## Core Principle

DB stores metadata and path references.
Object storage stores bytes.
Never store binary data in Postgres.
Every file category has a defined retention policy.
Deletion requires proof. Archival requires verification.

---

## 1. Storage Buckets (7 total)

| Bucket | Public? | Purpose | Retention | Max file size |
|--------|---------|---------|-----------|--------------|
| `property-photos` | Public | Marketing + reference photos, cover images | Permanent | 5 MB |
| `cleaning-photos` | **Private** | Worker proof photos (before/after cleaning) | 12 months live, then archive | 10 MB |
| `guest-uploads` | Private | Guest check-in attachments, deposit evidence | Booking lifecycle + 90 days | 10 MB |
| `pii-documents` | Private | Passport/ID photos, sensitive guest docs | **90 days from checkout** (configurable) | 10 MB |
| `staff-documents` | Private | Worker ID, work permit, HR documents | While employed + 12 months | 10 MB |
| `exports` | Private | Admin CSV/PDF data exports | 30 days, auto-delete | 50 MB |
| `event-archives` | Private | Semi-annual audit archive packages | **Permanent** | 50 MB |

### Path convention

All buckets use tenant-scoped paths:
```
/{tenant_id}/{entity_type}/{entity_id}/{filename}
```

### Important: `cleaning-photos` must be private

Cleaning photos may contain guest belongings, room interiors, or privacy-sensitive content.
Public access is a liability. Access via signed URLs only.

---

## 2. Retention Matrix

| Category | Bucket | Live retention | Archive? | Auto-delete? |
|----------|--------|---------------|---------|-------------|
| Property marketing photos | `property-photos` | Permanent | No | No |
| Property reference photos | `property-photos` | Permanent | No | No |
| Cover photos | `property-photos` | Permanent | No | No |
| Cleaning proof photos | `cleaning-photos` | 12 months | Yes | After archive |
| Problem report photos | `cleaning-photos` | 12 months | Yes | After archive |
| Passport / ID photos | `pii-documents` | **90 days from checkout** | No -- hard delete | **Yes** |
| Guest deposit evidence | `guest-uploads` | Booking + 90 days | Yes | After settled |
| Damage deduction evidence | `guest-uploads` | Booking + 180 days | Yes | After dispute window |
| Staff identity docs | `staff-documents` | Employed + 12 months | Yes | After offboarding |
| Admin exports | `exports` | 30 days | No -- regenerable | **Yes** |
| Audit archives | `event-archives` | **Permanent** | N/A | Never |

---

## 3. PII Retention Rules

Passport/ID photos are the most sensitive category.

1. **Default TTL:** 90 days from guest checkout date
2. **Admin-configurable:** Some jurisdictions require longer retention (e.g., Thailand TM.30)
3. **Before deletion:** System verifies no active dispute or legal hold exists
4. **Deletion is hard delete:** Storage object removed. DB row retains event record only.
5. **Audit trail:** A `PII_DELETED` event is written to `event_log` recording the deletion

---

## 4. Thumbnail / Performance Pipeline

### Rendering tiers (Supabase Image Transformations)

| Tier | Size | Quality | Use case |
|------|------|---------|---------|
| Thumbnail | 200x200px | 60% | List cards, task cards, grid views |
| Preview | 600px wide | 70% | Detail pages, modal previews |
| Original | Full resolution | 100% | Download, print, zoom, legal evidence |

### URL pattern

```
Original:  /storage/v1/object/{bucket}/{path}
Thumbnail: /storage/v1/render/image/{bucket}/{path}?width=200&height=200&resize=cover
Preview:   /storage/v1/render/image/{bucket}/{path}?width=600&quality=70
```

### Frontend rules

1. **List pages:** Thumbnails only. Never fetch originals on list/grid views.
2. **Detail pages:** Previews. Originals only on explicit "View Full Size" or "Download".
3. **Lazy loading:** All images below the fold use `loading="lazy"`.
4. **Placeholder shimmer:** CSS placeholder while images load. Never blank/broken state.
5. **WebP default:** All new uploads stored as WebP where possible.
6. **No media JOIN on list queries:** List pages query metadata columns only. Photo URLs fetched per-card or from preloaded cache.

---

## 5. Media Archive / Offload Cycle

### For cleaning and problem-report photos

At the 12-month event_log archive cycle:
1. Bundle cleaning/problem photos older than 12 months into a media archive package
2. Store in `event-archives` bucket alongside the event_log archive
3. Archive manifest records all included files (name, size, checksum)
4. After admin confirmation, delete originals from `cleaning-photos`
5. Archive remains permanently in `event-archives`

### Projected volumes at scale

| Properties | Cleaning photos/year | Live storage | After 12-month offload |
|-----------|---------------------|-------------|----------------------|
| 10 | ~3,900 photos / ~80 MB | 80 MB | 0 (offloaded) |
| 50 | ~19,500 photos / ~400 MB | 400 MB | 0 (offloaded) |
| 100 | ~39,000 photos / ~800 MB | 800 MB | 0 (offloaded) |

The system remains lightweight at any property count because live storage never exceeds 12 months of accumulation.

---

## 6. Product UI Location

### Admin level

```
Admin -> Compliance
  |-- Audit Archives           (semi-annual event_log packages)
  |-- Media Archives           (annual cleaning/problem photo packages)
  |-- Data Retention Settings  (PII TTL, configurable per-tenant)
  |-- Export History           (30-day admin export downloads)
```

### Super-platform level

```
Super Platform -> All Tenants -> [Tenant X]
  |-- Audit Archives
  |-- Media Archives
  |-- Storage Usage
  |-- PII Deletion Audit Trail
```

---

## 7. Invariants

> **INV-STORAGE-01 -- PII auto-deletion:**
> Passport and ID photos must be automatically deleted 90 days after guest checkout. No manual intervention required. The system must verify no active dispute or legal hold exists before deletion.

> **INV-STORAGE-02 -- Cleaning photo privacy:**
> The `cleaning-photos` bucket must be private. Cleaning proof photos must only be accessible via signed URLs. Public access to cleaning photos is a privacy violation.

> **INV-STORAGE-03 -- Original preservation before offload:**
> Before any media offload/archive operation deletes original files from live Storage, the archive package must be verified as complete (checksum match, file count match) and admin must confirm.

---

*Phase 887d -- 2026-03-25*
