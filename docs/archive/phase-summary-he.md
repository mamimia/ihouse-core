# iHouse Core — סיכום כל הפאזות (בעברית)

---

**פאז 1** — הונחה בסיס טבלת אירועים בלתי ניתן לשינוי. כל מצב מערכת נגזר מאירועים, לא מוכתב ישירות.

**פאז 2** — הוכנס מנגנון הקרנה (projection) ושחזור דטרמיניסטי — ניתן לבנות מחדש את כל המצב מהיסטוריית האירועים.

**פאז 3** — אכיפת אידמפוטנסיה ברמת בסיס הנתונים. אירוע שנשלח פעמיים לא ייצור שורה כפולה.

**פאז 4** — נוסף אימות טביעת אצבע (fingerprint) לשחזור; טבלת האירועים הוכרזה בלתי ניתנת לשינוי בזמן rebuild.

**פאז 5** — נמנעה ניפוח גרסה (version inflation) בעת שחזור חוזר; תאימות קדימה ואחורה נעולה.

**פאז 6** — הוכנס Outbox pattern עם תמיכה במספר workers, ומנגנוני claim + lease למניעת ביצוע כפול.

**פאז 7** — הקשחת תשתית: WAL, foreign_keys, busy_timeout — שחזור דטרמיניסטי אומת פעמיים.

**פאז 8** — FastAPI הוכנס; נחשפה ממשק POST /events לקליטה וממשק query לשאילתות.

**פאז 9** — הקשחת HTTP: אכיפת API key, לוגים מובנים, אין דליפת stack traces.

**פאז 10** — הקשחת Skill Runner: timeout, בידוד subprocess, kind_registry חיצוני.

**פאז 11** — ניתוב Kind→Skill הועבר ל-Core; mapping דיפולטי של Python הוסר.

**פאז 12** — ביקורת domain הושלמה; תכנית מיגרציה פנימית הוכנה.

**פאז 13A** — event_log כ-append-only פורמל; transakció אטומי של envelope הוגדר.

**פאז 13B** — commit רק כאשר apply_status == APPLIED; booking_state.last_envelope_id הוכנס.

**פאז 13C** — Supabase הוכנס כ-persistence: event_log ו-booking_state נוצרו ב-Cloud.

**פאז 14** — נקבע נתיב commit דטרמיניסטי יחיד; replay לא מבצע commit; כתיבות מסתורות אל state הוסרו.

**פאז 15** — FastAPI נקבע כ-entrypoint הביצוע היחיד; ביצוע מקבילי הוסר.

**פאז 16** — מיגרציית domain קנונית: נעילת schema, יישור core דטרמיניסטי, שער אידמפוטנסיה קשיח (grade פיננסי).

**פאז 17A** — run_api.sh קנוני; scripts לסביבת dev; CI; מדיניות secret-based API key.

**פאז 17B** — apply_envelope אומת כסמכות כתיבה אטומית יחידה; replay ללא מוטציה אומת E2E.

**פאז 17C** — overlap gate הוכנס (טווח half-open [check_in, check_out)); business dedup key לפי tenant+source+reservation+property.

**פאז 18** — ביטול הזמנה (BOOKING_CANCELED) הוכנס; status='canceled' מסיר את ה-booking מ-overlap checks.

