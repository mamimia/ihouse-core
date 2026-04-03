# Evidence File: Oren — Trust & Privacy Reviewer

**Paired memo:** `13_oren_trust_privacy_reviewer.md`
**Evidence status:** Strong security evidence from token implementation, PII controls, and audit mechanisms. Storage bucket RLS remains unverifiable from code alone — requires runtime check.

---

## Claim 1: Guest token uses HMAC-SHA256 with constant-time comparison and hash-only storage

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/services/guest_token.py`, line ~166: `hmac.compare_digest()` used for token verification — constant-time comparison prevents timing attacks
- Same file: Token format is `{booking_ref}:{guest_email}:{exp_timestamp}` signed with HMAC-SHA256 and base64url-encoded
- Same file: Only the SHA-256 hash of the token is stored in the database, not the token itself
- Same file: Minimum secret length enforced at 32 bytes (RFC 7518 §3.2 compliance)
- Same file: 7-day default TTL with expiry validation on every request

**What was observed:** The guest token implementation follows security best practices: HMAC-SHA256 for signing, constant-time comparison for verification (prevents timing side-channels), hash-only storage in DB (token compromise from DB dump is not possible), booking-scoped (one token = one booking), time-limited (7-day TTL), revocable via `is_guest_token_revoked()` DB check.

**Confidence:** HIGH

**Uncertainty:** None. The implementation is textbook correct for transient portal access tokens.

---

## Claim 2: Guest portal returns only non-sensitive fields — no financial data exposed

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/guest_portal_router.py` — Response fields: booking_ref, property_name, dates, guest_name, wifi credentials, access_code, house_rules, emergency_contact, status, appliance instructions, nearby places. NO deposit amounts. NO financial data. NO worker information. NO owner information.

**What was observed:** The guest portal endpoint is carefully scoped. It returns only what a guest needs: property information, access details, and stay logistics. Financial data (deposits, payments, commissions) is completely absent from the guest-facing API.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 3: PII document access is admin-only with 5-minute signed URLs and audit logging

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/pii_document_router.py` — Role guard: `role == "admin"` required for all PII document endpoints
- Same file: `_SIGNED_URL_EXPIRY_SECONDS = 300` (5 minutes)
- Same file: Every access logged with: actor_id, IP address, document types requested, guest_ids accessed
- File: `src/api/guest_portal_router.py` — Passport photos in API responses are redacted to `***`. Boolean flags `passport_photo_captured` and `signature_recorded` used instead of actual data.

**What was observed:** Three layers of PII protection: (1) Only admin role can access PII document endpoints. (2) Signed URLs expire after 5 minutes — no permanent links. (3) Every access is audit-logged with full context. Additionally, the API layer itself redacts passport photo URLs, replacing them with boolean flags.

**Confidence:** HIGH

**Uncertainty:** None for the application-level controls. Whether these controls are also enforced at the storage bucket level (RLS policies) is a separate claim (see Claim 6).

---

## Claim 4: Act-as system has dual attribution and is architecturally disabled in production

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/act_as_router.py`, line ~128: Production gate — Act-as is disabled in production environment
- Same file: JWT payload preserves `real_admin_id` alongside `effective_user_id`
- Same file: `acting_sessions` table records: real_admin_user_id, acting_as_role, acting_as_user_id, expires_at, ended_at
- Same file: Explicit `ACT_AS_STARTED` and `ACT_AS_ENDED` audit events
- Same file: 4-hour maximum TTL on sessions

**What was observed:** The Act-as system is architecturally robust: dual attribution ensures every action is traceable to the real admin, time-limited sessions prevent forgotten impersonations, and explicit start/end audit events create a complete timeline. The production gate means this system is currently development/staging only.

**Confidence:** HIGH

**Uncertainty:** Whether the production gate is a temporary measure (will be enabled later with additional safeguards) or a permanent decision.

---

