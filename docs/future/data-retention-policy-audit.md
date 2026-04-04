# Data Retention Policy — Audit (Item 10)

**Status:** Audit-only — no enforcement yet  
**Date:** 2026-04-04  
**Classification:** Internal product/legal planning  
**Next step:** Policy decisions needed before enforcement work begins

---

## 1. Data Categories and What Is Currently Stored

### A — Guest Identity / Personal Data

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `guests` | full_name, email, phone, nationality, passport_no, date_of_birth, passport_expiry, document_type, document_photo_url, whatsapp, line_id, telegram, identity_verified_at, extraction_metadata (OCR), issuing_country | **None.** Rows are written and never deleted or anonymized. |
| `guest_profile` | booking_id, guest_name, guest_email, guest_phone, source | **None.** 0 rows live but schema indefinite. |
| `guest_checkin_guests` | full_name, nationality, document_type, document_number, passport_photo_url, phone, email, is_primary | **None.** No expiry or cleanup. |

**Note:** `guests.document_photo_url` and `guest_checkin_guests.passport_photo_url` contain
**links to ID/passport image files** stored in Supabase storage. These are image files
of government-issued documents — the most sensitive personal data category in the system.

---

### B — OCR Extracted Data

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `ocr_results` | storage_path (image link), raw_response (full OCR API output), extracted_fields (parsed PII: name, DOB, passport number, etc.), field_confidences, corrected_fields, provider_used, document_type | **None.** `raw_response` is a full JSONB blob of OCR provider output, which may include unredacted PII from government documents. |

**Risk note:** `raw_response` in `ocr_results` very likely contains the raw machine-readable
zone (MRZ) or full field dump from the document scan. This is high-sensitivity PII stored
as cold JSONB with no expiry, cleanup, or anonymization path.

---

### C — Booking / Stay Data

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `booking_state` | guest_name, guest_count, total_price, check_in/out, status, all checkout/checkin audit fields, guest contact fields (checkout_contact_phone, checkout_contact_email), checkout summary JSONB | **None.** Operational read-write. No archive or delete logic. |
| `event_log` | Full canonical event envelope per booking event (8,714 rows) | **None.** Append-only by design for auditability. |
| `event_log_archive` | Archived event rows (currently empty) | Has a table but no active archival job runs. |
| `booking_financial_facts` | Total price, OTA commission, net_to_property, currency, source_confidence per booking | **None.** Financial record, likely needs long-term keep. |

---

### D — Chat / Messaging

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `guest_chat_messages` | Full message text (sender_type, message, booking_id, assigned_om_id) | **None.** |
| `guest_messages_log` | channel, intent, content_preview (message excerpt), booking_id, guest_id, sent_by | **None.** |
| `notification_log` | recipient (phone/email), subject, body_preview, notification_type | **None.** |
| `notification_delivery_log` | user_id, task_id, channel_id (could be phone/email/LINE ID), trigger_reason | **None.** |

**Risk note:** `notification_log.recipient` stores real phone numbers and email addresses
used to send notifications. `body_preview` stores a partial copy of sent message content.
Neither has any expiry or deletion behaviour.

---

### E — Financial / Deposit Records

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `cash_deposits` | amount, currency, collected_by, forfeiture_reason, returned_at/by | **None.** Financial record. |
| `checkin_deposit_records` | amount, collected_by, collected_at, notes | **None.** |
| `guest_deposit_records` | amount, currency, cash_photo_url, signature_url, collected_by/at, returned_by/at | **None.** `signature_url` links to a file in Supabase storage. |
| `deposit_deductions` | description, amount, category, photo_url | **None.** |
| `electricity_meter_readings` | meter_value, meter_photo_url (storage link), recorded_by, ocr_result_id | **None.** |

---

### F — Photo / File Uploads

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `booking_checkin_photos` | storage_path per check-in photo, room_label, booking_id | **None.** |
| `checkout_photos` | photo_url (storage link), room_label, booking_id | **None.** |
| `cleaning_photos` | storage_path, photo_url, room_label | **None.** |
| `problem_report_photos` | photo_url, caption | **None.** |
| `property_marketing_photos` | photo_url (marketing asset) | **None.** But this is not personal data — correct to keep. |
| `property_reference_photos` | photo_url (reference asset) | **None.** Also not personal data — correct to keep. |

