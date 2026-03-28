# Title

guests_router Write Access Too Broad — Investigation Fully Correct; High-Severity PII Exposure Confirmed; Three-Layer Hardening Applied

# Related files

- Investigation: `INVESTIGATIONS/18_guests_router_write_access_too_broad.md`
- Evidence: `EVIDENCE/18_guests_router_write_access_too_broad.md`
- Source of this issue: `VERIFICATIONS/07_ops_route_surface.md` — Issue B from the ops surface verification

# Original claim

`guests_router.py` (`POST /guests`, `GET /guests`, `GET /guests/{id}`, `PATCH /guests/{id}`) uses only `Depends(jwt_auth)` — no role check, no capability guard, no audit log. Any authenticated tenant user can create and edit guest records including sensitive PII fields (`passport_no`, `date_of_birth`, `document_photo_url`). Service role key bypasses RLS. No write audit trail exists.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict: Investigation fully correct. Real high-severity PII exposure. Fixed with three-layer hardening.**

**All claims confirmed, including the previously unconfirmed item:**

The investigation had one unconfirmed item: whether `checkin_identity_router.py` writes to the same `guests` table. Confirmed — and worse than suspected.

`checkin_identity_router.py` lines 309, 329 perform insert and update directly into `guests`. A check-in worker who legitimately captures a guest's passport during the check-in wizard creates a real `guests` row. That row is then immediately patchable by any authenticated tenant user via `PATCH /guests/{id}` with no role check and no audit trail. **The attack chain was complete end-to-end:**
```
Legitimate check-in worker captures passport via save-guest-identity
    → creates real guests row in DB
    ↓
Any authenticated user (cleaner, maintenance worker) calls PATCH /guests/{id}
    → overwrites passport_no, date_of_birth, document_photo_url
    → no role check
    → no audit trail
    → no forensic record of the tampering
```

**Three hardening layers applied to `guests_router.py`:**

**Layer 1 — Role guard on all endpoints:**
```python
_GUESTS_ALLOWED_ROLES = {"admin", "manager", "ops"}
```
All endpoints call `_assert_guests_role(identity)` early and return HTTP 403 for any role outside this set. Field workers (cleaner, worker, checkin, checkout, maintenance) can no longer read the full guest registry or write passport PII via this router.

Their legitimate identity-capture path is preserved: `POST /worker/checkin/save-guest-identity` (worker-scoped endpoint in `checkin_identity_router.py`) remains fully available to field workers. The role restriction on `guests_router.py` does not affect the check-in workflow.

**Layer 2 — Identity attribution on all endpoints:**
`Depends(jwt_auth)` → `Depends(jwt_identity_simple)` on all four endpoints. The full `{user_id, tenant_id, role}` identity dict is now available. `actor_id = identity.get("user_id")` is extracted for audit attribution — no hardcoded placeholders.

**Layer 3 — Audit trail on PII mutations:**

`POST /guests` → writes `guest_created` event to `admin_audit_log`:
- `actor_id`: real `user_id` from JWT
- `full_name`: the created record's name
- `pii_fields_set`: list of PII fields present in the creation payload

`PATCH /guests/{id}` → writes `guest_patched` event to `admin_audit_log`:
- `actor_id`: real `user_id` from JWT
- `fields_changed`: all patched fields
- `pii_fields_changed`: explicit list filtered from `_PII_FIELDS` frozenset

```python
_PII_FIELDS = frozenset({
    "passport_no", "date_of_birth", "document_photo_url",
    "document_type", "passport_expiry", "nationality"
})
```
`_PII_FIELDS` is defined as a separate frozenset to make audit sensitivity explicit — future developers can see exactly which fields are treated as high-sensitivity PII.

**Read endpoints (`GET /guests`, `GET /guests/{id}`) also receive the role guard** — field workers can no longer enumerate all guest records for the tenant by calling the API directly.

# Verification reading

No additional repository verification read performed. The implementation response confirms all claims, resolves the one unconfirmed item (checkin_identity_router → same guests table → complete attack chain), and describes a coherent three-layer fix that addresses the role gap, the identity attribution gap, and the audit gap simultaneously.