## Claim 5: Invite token security — SHA-256 hash storage, single-use, INVITABLE_ROLES guard

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/invite_router.py` — Token stored as SHA-256 hash. `used_at` field enforces single-use. `revoked_at` field enables revocation. INVITABLE_ROLES constant prevents admin creation via invite path.
- Two-stage validation: (1) cryptographic verification of token, (2) database state check (not used, not revoked, not expired)

**What was observed:** Invite tokens follow the same security pattern as guest tokens: hash-only storage, time-limited, revocable. The INVITABLE_ROLES guard is a structural privilege escalation prevention — even if an attacker compromises an invite token, they cannot create an admin account.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 6: Storage bucket RLS policies are NOT visible in examined migrations — cannot confirm private configuration

**Status:** NOT PROVEN — REQUIRES RUNTIME VERIFICATION

**Evidence basis:**
- File: `artifacts/supabase/schema.sql` — Migration files define table structures and row-level security policies for tables. Storage bucket configuration (public vs. private) for passport-photos, signatures, staff-documents, guest-documents buckets was NOT found in the examined SQL files.
- Supabase storage bucket visibility is typically configured via the Supabase dashboard or storage API, not always in migration files.

**What was observed:** The application-level PII protection (signed URLs, admin-only access, audit logging) is proven. But if any PII storage bucket is configured as public in Supabase, the signed URL mechanism provides no additional security — URLs follow predictable patterns (`{tenant_id}/{task_id}/{room_label}_{uuid}.{ext}`) and could be enumerated.

**Confidence:** CANNOT DETERMINE from code alone

**Uncertainty:** HIGH. This is the highest-priority verification item for trust and privacy. Requires direct inspection of Supabase storage configuration (dashboard or API).

---

## Claim 7: Test token shortcut accepts `test-` prefix without HMAC verification

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/services/guest_token.py`, line ~247: `resolve_guest_token_context()` checks if token starts with `test-` and, if so, bypasses HMAC verification

**What was observed:** Tokens prefixed with `test-` skip the entire HMAC verification chain. This is appropriate for CI/test environments but must be gated by an environment variable (e.g., IHOUSE_DEV_MODE or TEST_MODE). Whether this shortcut is active in production was not confirmed from code alone.

**Confidence:** HIGH that the shortcut exists. MEDIUM confidence on production gating — requires runtime environment check.

**Uncertainty:** Whether the test shortcut is disabled in production. If it's active, any request with a `test-` prefixed token would bypass guest authentication entirely.

---

## Claim 8: No data retention policy — PII retained indefinitely

**Status:** DIRECTLY PROVEN (absence)

**Evidence basis:**
- No scheduled cleanup, purge, or retention logic was found in any examined file for: guest passport photos, expired tokens, completed booking data, onboarding metadata, identity documents.
- File: `src/services/guest_token.py` — Expired tokens are rejected on validation but never deleted from the database
- File: `src/api/pii_document_router.py` — No reference to document expiry or scheduled deletion

**What was observed:** The system accumulates PII over time with no visible mechanism for removal. Passport photos, identity documents, and personal data from completed bookings remain in storage indefinitely. This may have regulatory implications depending on jurisdiction (PDPA in Thailand, GDPR if EU guests are served).

**Confidence:** HIGH that no retention policy exists in examined code

**Uncertainty:** A retention policy could exist in infrastructure (Supabase lifecycle rules, cron jobs) not visible in the application codebase.

---

## Claim 9: Dev mode requires explicit IHOUSE_DEV_MODE="true" environment variable

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/auth.py` — Checks for `os.environ.get("IHOUSE_DEV_MODE") == "true"`. Not a default. Must be explicitly set. When active, bypasses JWT verification entirely with a hardcoded dev tenant context.

**What was observed:** Dev mode is an explicit opt-in, not a default or auto-detected setting. It bypasses authentication entirely, which is appropriate for local development. The environment variable approach is standard practice.

**Confidence:** HIGH

**Uncertainty:** None regarding the gating mechanism. The concern is operational: ensuring this variable is never set in production environments.