**Risk note:** Supabase Storage bucket is used but no storage lifecycle rules were found.
URLs stored in DB rows point to files that are never cleaned up independently of the DB row.
If a DB row is deleted (which does not happen) the linked storage object would remain.
If a storage object is deleted, the DB row becomes a broken link.

---

### G — Tokens and Auth

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `guest_tokens` | booking_ref, guest_email, token_hash, expires_at, revoked_at | ✅ **Active cleanup**: `token_cleanup` scheduled job deletes rows where `expires_at` < now. |
| `access_tokens` | token_type, entity_id, email, token_hash, expires_at, used_at, revoked_at, metadata | ❌ **No cleanup**. `expires_at` is set but no job deletes expired rows from `access_tokens`. |
| `guest_qr_tokens` | token, portal_url, expires_at | ❌ **No cleanup**. `expires_at` column exists but no deletion job targets this table. |
| `user_sessions` | token_hash, user_agent, ip_address, expires_at, revoked_at, revoked_reason | ❌ **No cleanup**. `expires_at` and `revoked_at` exist. 262 rows live, no expiry job. |
| `acting_sessions` | real_admin_email, acting_as_role, acting_as_context, expires_at, ended_at | ❌ **No cleanup**. Admin impersonation sessions accumulate indefinitely. |

**Note:** `user_sessions` stores `ip_address` — a personal data field under most privacy regulations
(GDPR, PDPA Thailand). No deletion, no anonymization. This is a clear gap.

---

### H — Staff / Worker Data

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `org_members` | User association, role | **None.** |
| `staff_property_assignments` | worker_id, property_id, role | **None.** |
| `staff_onboarding_requests` | Request data for staff onboarding | **None.** |
| `worker_availability` | Staff schedule data | **None.** |

---

### I — Audit / System Events

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `audit_events` | actor_id, action, entity_type, entity_id, payload (JSONB), occurred_at (451 rows) | **None.** Intentional audit log — should be kept. |
| `admin_audit_log` | actor_user_id, action, before_state/after_state JSONB, performed_at | **None.** Admin action audit — should be kept. |
| `ai_audit_log` | endpoint, input_summary, output_summary, entity_type/id | **None.** AI operation log — should be kept but may contain PII in summaries. |

---

### J — Operational Queues and Logs

| Table | What is stored | Deletion behaviour |
|---|---|---|
| `pre_arrival_queue` | booking_id, draft_preview (message content preview), tasks_created | **None.** Operational queue, accumulates indefinitely. |
| `ota_dead_letter` | Raw OTA payload, rejection_code, replayed_at | **None.** |
| `ota_ordering_buffer` | Raw event payload | **None.** |
| `outbound_sync_log` | Sync attempt log | **None.** |
| `scheduled_job_log` | Job results JSONB | **None.** (0 rows — job runner appears not to have been triggered live yet.) |
| `webhook_retry_queue` | payload_json, webhook_url, last_error | **None.** |
| `webhook_dlq` | payload_json, webhook_url, last_error, attempts | **None.** |

---

## 2. Sensitivity Classification

