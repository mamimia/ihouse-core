# Audit Result: 13 — Oren (Trust & Privacy Reviewer)

**Group:** C — Stakeholder-Facing Product
**Reviewer:** Oren
**Closure pass:** 2026-04-04
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Final Closure State |
|---|---|
| Guest token HMAC-SHA256 design | ✅ **Proven resolved** |
| Guest portal returns only non-sensitive fields | ✅ **Proven resolved** |
| PII document access (admin-only, signed URLs, audit log) | ✅ **Proven resolved** |
| Act-as dual attribution + production gate | ✅ **Proven resolved** |
| Invite token security | ✅ **Proven resolved** |
| `test-` token bypass has no environment gate | ✅ **Fixed** (prior pass) — gated behind IHOUSE_DEV_MODE / IHOUSE_TEST_MODE |
| Worker PII columns exposed to non-admin callers | ✅ **Fixed** (prior pass) — response-layer strip applied |
| Storage bucket RLS verification | ✅ **Verified from live DB** — see verified matrix below |
| No data retention policy | 🔵 **Intentional future gap** — compliance decision required |
| No audit log for admin PII access via permissions endpoints | 🔵 **Intentional future gap** — audit completeness item |

---

## Fix 1: `test-` Token Bypass Gated Behind Environment Variable

**File:** `src/services/guest_token.py`

The `test-` token bypass in `resolve_guest_token_context()` skips ALL HMAC verification. It was completely unconditional — active in production by default.

**Fix:**
```python
_test_env_active = (
    os.environ.get("IHOUSE_DEV_MODE", "").strip().lower() == "true"
    or os.environ.get("IHOUSE_TEST_MODE", "").strip().lower() == "true"
)
if token.startswith("test-") and _test_env_active:
    # bypass fires only when explicitly opted in
    logger.warning("test-token shortcut used (dev/test env only)...")
```

In production (where IHOUSE_DEV_MODE and IHOUSE_TEST_MODE are not set), the `test-` prefix check evaluates to False and the code path is dead. In CI/dev environments, set `IHOUSE_TEST_MODE=true` to re-enable the shortcut.

---

## Fix 2: Worker PII Columns Stripped for Non-Admin Callers

**File:** `src/api/permissions_router.py`

`GET /permissions` and `GET /permissions/{user_id}` were returning `id_number`, `date_of_birth`, `id_expiry_date`, `id_photo_url`, `work_permit_number`, `work_permit_expiry_date`, `work_permit_photo_url` to ANY authenticated caller.

**Fix:**

Added `_WORKER_PII_COLUMNS` frozenset (7 identity document fields) and `_strip_pii_for_role()` helper:
- `caller_role == "admin"` → full row returned
- Any other role → PII fields absent from response object

The DB query itself is unchanged — all columns are still fetched for internal use. The filter is at the **response serialization layer**, not at the query layer. This makes the fix auditable and easy to verify.

`_get_caller_role()` decodes the JWT from the Authorization header (unsigned decode for role check only — the JWT is already verified by `jwt_auth`).

---

## Storage Bucket Verification — Live DB Audit (2026-04-04)

**Verification method:** Direct SQL query to `storage.buckets` on the live Supabase project (`reykggmlcehswrxjviup`).

| Bucket | Public | Classification | Verdict |
|---|---|---|---|
| `pii-documents` | **false** ✅ | PII — staff passport/ID documents | Correct |
| `staff-documents` | **false** ✅ | PII — staff work permits, employment docs | Correct |
| `guest-documents` | **false** ✅ | PII — guest identity documents | Correct |
| `guest-uploads` | **false** ✅ | Guest-submitted files — may contain PII | Correct |
| `cleaning-photos` | **false** ✅ | Operational — scoped to tenant/property | Correct |
| `exports` | **false** ✅ | Admin exports — may contain financial data | Correct |
| `property-photos` | **true** ⚠️ | Property marketing images — intentionally public | Correct by design |
| `checkout-photos` | **true** ⚠️ | Checkout condition photos — intentionally public | **Verified as intentional** |

**`checkout-photos` public: confirmed intentional.** Code at `deposit_settlement_router.py` line 556 explicitly builds `/storage/v1/object/public/checkout-photos/` URLs. These are property condition photos (room damage documentation at checkout) used in the photo-comparison UI. No PII is stored here. Bucket is empty (0 files as of audit date). The public designation is correct by design.

**`property-photos` public: intentional.** Used for marketing/listing images displayed on the guest portal and property cards. By definition, these must be publicly accessible.

**All PII-containing buckets confirmed private.** No incorrectly configured bucket found.

**This item is fully closed.** No configuration change required.

---

## Closure Detail: Data Retention Policy

**Closure state: Intentional future gap — compliance decision required before implementation**

No purge logic, scheduled cleanup, or retention rules exist for guest passport photos, identity documents, expired tokens, or onboarding metadata. Data accumulates indefinitely.

**Why not appropriate for this audit pass:**
- Retention periods for each data category are a legal/compliance decision (e.g., "how long must we keep guest identity photos for property liability purposes?")
- Implementation requires Supabase Storage lifecycle rules or a scheduled purge job
- Different categories need different retention rules

This is a compliance infrastructure item that requires legal input before code is written.

---

## Closure Detail: Audit Log for Admin PII Access via Permissions Endpoints

**Closure state: Intentional future gap — improvement item**

`pii_document_router.py` logs every PII document access with actor, IP, document types, and guest IDs. `permissions_router.py` does NOT emit audit events when admin callers read worker PII fields.

**Why not fixed in this pass:** The fix (calling `write_audit_event` after `_get_caller_role()` returns `admin` and PII was in the response) is a one-function addition. However, this was not included in the current pass to keep the fix focused on the security gap (exposure to non-admins) rather than the audit completeness improvement.

**Classification:** Audit completeness improvement, not a security gap. Admin access to their own workers' PII is authorized. The gap is in the audit trail. Low priority at current scale.