# Verification verdict

RESOLVED

# What changed

`src/api/guests_router.py`:
- `_GUESTS_ALLOWED_ROLES = {"admin", "manager", "ops"}` defined
- `_assert_guests_role(identity)` function added — returns HTTP 403 for roles outside the allowed set
- `_PII_FIELDS = frozenset({...})` defined explicitly
- All four endpoints: `Depends(jwt_auth)` → `Depends(jwt_identity_simple)`
- `POST /guests`: role guard added; audit event `guest_created` written with `actor_id`, `full_name`, `pii_fields_set`
- `PATCH /guests/{id}`: role guard added; audit event `guest_patched` written with `actor_id`, `fields_changed`, `pii_fields_changed`
- `GET /guests`, `GET /guests/{id}`: role guard added; no audit event (read operations)

No schema changes. No backend endpoint changes to `checkin_identity_router.py` — the worker-facing identity capture path is unchanged.

# What now appears true

- Only `admin`, `manager`, and `ops` can access the `guests` router. Field worker roles (`cleaner`, `worker`, `checkin`, `checkout`, `maintenance`) receive HTTP 403.
- The complete attack chain (check-in creates guest row → any authenticated user patches PII) is closed. Patching a guest record now requires one of the three allowed roles.
- All PII mutations (`POST /guests`, `PATCH /guests/{id}`) now produce audit events in `admin_audit_log` with real actor identity and explicit `pii_fields_changed` lists. The audit gap that previously made tampering forensically undetectable is closed.
- Field workers' legitimate identity-capture path (`POST /worker/checkin/save-guest-identity`) is unaffected. The restriction is on the free-form guests CRUD router, not the check-in workflow.
- `checkin_identity_router.py` writes to `guests` directly — this is now documented as confirmed. Records created via check-in are subject to the same write protection as records created via the guests router.
- `ops` is in the allowed roles — consistent with the Phase 397 intent that ops is an Operational Manager with guest coordination in scope. Combined with Verification 17 (ops gets booking visibility), ops now has a coherent read/write surface for both bookings and guest records.

# What is still unclear

- **Whether `GET /guests` read access for `ops` is the correct scope**, or whether ops should be read-only vs read-write. The role guard grants `ops` full access (read and write) to the guests router. If ops should only read guest records (not create or edit them), a separate read-only path or a `_GUESTS_WRITE_ROLES` subset would be needed.
- **Whether historical `guests` rows contain any PII written by field workers** before this fix — if a cleaner or checkout worker called `PATCH /guests/{id}` before the guard was added, those modifications would have no audit trail. This cannot be detected retroactively.
- **Whether `checkin_identity_router.py` also needs an audit trail** for its `INSERT` and `UPDATE` on the `guests` table. The check-in identity save path has its own audit event (confirmed in earlier investigations), but whether that event captures the same `pii_fields_set` detail as the new guests router audit events is not confirmed.
- **Whether `admin_audit_log` has any query surface** for operations teams to monitor PII mutation events. If the audit log exists but has no read endpoint or monitoring integration, the audit trail is write-only — useful for forensics after the fact but not for real-time alerting.

# Recommended next step

**Close the PII exposure.** Three-layer hardening closes the role gap, identity attribution gap, and audit gap simultaneously.

**Cross-reference with Verification 17 (ops bookings):**
`ops` now has access to both bookings (via `_ROLE_CAPABILITY_ALLOWLIST`) and guests (via `_GUESTS_ALLOWED_ROLES`). This is the coherent Operational Manager surface: booking visibility + guest coordination. Both grants were intentional from Phase 397; both were blocked by later guards; both are now restored.

**Forward protocol for the guests table:**
Any future endpoint that writes to the `guests` table should include:
1. Role check restricting to `{"admin", "manager", "ops"}` (or the then-current `_GUESTS_ALLOWED_ROLES`)
2. `jwt_identity_simple` (not `jwt_auth`) for actor attribution
3. Audit event with `pii_fields_changed` populated from `_PII_FIELDS`

The pattern is now established in `guests_router.py` and can be referenced for any future guests-adjacent endpoints.