| Category | Sensitivity | Regulatory risk |
|---|---|---|
| `guests.passport_no`, `date_of_birth`, `document_photo_url` | 🔴 **Critical** | GDPR special category, PDPA Thailand sensitive data |
| `guest_checkin_guests.passport_photo_url`, `document_number` | 🔴 **Critical** | Same as above. Government ID scans. |
| `ocr_results.raw_response`, `extracted_fields` | 🔴 **Critical** | Contains MRZ-level PII. Raw OCR dump of passport/ID. |
| `user_sessions.ip_address` | 🟠 **High** | IP address = personal data under GDPR/PDPA |
| `guests.email`, `phone`, `whatsapp`, `line_id` | 🟠 **High** | Direct contact data |
| `guest_tokens.guest_email`, `notification_log.recipient` | 🟠 **High** | Contact data in auth/messaging infrastructure |
| `guest_chat_messages.message` | 🟠 **High** | Potentially sensitive message content |
| `guest_deposit_records.signature_url` | 🟠 **High** | Handwritten signature — biometric-adjacent |
| `booking_state.guest_checkout_contact_phone/email` | 🟡 **Medium** | Guest contact collected at checkout |
| `guest_messages_log.content_preview` | 🟡 **Medium** | Partial message content |
| `ai_audit_log.input_summary`, `output_summary` | 🟡 **Medium** | May summarize PII |
| `cash_deposits`, `electricity_meter_readings`, financial tables | 🟡 **Medium** | Financial records — retain for accounting |
| `audit_events`, `admin_audit_log` | 🟡 **Medium** | Retain for audit, but actor identities are personal data |
| `booking_state` core fields | 🟢 **Low** | Operational booking data |
| `event_log` | 🟢 **Low-med** | Canonical records — must keep |
| `property_marketing_photos` | 🟢 **Low** | Not personal data |

---

## 3. Current Gaps

### Gap 1 — No retention durations defined anywhere

There are **zero** documented retention durations for any data category.
No column, migration comment, or doc states "this table retains data for X months/years".
Retention is effectively indefinite for everything except `guest_tokens`.

### Gap 2 — Only one active deletion job (guest_tokens only)

`job_runner.py` has `token_cleanup` → deletes `guest_tokens` rows where `expires_at < now`.

**No other table has any active cleanup, deletion, or archival job:**
- `access_tokens` — has `expires_at` column, no cleanup job
- `user_sessions` — has `expires_at` and `revoked_at`, no cleanup job
- `acting_sessions` — has `expires_at`/`ended_at`, no cleanup job
- `guest_qr_tokens` — has `expires_at`, no cleanup job

### Gap 3 — Passport/ID images and OCR raw data have no lifecycle at all

The highest-risk PII in the system — document scan images (`document_photo_url`,
`passport_photo_url`) and OCR raw responses (`ocr_results.raw_response`) — has
no expiry, no deletion, and no anonymization. These rows accumulate indefinitely
with no plan.

### Gap 4 — No guest deletion request path exists

There is no API endpoint, admin tool, or documented process for a guest to request
deletion of their personal data. Under GDPR (Article 17) and Thailand PDPA
(Section 33), this is a required capability.

### Gap 5 — Supabase Storage objects are not linked to DB row lifetimes

Multiple tables store URLs pointing to files in Supabase Storage
(`document_photo_url`, `passport_photo_url`, `meter_photo_url`, `signature_url`,
`storage_path` in photo tables). There is no lifecycle policy on the storage bucket
itself, no cleanup job, and no enforced relationship between DB row deletion
and storage object deletion.

### Gap 6 — `user_sessions.ip_address` has no anonymization

IP addresses are personal data under most modern privacy frameworks.
They are stored raw, retained indefinitely, and never hashed or anonymized.

### Gap 7 — `notification_log.recipient` stores raw phone/email with no expiry

The notification log stores the real recipient phone number or email alongside
the message type and status. This row is operational data but contains personal
contact information with no TTL or deletion path.

### Gap 8 — `ocr_results.raw_response` stores the full provider dump

The OCR provider's raw JSON response is stored in full. This likely includes
characters extracted from the MRZ (machine-readable zone) of passports, including
document number, nationality code, date of birth, and checksum digits. There is
no documented reason why the raw provider dump needs to be retained after the
`extracted_fields` JSONB has been validated and confirmed.

### Gap 9 — No formal distinction between operational history and personal data

All tables are treated identically from a retention perspective: write it, keep
it forever. There is no formal classification of "this is operational audit history
(keep)" vs "this is personal data (time-limited)".

### Gap 10 — No archive/anonymization mechanism

There is an `event_log_archive` table but no active archival job uses it.
No anonymization functions exist (`anonymize_guest()` or equivalent).
The system has zero infrastructure for soft-deleting or pseudonymizing records
while preserving audit referential integrity.

### Gap 11 — `pre_arrival_queue.draft_preview` stores message content

