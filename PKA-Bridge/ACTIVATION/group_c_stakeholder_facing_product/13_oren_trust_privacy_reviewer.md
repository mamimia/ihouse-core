# Activation Memo: Oren — Trust & Privacy Reviewer

**Phase:** 973 (Group C Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (src/services/guest_token.py, src/api/guest_portal_router.py, pii_document_router.py, act_as_router.py, staff_onboarding_router.py, invite_router.py, auth.py, capability_guard.py, permissions_router.py)
**Builds on:** Group A (414 auth deps, capability guards), Group B (staffApi session isolation, Preview/Act-as mechanisms, worker PII columns)

---

## 1. What in the Current Real System Belongs to This Domain

Oren's domain is trust boundaries and sensitive data exposure. The real system has these trust-sensitive areas:

- **Guest token system**: HMAC-SHA256 with constant-time comparison, hash-only storage, 7-day TTL, booking-scoped, revocation support
- **Guest portal data scoping**: Token scoped to specific booking_ref. No financial data exposed. No cross-booking access
- **PII document handling**: Admin-only access with 5-minute signed URLs. Audit logging of every PII access. Passport photos redacted in API responses
- **Act-as audit trail**: Dual attribution (real_admin_id + effective_user_id). Production gate (disabled in prod). 4-hour max TTL. Session start/end events
- **Worker PII**: id_number, date_of_birth, work_permit data in tenant_permissions. Stored in onboarding flow metadata
- **Dev mode bypass**: IHOUSE_DEV_MODE flag must be explicit opt-in. Bypasses JWT verification
- **Invite token security**: SHA-256 hash storage, single-use enforcement, INVITABLE_ROLES guard (no admin via invite)

## 2. What Appears Built

- **Guest token HMAC-SHA256 (PROVEN SECURE)**: `guest_token.py` implements proper HMAC signing with `hmac.compare_digest()` for constant-time comparison. Token format: `{booking_ref}:{guest_email}:{exp_timestamp}` signed and base64url-encoded. Only SHA-256 hash stored in DB. 7-day default TTL with expiry validation. Booking-scoped validation prevents cross-booking access. DB-backed revocation via `is_guest_token_revoked()`. Minimum secret length 32 bytes (RFC 7518 §3.2).

- **Guest portal data scoping (PROVEN CORRECT)**: `guest_portal_router.py` returns only non-sensitive fields: booking_ref, property_name, dates, guest_name, wifi, access_code, house_rules, emergency_contact, status. NO financial data exposed to guests. NO deposit amounts. NO worker information. Single-booking access enforced by token validation.

- **PII document access control (PROVEN)**: `pii_document_router.py` restricts passport/identity document access to `role == "admin"` only. Signed URLs with 5-minute expiry (`_SIGNED_URL_EXPIRY_SECONDS = 300`). Every access logged with actor_id, IP, document types, guest_ids. Passport photos in API responses are redacted to `***` with boolean flags (`passport_photo_captured`, `signature_recorded`) instead.

- **Act-as audit trail (PROVEN ROBUST)**: `act_as_router.py` preserves `real_admin_id` in JWT payload. `acting_sessions` table records real_admin_user_id, acting_as_role, acting_as_user_id, expires_at, ended_at. Explicit `ACT_AS_STARTED` and `ACT_AS_ENDED` audit events. 4-hour max TTL. Person-specific flag in JWT. **Critical note**: Act-as is architecturally disabled in production (line 128).

- **Invite token security (PROVEN)**: SHA-256 hash storage. Single-use via `used_at` field check. Revocation via `revoked_at`. INVITABLE_ROLES guard prevents admin creation via invite. Two-stage validation: crypto verification + DB state check.

- **Dev mode gating (PROVEN APPROPRIATE)**: `auth.py` requires explicit `IHOUSE_DEV_MODE="true"` environment variable. Not a default. Bypasses JWT verification with hardcoded dev tenant. Appropriate for development only.

- **Bookings endpoint does NOT over-fetch guest PII**: `/bookings` returns guest_name only — no guest_phone, guest_email. Worker task endpoints never include financial data (explicit invariant in worker_router.py line 32).

## 3. What Appears Partial

- **Worker PII column filtering**: PII columns (id_number, date_of_birth, work_permit_number, work_permit_photo_url, id_expiry_date) exist in tenant_permissions. When `/permissions` or worker listing endpoints return staff data, whether these columns are filtered for non-admin roles was not confirmed. If the response includes all columns, managers or ops users could see worker identity documents.

- **Guest token test shortcut**: `resolve_guest_token_context()` (line 247) accepts tokens prefixed with `test-` without HMAC verification. This is appropriate for CI/test environments but must be gated by environment flag. Whether this shortcut is active in production was not confirmed.

- **Storage bucket RLS policies**: Signed URL mechanism is correct for PII buckets (passport-photos, signatures, staff-documents, guest-documents). But the Supabase storage bucket RLS policies are NOT visible in the examined migrations. If any PII bucket is configured as public, signed URLs provide no additional protection and URLs could be guessable.

## 4. What Appears Missing

- **No data retention policy**: No purge logic for guest passport photos, expired tokens, completed booking data, or onboarding metadata. Passport photos, identity documents, and cash deposit photos appear to be retained indefinitely. No scheduled cleanup visible.

- **No PII access audit for worker listings**: PII document access is audit-logged (proven). But accessing worker PII via the permissions/staff listing endpoints does NOT appear to have equivalent audit logging. An admin viewing id_number or work_permit_photo_url via the staff detail page would not generate an audit event.

- **No rate limiting on guest token endpoints**: Guest portal endpoints validate the token but no rate limiting on failed attempts was observed. An attacker could brute-force booking_ref values (though the HMAC signature prevents token forgery).

- **No field-level access control on API responses**: The system uses route-level (middleware) and endpoint-level (role guard) access control. But there's no response-level field filtering based on the caller's role. If an endpoint returns all columns, every authorized caller sees all fields.

**Open question impact — worker disable / task safety (#5)**: If a deactivated worker's session tokens remain valid (no explicit token revocation on deactivation), they could continue accessing the system until token expiry. This is a trust boundary gap — deactivation should invalidate active sessions.

## 5. What Appears Risky

- **Storage bucket misconfiguration**: If any PII storage bucket (passport-photos, signatures, staff-documents) is public in Supabase, the entire signed-URL mechanism is security theater. URLs follow predictable patterns (`{tenant_id}/{task_id}/{room_label}_{uuid}.{ext}`). Public buckets would allow URL enumeration.

- **Worker PII in onboarding metadata**: `access_tokens.metadata.worker_data` contains plaintext PII (email, phone, emergency_contact) during the onboarding approval window. If the access_tokens table is accessible to non-admin queries, this data is exposed.

- **No session invalidation on deactivation**: Group B (Hana) identified that worker deactivation doesn't handle tasks. Oren adds: deactivation also doesn't appear to invalidate active JWT tokens. A deactivated worker's token remains valid until expiry. Middleware may check `is_active` on each request (needs verification), but if not, deactivated workers retain access.

## 6. What Appears Correct and Worth Preserving

- **Guest token design**: HMAC-SHA256, constant-time comparison, hash-only storage, booking-scoped, revocable, 7-day TTL. This is textbook correct for transient portal access.
- **PII redaction in API responses**: Passport photos never returned in API responses. Boolean flags instead. This prevents accidental PII exposure through API logs or caches.
- **5-minute signed URLs for PII documents**: Time-limited access. After 5 minutes, the URL is invalid. Correct for view-once-then-close workflows.
- **PII access audit logging**: Every access to passport/identity documents logged with actor, IP, and context. Full traceability.
- **Act-as dual attribution**: Both the real admin and the acted-as user are recorded. Mutations are traceable to the responsible admin.
- **Financial data isolation from worker surfaces**: Worker router explicitly states "NEVER writes to booking_financial_facts." Workers don't see financial data in their task payloads.
- **INVITABLE_ROLES guard**: Cannot create admin via invite. Structural privilege escalation prevention.

## 7. What This Role Would Prioritize Next

1. **Verify Supabase storage bucket RLS policies**: Examine actual bucket configurations for passport-photos, signatures, staff-documents, guest-documents. Confirm all are private.
2. **Add field-level filtering for worker PII**: Ensure id_number, date_of_birth, work_permit data are NOT returned in staff listing endpoints for non-admin roles.
3. **Implement data retention policy**: Define purge schedules for guest documents, expired tokens, and completed booking PII.
4. **Verify is_active check in middleware**: Confirm that deactivated workers are blocked at middleware level, not just UI level.
5. **Gate test token shortcut by environment**: Ensure `test-` prefix bypass in guest_token.py is disabled in production.

## 8. Dependencies on Other Roles

- **Daniel (Group A)**: Oren reviews what's exposed; Daniel defines who should see what. They collaborate on whether the permission model adequately protects PII.
- **Hana (Group B)**: Hana's deactivation gap has trust implications — Oren flags that deactivation should also invalidate sessions.
- **Yael**: Oren reviews guest portal security; Yael designs the guest experience. They share the guest token as the trust boundary.
- **Marco (Group B)**: Marco owns worker mobile surfaces. Oren reviews whether those surfaces expose data beyond the worker's trust boundary.

## 9. What the Owner Most Urgently Needs to Understand

The trust and privacy posture is stronger than typical early-stage property management platforms. Guest tokens use proper HMAC with constant-time comparison. PII access is admin-only with signed URLs and audit logging. Financial data is isolated from worker surfaces. The Act-as system has robust dual attribution.

Two areas need immediate verification:

1. **Storage bucket RLS policies**: The entire PII protection model depends on storage buckets being private. If any PII bucket is public, signed URLs are ineffective and document URLs could be discovered. This must be verified directly in Supabase — it cannot be confirmed from code alone.

2. **Worker PII column exposure**: Identity document numbers, work permit data, and date of birth exist in the database. Whether non-admin roles can see these fields in API responses needs confirmation. If they can, this is a trust boundary violation.
