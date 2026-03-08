# iHouse Core — Handoff Letter לצ'אט הבא

**נכתב:** 2026-03-08 | **Branch:** `checkpoint/supabase-single-write-20260305-1747` | **Last commit:** `4e5ad4b`

---

## הקשר — מה אנחנו בונים

**iHouse Core** — מערכת event-sourced קנונית לניהול הזמנות דירות מ-OTA providers (Booking.com, Expedia).

**עקרונות הברזל:**
- `event_log` הוא append-only — אין מחיקה, אין עדכון
- [booking_state](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_booking_status_contract.py#92-98) הוא projection-only — נכתב אך ורק דרך [apply_envelope](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_dlq_replay_contract.py#128-152)
- [apply_envelope](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_dlq_replay_contract.py#128-152) היא הsingle write authority הבלעדית
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical
- MODIFY → מ却 reject-by-default עד שפייז 50 מושלם

---

## סיכום כל הפייזים שנסגרו (1–49)

| פייז | נושא | תוצאה |
|------|------|-------|
| 1–22 | Infrastructure, schema, event_log, booking_state | בסיס קנוני |
| 23–30 | OTA adapters, BookingCom, Expedia, semantics, registry | Multi-OTA |
| 31–36 | Dead letter queue (DLQ), dlq_replay, dlq_inspector | Fault tolerance |
| 37–41 | DLQ alerting, booking_status, invariants | Observability |
| 42–43 | BOOKING_CANCELED, full validation, E2E live | Lifecycle complete |
| 44 | OTA ordering buffer (table + functions) | Out-of-order handling |
| 45 | Ordering auto-trigger on BOOKING_CREATED | Full loop closed |
| 46 | System health check ([health_check.py](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/adapters/ota/health_check.py)) | OVERALL OK ✅ |
| 47 | OTA payload boundary validation ([payload_validator.py](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/adapters/ota/payload_validator.py)) | Boundary guard |
| 48 | Idempotency key standardization ([idempotency.py](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/adapters/ota/idempotency.py)) | `provider:type:id` |
| 49 | Normalized AmendmentPayload schema ([amendment_extractor.py](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/src/adapters/ota/amendment_extractor.py)) | Schema ready |

**153 tests passing** (2 pre-existing SQLite failures, unrelated).

---

## מה קרה ב-Phase 50 (פתוח — לא נסגר)

Phase 50 = BOOKING_AMENDED DDL + apply_envelope Branch.

### מה כבר בוצע ✅

**Step 1 כבר רץ על Supabase:**
```sql
ALTER TYPE public.event_kind ADD VALUE IF NOT EXISTS 'BOOKING_AMENDED';
```
אומת בbrowser — enum כולל `BOOKING_AMENDED` ✅

### מה עוד נדרש 🔴

**Step 2 — החלפת [apply_envelope](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/tests/test_dlq_replay_contract.py#128-152) בגרסה עם BOOKING_AMENDED branch:**

הקובץ כבר קיים ומוכן:
```
/Users/clawadmin/Antigravity Proj/ihouse-core/artifacts/supabase/migrations/phase50_step2_apply_envelope_amended.sql
```

הוא תוסרב ב-browser בגלל שה-Supabase SQL editor חוסם הדבקת 300 שורות דרך automation.

**פתרון — המשתמש צריך לעשות זאת ידנית:**

1. פתח את הקובץ:
   ```
   /Users/clawadmin/Antigravity Proj/ihouse-core/artifacts/supabase/migrations/phase50_step2_apply_envelope_amended.sql
   ```
2. Copy All (⌘A, ⌘C)
3. עבור ל-Supabase SQL Editor:
   `https://supabase.com/dashboard/project/reykggmlcehswrxjviup/sql/new`
4. הדבק (⌘V) והרץ (Ctrl+Enter)
5. צפה להודעה: `Success. No rows returned.`

### BOOKING_AMENDED Branch Logic (מה כלול ב-SQL)

```
BOOKING_AMENDED:
1. Extract booking_id → BOOKING_ID_REQUIRED if missing
2. SELECT booking_state FOR UPDATE → BOOKING_NOT_FOUND if missing
3. ACTIVE-state guard: if status='canceled' → AMENDMENT_ON_CANCELED_BOOKING ❌
4. Extract new_check_in / new_check_out (both optional)
5. Validate dates if both provided
6. Write STATE_UPSERT to event_log (append-only) ✅
7. UPDATE booking_state — apply new dates only if provided
   - check_in = COALESCE(new_check_in, existing)
   - check_out = COALESCE(new_check_out, existing)
   - status stays 'active'
```

---

## אחרי שה-SQL רץ — מה הצ'אט החדש צריך לעשות

### 1. E2E Live Test (Python) — אמת ש-apply_envelope עובד

```python
# צור booking_id ייחודי
# שלח BOOKING_CREATED → אמת APPLIED
# שלח BOOKING_AMENDED → אמת APPLIED + check_in עודכן
# שלח BOOKING_AMENDED על CANCELED booking → אמת AMENDMENT_ON_CANCELED_BOOKING
```

קובץ test:
```
tests/test_booking_amended_e2e.py
```

### 2. עדכון Python Pipeline — Phase 51

**semantics.py** — כרגע MODIFY → reject. צריך לאפשר reservation_modified → BOOKING_AMENDED:
```python
"reservation_modified" → "BOOKING_AMENDED"  # (במקום MODIFY → reject)
```

**service.py** — BOOKING_AMENDED צריך לפעול כמו BOOKING_CREATED/CANCELED:
- normalize → classify → validate → to_canonical_envelope → apply_envelope

**Pipeline integration tests** — עדכון tests שמכינים MODIFY כdead letter.

### 3. Contract Tests ל-BOOKING_AMENDED

```
tests/test_booking_amended_contract.py
```

---

## מצב נוכחי — BOOKING_AMENDED Prerequisites: 8/10

| Prerequisite | Status |
|-------------|--------|
| DLQ infrastructure | ✅ |
| booking_id stability | ✅ |
| MODIFY classification | ✅ |
| booking_state.status | ✅ |
| Ordering infrastructure | ✅ |
| Idempotency key format | ✅ |
| Normalized AmendmentPayload | ✅ |
| event_kind enum: BOOKING_AMENDED | ✅ (Phase 50 Step 1) |
| apply_envelope BOOKING_AMENDED branch | 🔴 (Phase 50 Step 2 — SQL READY, needs manual paste) |
| ACTIVE-state guard | 🔴 (כלול ב-Step 2) |

---

## קבצים שנוצרו

```
src/adapters/ota/
├── idempotency.py          # Phase 48 — generate_idempotency_key
├── payload_validator.py    # Phase 47 — validate_ota_payload
├── amendment_extractor.py  # Phase 49 — normalize_amendment
├── health_check.py         # Phase 46 — system_health_check
├── ordering_buffer.py      # Phase 44 — buffer/get/mark
├── ordering_trigger.py     # Phase 45 — trigger_ordered_replay
├── schemas.py              # AmendmentFields frozen dataclass
└── ...

artifacts/supabase/migrations/
├── phase50_step1_booking_amended_enum.sql       ✅ done
└── phase50_step2_apply_envelope_amended.sql     🔴 NEEDS MANUAL PASTE
```

---

## ENV Variables שנחוצות

```bash
SUPABASE_URL=https://reykggmlcehswrxjviup.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJleWtnZ21sY2Voc3dyeGp2aXVwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjI5Njc2NiwiZXhwIjoyMDg3ODcyNzY2fQ.L2oIbuAZ_Q-RWtQHoo9kPs9QPrtsary8aVYb1OdzeC8
```

---

## איך להפעיל tests

```bash
cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
source .venv/bin/activate
PYTHONPATH=src python3 -m pytest tests/ --tb=short
# Expected: 153 passed (2 SQLite failures pre-existing, unrelated)
```

---

## הוראות לצ'אט החדש

**צעד ראשון:** בקש מהמשתמש לאשר שהוא הדביק והריץ את [phase50_step2_apply_envelope_amended.sql](file:///Users/clawadmin/Antigravity%20Proj/ihouse-core/artifacts/supabase/migrations/phase50_step2_apply_envelope_amended.sql) ב-Supabase SQL Editor.

**צעד שני:** כתוב E2E test חי (`test_booking_amended_e2e.py`) שמריץ על Supabase live:
- BOOKING_CREATED → APPLIED
- BOOKING_AMENDED → APPLIED + dates updated
- BOOKING_AMENDED on CANCELED → AMENDMENT_ON_CANCELED_BOOKING

**צעד שלישי:** Phase 51 — עדכון semantics.py ו-service.py לניתוב BOOKING_AMENDED.

**המטרה:** לסגור את Phase 50 ול-10/10 prerequisites, ואז Phase 51 = full adapter integration.