The AI-generated pre-arrival message draft preview is stored indefinitely
in the queue table, even after the booking check-in has long passed.

---

## 4. Proposed First-Pass Retention Model

This is a recommendation only. Policy decisions are noted in Section 5.

### Tier 1 — Keep permanently (or for the operating lifetime of the tenancy)

| Data | Reason |
|---|---|
| `event_log` | Canonical audit record — source of truth |
| `audit_events` | Operational audit trail |
| `admin_audit_log` | Governance and compliance record |
| `booking_financial_facts` | Financial record — accounting / tax |
| `cash_deposits`, `deposit_deductions`, `booking_settlement_records` | Financial records |
| `electricity_meter_readings` (values only) | Operational billing record |
| `booking_state` core fields (dates, property, booking_id) | Core operational record |

### Tier 2 — Keep for a defined period, then delete or anonymize

| Data | Suggested window | Rationale |
|---|---|---|
| `guests` row (non-document fields) | 3–5 years after last stay | Reasonable for repeat-guest recognition and operational continuity |
| `guests.document_photo_url` | ~30–90 days after checkout | No operational need after stay closure; regulatory risk increases with age |
| `guests.passport_no`, `date_of_birth`, `extraction_metadata` | 30–90 days after checkout, or anonymize | High-risk PII, not needed after stay closure |
| `guest_checkin_guests` rows | Same as above | Per-guest high-risk PII |
| `ocr_results.raw_response` | Delete after `extracted_fields` confirmed valid | Raw provider dump has no ongoing need |
| `ocr_results` row (metadata only) | 1–2 years | OCR metadata (confidence, provider, timing) useful for QA |
| `guest_chat_messages` | 1–2 years after checkout | Operational value diminishes after stay; contains message content |
| `guest_messages_log` | 1 year | Operational log |
| `notification_log` | 90–180 days | Short-term operational value |
| `notification_delivery_log` | 90 days | Delivery debugging window |
| `user_sessions` | 90 days after expiry/revocation | Session audit trail |
| `acting_sessions` | 90 days after ended_at | Admin impersonation audit |
| `access_tokens` (expired/revoked) | 90 days after expires_at | Security audit window |
| `guest_qr_tokens` (expired) | 30 days after expires_at | No value after expiry |
| `pre_arrival_queue` rows | 30 days after check_in date | Queue entries stale after stay |
| `booking_checkin_photos` | 6 months–1 year after checkout | Property inspection reference; reduce after dispute window closes |
| `checkout_photos` | 6 months after checkout | Same rationale |
| `cleaning_photos` | 90 days | Short-term operational |
| `guest_deposit_records.signature_url` | 1 year after checkout | Dispute window |
| `electricity_meter_readings.meter_photo_url` | 6 months | Photo reference for billing dispute |

### Tier 3 — Keep in anonymized/aggregated form only

| Data | Anonymization model |
|---|---|
| `user_sessions.ip_address` | Hash or null after 90 days |
| `notification_log.recipient` | Mask after 90 days (keep delivery status/type) |
| Financial aggregates derived from personal data | Keep aggregate; drop PK link to guest identity |

### Tier 4 — Requires explicit policy decision (see Section 5)

- All OCR raw data
- Passport/ID image files (who owns them? Do guests have right to delete?)
- `guests.extraction_metadata` (OCR-produced, stored permanently)
- Staff personal data (different to guest data; employment law applies)

---

## 5. Open Decisions Requiring Product / Policy Approval

These cannot be resolved by engineering alone:

