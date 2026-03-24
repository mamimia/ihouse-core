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
| `pii-documents` | Private | **Guest** passport/ID photos captured during check-in | **90 days from checkout** (configurable) | 10 MB |
| `staff-documents` | Private | Worker ID, work permit, HR docs, **staff identity/employment documents** | **While employed + 12 months** | 10 MB |
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
| **Guest** passport/ID photos | `pii-documents` | **90 days from checkout** | No -- hard delete | **Yes -- automatic** |
| Guest deposit evidence | `guest-uploads` | Booking + 90 days | Yes | After settled |
| Damage deduction evidence | `guest-uploads` | Booking + 180 days | Yes | After dispute window |
| **Staff** identity/employment docs | `staff-documents` | **While employed + 12 months** | Yes -- HR archive | **No -- never auto-deleted** |
| Admin exports | `exports` | 30 days | No -- regenerable | **Yes** |
| Audit archives | `event-archives` | **Permanent** | N/A | Never |

---

## 3. Identity Document Retention Rules

**Guest and staff identity documents are different categories with different rules.**

### 3a. Guest identity documents (check-in captures)

Examples: guest passport photo, guest ID captured during check-in, temporary identity images tied to a stay.

1. **Bucket:** `pii-documents`
2. **Default TTL:** 90 days from guest checkout date
3. **Admin-configurable:** Some jurisdictions require longer retention (e.g., Thailand TM.30)
4. **Before deletion:** System verifies no active dispute or legal hold exists
5. **Deletion is hard delete:** Storage object removed. DB row retains event record (upload/deletion timestamp) only.
6. **Audit trail:** A `PII_DELETED` event is written to `event_log` recording the deletion
7. **Auto-deletion:** Yes -- system runs this automatically, no admin action required

### 3b. Staff identity / employment documents

Examples: staff passport, staff ID, work permit, employment contract photos, any permanent identity or HR document.

1. **Bucket:** `staff-documents`
2. **Retention:** While employed + 12 months after offboarding
3. **Admin-configurable:** Yes -- admin may extend per local labor law requirements
4. **Auto-deletion:** **NO** -- staff documents are never auto-deleted
5. **Archive on offboarding:** When a staff member is offboarded, their documents remain accessible for 12 months, then are archived (bundled into HR archive, originals removed from live Storage)
6. **Access:** Admin only -- workers can view their own documents but cannot delete them
7. **The system must never apply guest-document deletion logic to staff documents**

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

### Storage invariants

> **INV-STORAGE-01 -- Guest PII auto-deletion (guest documents only):**
> Guest passport/ID photos captured during check-in must be automatically deleted 90 days after checkout. No manual intervention required. The system must verify no active dispute or legal hold exists before deletion. **This rule applies only to guest identity documents. Staff identity/employment documents are never auto-deleted.**

> **INV-STORAGE-02 -- Cleaning photo privacy:**
> The `cleaning-photos` bucket must be private. Cleaning proof photos must only be accessible via signed URLs. Public access to cleaning photos is a privacy violation.

> **INV-STORAGE-03 -- Original preservation before offload:**
> Before any media offload/archive operation deletes original files from live Storage, the archive package must be verified as complete (checksum match, file count match) and admin must confirm.

### Lightweight media invariants (canonical platform rules)

> **INV-MEDIA-01 -- No binary in Postgres:**
> The application database must never store image/file binary data (bytea, base64 strings, data URIs). DB columns store only the Storage path or URL reference. The binary lives in Supabase Storage.

> **INV-MEDIA-02 -- Correct bucket routing:**
> Every file must be uploaded to the bucket that matches its category. No bucket may be used as a catch-all. Staff files -> `staff-documents`. PII -> `pii-documents`. Property photos -> `property-photos`. Cleaning photos -> `cleaning-photos`. Never cross-route.

> **INV-MEDIA-03 -- Thumbnail-first rendering:**
> List pages and card views must render thumbnails (200x200px, 60% quality) via Supabase Image Transformations. Detail pages render previews (600px, 70%). Originals load only on explicit user action. No list page may load original-resolution images.

> **INV-MEDIA-04 -- Lazy loading:**
> All images below the initial viewport must use `loading="lazy"` or `IntersectionObserver`. No page may attempt to load all images on mount.

> **INV-MEDIA-05 -- Metadata-only list queries:**
> List/grid page queries must select only metadata columns. File URL columns should not be included in bulk list queries. Photo URLs are resolved per-card during render.

> **INV-MEDIA-06 -- Retention assignment required:**
> Every new file category must have a defined retention policy before the upload flow is implemented. No file category may exist without a documented retention period and archival/deletion rule.

---

## 8. Bucket Routing Rules

| Upload source | Correct bucket | Never use |
|--------------|---------------|-----------|
| Property gallery/reference/cover | `property-photos` | -- |
| Staff profile/avatar photos | `staff-documents` | `property-photos` |
| Staff ID/work permit photos | `pii-documents` or `staff-documents` | `property-photos` |
| Cleaning/problem proof photos | `cleaning-photos` | `property-photos` |
| Guest passport/ID | `pii-documents` | any public bucket |
| Guest deposit evidence | `guest-uploads` | any public bucket |
| Pre-onboarding staging uploads | `property-photos` (staging/ path) | -- |
| Admin exports | `exports` | -- |
| Audit archives | `event-archives` | -- |

**After property approval:** staging files must be migrated to the property's permanent path and staging originals must be deleted.

---

## 9. New Media Category Onboarding Checklist

Before adding any new image/file feature, the developer must complete:

1. **Category name** and business justification
2. **Bucket assignment** -- which of the 7 buckets, or justify a new one
3. **Privacy level** -- public, signed-URL, or service-role-only
4. **Path structure** -- `/{tenant_id}/{type}/{entity_id}/{filename}`
5. **Retention policy** -- live duration, archive or delete, auto-delete
6. **DB reference** -- table, column (TEXT type, path only, no binary)
7. **Rendering tiers** -- thumbnail, preview, original URL patterns
8. **Frontend rules** -- lazy loading, shimmer placeholder, no bulk URL fetch
9. **Upload limits** -- max file size, allowed MIME types
10. **Cleanup rules** -- on entity deletion, staging cleanup, orphan prevention

**This checklist must be completed before upload code is merged.**

---

## 10. Current-State Findings (2026-03-25 audit)

| Finding | Severity | Status |
|---------|----------|--------|
| Staff PII files (2) in public `property-photos` bucket | **CRITICAL** | Needs immediate fix |
| Staff onboarding photos (21) misrouted to `property-photos` | Medium | Fix routing, migrate existing |
| Staging files (31, 18 MB) never cleaned after approval | Medium | Add post-approval cleanup |
| Orphaned files (12) for deleted properties still in Storage | Low | Add Storage cascade to property delete |
| `cleaning-photos` bucket is public, should be private | Medium | Change to private |

---

*Phase 887d -- 2026-03-25*