**פאז 19** — gate אימות event_version ב-DB; קודי דחייה דטרמיניסטיים נעולו (UNKNOWN_EVENT_KIND, ALREADY_APPLIED וכו').

**פאז 20** — apply_envelope אומת כ-write gate יחיד; replay כפול אומת כ-zero-mutation E2E.

**פאז 21** — גבול קליטה חיצוני הוגדר: מערכות חיצוניות לא כותבות ישירות ל-event_log. נתמכות: BOOKING_CREATED, BOOKING_CANCELED.

**פאז 22** — adapter layer לערוצי OTA חיצוניים הוכנס; pipeline נירמול → validation → apply_envelope.

**פאז 23** — semantics.py: סיווג סמנטי דטרמיניסטי לאירועי OTA לפני יצירת envelope קנוני.

**פאז 24** — MODIFY הוכנס כסוג סמנטי מיניים לשינויי הזמנה; אירועי עדכון לא מסווגים אוטומטית כ-CREATE/CANCEL.

**פאז 25** — כלל נעול: MODIFY → deterministic reject by default. אין שינוי קנוני ממידע OTA עמום.

**פאז 26** — בדיקת שאילתות OTA לחמישה ספקים (Booking.com, Expedia, Airbnb, Agoda, Trip.com): אין subtype דטרמיניסטי פאיילד-only לשינוי. הכלל נעול.

**פאז 27** — ארכיטקטורת adapter מרובי-OTA הוכנסה; pipeline.py משותף; Expedia scaffold נוסף.

**פאז 28** — משטח קליטה חיצוני קנוני: BOOKING_SYNC_INGEST הוחלף ב-BOOKING_CREATED/BOOKING_CANCELED מפורשים.

**פאז 29** — harness שחזור OTA נוסף; כיסוי replay ל-CREATED/CANCELED/MODIFY/duplicate/invalid.

**פאז 30** — handoff runtime OTA נעול: ingest_provider_event → process_ota_event → apply_envelope.

**פאז 31** — docs סונכרנו ל-runtime contract; backlog future-improvements.md הוכנס.

**פאז 32** — test verification loop של OTA ingest contract נסגר; כל נתיב runtime מכוסה בטסטים.

**פאז 33** — discovery: OTA transport idempotency vs. canonical business idempotency הופרדו; פער routing זוהה.

**פאז 34** — הוכחה: BOOKING_CREATED ניתב ל-noop skill; BOOKING_CANCELED לא ניותב. פער alignment ב-payload מוכח.

**פאז 35** — יישום: booking_created skill + booking_canceled skill; registry עודכן; BOOKING_CREATED/CANCELED מגיעים ל-apply_envelope. E2E ✅.

**פאז 36** — canonicalization של booking_id: {source}_{reservation_ref} — כלל נעול; dedup כפול ב-apply_envelope אומת.

**פאז 37** — discovery: אירוע CANCELED לפני CREATED → BOOKING_NOT_FOUND דטרמיניסטי. אין data loss שקט. פער open.

**פאז 38** — Dead Letter Queue: ota_dead_letter table; אירועים שנכשלו נשמרים במקום לאבד אותם. E2E ✅.

**פאז 39** — DLQ Controlled Replay: replay_dlq_row() — ידני, אידמפוטנטי, תמיד דרך apply_envelope.

**פאז 40** — DLQ Observability: view ota_dlq_summary; פונקציות inspection read-only.

**פאז 41** — DLQ Alerting: threshold configurable; WARNING לוג כאשר pending ≥ threshold.

**פאז 42** — discovery: תנאים מוקדמים ל-BOOKING_AMENDED — 3/10 מתקיימים, 7 פערים זוהו.

**פאז 43** — booking_state.status אומת כ-existing (Phase 42 טעה); get_booking_status() read-only. 4/10 ✅.

**פאז 44** — ordering buffer: ota_ordering_buffer table; אירועים שנחסמו בגלל סדר שגוי נשמרים לפי booking_id.

**פאז 45** — auto-trigger לאחר BOOKING_CREATED: ה-buffer מנוגב אוטומטית ואירועים ממתינים מנוגנים מחדש.

**פאז 46** — System Health Check: 5 קומפוננטות; never raises; OVERALL OK E2E ✅.

**פאז 47** — OTA Payload Boundary Validation: PayloadValidationResult; 6 kllalim; כל error codes מוחזרים ביחד.

**פאז 48** — Idempotency Key Standardization: format provider:event_type:event_id; collision-safe cross-provider.

**פאז 49** — AmendmentFields dataclass; amendment_extractor.py ל-Booking.com ו-Expedia. 7/10 ✅.

**פאז 50** — BOOKING_AMENDED DDL + apply_envelope branch: ALTER TYPE + migration; lifecycle guard ACTIVE-state; COALESCE לתאריכים. E2E ✅ על Supabase חי. 10/10 ✅.

**פאז 51** — Python pipeline integration: semantics.py + service.py ניתוב BOOKING_AMENDED דרך pipeline המלא.

**פאז 52** — GitHub Actions CI Hardening: CI pipeline מאובטח; build + test אוטומטי על כל push.

**פאז 53** — Expedia Adapter: normalize() + extract_financial_facts() מלאים; מכסה CREATED/CANCELED.

**פאז 54** — Airbnb Adapter: normalize() + extract_financial_facts(); payout_amount + booking_subtotal.

**פאז 55** — Agoda Adapter: normalize() + extract_financial_facts(); selling_rate + net_rate.

**פאז 56** — Trip.com Adapter: normalize() + extract_financial_facts(); order_amount + channel_fee.

**פאז 57** — Webhook Signature Verification: HMAC-SHA256 לכל 5 ספקים; production rejects fakes.

**פאז 58** — HTTP Ingestion Layer: POST /webhooks/{provider} FastAPI endpoint; 200/400/403/500 locked.

**פאז 59** — FastAPI App Entrypoint: src/main.py; GET /health; lifespan; dev runner.

**פאז 60** — Request Logging Middleware: UUID request_id; → ← log lines; X-Request-ID header.

**פאז 61** — JWT Auth: tenant_id מ-JWT sub; auth.py; Depends(jwt_auth); dev bypass.

**פאז 62** — Per-Tenant Rate Limiting: sliding window; 60/min/tenant; 429 + Retry-After.

**פאז 63** — OpenAPI Docs: /docs ו-/redoc בדרגת production; BearerAuth scheme; response schemas.

**פאז 64** — Enhanced Health Check: Supabase ping + DLQ count; ok/degraded/unhealthy (503).

**פאז 65** — Financial Data Foundation: BookingFinancialFacts frozen dataclass; 5 ספקים מחלצים שדות פיננסיים; ללא כתיבה ל-DB. Invariant: booking_state לעולם לא יכיל נתוני כסף.

**פאז 66** — booking_financial_facts Supabase Projection: טבלה append-only + RLS; financial_writer.py כותב לאחר BOOKING_CREATED APPLIED. E2E ✅.

**פאז 67** — Financial Facts Query API: GET /financial/{booking_id}; JWT auth; tenant isolation; 404 אם לא נמצא; קורא רק מ-booking_financial_facts.

---

**סה"כ:** 396 טסטים עוברים, 2 מדולגים.