| Decision | Options | Impact |
|---|---|---|
| **What jurisdiction governs personal data?** | Thailand PDPA / GDPR / both | Determines minimum retention limits and deletion rights |
| **Do guests have a right-to-be-forgotten request path?** | Yes (required by GDPR/PDPA) / not yet implemented | If yes, needs API endpoint + deletion scope definition |
| **How long are passport scan images legally required?** | Depends on Thailand hotel law (TM.30 reporting) vs. privacy law | May have a mandatory minimum retention window |
| **Does TM.30 reporting require retaining the original passport scan?** | If yes, 30-day minimum; if no, delete after submission | Operators in Thailand submit foreigner registration — legal requirement may dictate minimum retention |
| **Who owns the retention decision for each tenant?** | Platform vs. per-tenant configurable | PDPA assigns the data controller role — is iHouse the processor or controller? |
| **Should `ocr_results.raw_response` be stored at all?** | Delete immediately after extraction / keep for QA / keep permanently | Engineering preference: delete after extraction confirmed. Needs product sign-off. |
| **What is the guest data deletion scope?** | `guests` row only / all linked tables / storage files / all cross-table PII | Defining the exact deletion footprint requires explicit legal scope |
| **Staff data retention period** | Employment law standard (often 7 years) / shorter | Different rules from guest data |
| **`ai_audit_log` — does it log PII?** | Likely yes (input_summary may contain guest name/passport) | Needs audit of what summaries contain |

---

## 6. What to Document Now vs. Implement Later

### Document now (no code needed)

1. **A formal data category map** (this document is a first draft of that)
2. **Sensitivity classifications** per table — so developers know what they are touching
3. **Which tables contain PII that is in-scope for deletion requests**
4. **Owner of the data controller decision** (platform vs. tenant)
5. **The open legal questions** (TM.30, PDPA applicability, employment law)

### Implement later (post-decision)

1. **Token/session cleanup jobs** — extend `token_cleanup` pattern to `access_tokens`, `user_sessions`, `acting_sessions`, `guest_qr_tokens` (low risk, can be done now)
2. **Pre-arrival queue archival** — simple scheduled sweep of old rows
3. **Notification log trim job** — delete rows older than N days
4. **Guest data expiry fields** — add `pii_delete_after` or equivalent column per table
5. **Passport/OCR image lifecycle policy** — delete storage objects after N days post-checkout
6. **`ocr_results.raw_response` selective redaction** — nullify after extraction confirmed
7. **Guest deletion API** — admin endpoint to execute deletion scope for a given guest_id
8. **`user_sessions.ip_address` anonymization job**
9. **Supabase Storage bucket lifecycle rules** — object expiry for sensitive upload paths

---

## 7. Files and Sources Reviewed

### Database tables (via Supabase MCP)
All 100 tables in the `public` schema were inventoried. Column structure was inspected
for 34 tables identified as containing personal, sensitive, or security-relevant data.

### Source files reviewed
- `src/services/guest_token.py` — token TTL and expiry logic
- `src/services/access_token_service.py` — access token creation and expiry
- `src/services/job_runner.py` — scheduled cleanup jobs (only `token_cleanup` active)
- `src/services/pre_arrival_scanner.py` — self-checkin token TTL config
- `src/services/self_checkin_service.py` — 30-day token TTL for checkin
- `src/services/scheduler.py` — job scheduling
- `src/api/guest_checkout_router.py` — checkout data stored in `booking_state`
- `src/ocr/` directory — OCR pipeline (confirms `raw_response` is stored)

### Documentation reviewed
- `docs/future/contextual-help-layer.md`
- `docs/future/guest-pre-arrival-form.md`
- `docs/archive/improvements/future-improvements.md`
- `docs/phases/phase-1066-guest-checkout-resolution-fix.md`
- `docs/phases/phase-1067-checkout-wizard-completion-fix.md`

---

## Summary

**The honest current state:**

The system stores a significant amount of guest PII — including passport scans, extracted
document fields, government ID numbers, and contact data — with effectively **zero retention
limits, zero deletion automation, and zero guest deletion request capability**.

The only active cleanup is `guest_tokens` (one scheduled job, not confirmed to be running
in production).

The highest-severity gaps are:
1. Passport scan images and OCR raw_response — no expiry
2. `user_sessions.ip_address` — no anonymization
3. No right-to-deletion path for guests
4. No documented or enforced retention durations for any category

These gaps are not bugs. The system was built correctly for its operational purpose.
But as real guest data accumulates on the platform — especially scan images and OCR
outputs — the risk exposure increases without a retention policy in place.

**Recommended next action:** Policy decisions (Section 5) should be made before enforcement
work begins. Several can be answered internally; at least one (TM.30 passport scan duration)
may require legal input specific to Thailand hotel law.
