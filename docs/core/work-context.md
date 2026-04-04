## Current Active Phase

Phase 1059 — Operational Resilience Hardening (ACTIVE 2026-04-04). Phases 841–1058 closed.

## Last Closed Phase

Phase 1058 — Operational Audit Closure: PKA-Bridge Group B + Group C + Backend Authorization Hardening (CLOSED 2026-04-04).

## Current Objective

✅ **Phase 1031 — Assignment Priority Normalization & Canonical Lane Protection — CLOSED** (2026-03-31)

Root cause: `POST /staff/assignments` always used `DEFAULT 1` for priority — every worker in every property got priority=1, making `ORDER BY priority ASC LIMIT 1` non-deterministic.

Fixes: early-checkout healing priority walk, backfill Primary-existence guard, `OWNERLESS_TASK_CREATED` error token. DB triggers block (property, lane, priority) collisions and block no-lane INSERT. API returns `400 NO_OPERATIONAL_LANE` for roleless workers. 11 invalid rows removed (managers, ghost user, owner). Lane model locked: CLEANING / MAINTENANCE / CHECKIN_CHECKOUT only — no UNKNOWN lane. DB proofs: zero collisions, zero ownerless tasks, all 14 assignments in real operational lanes. 161 tests pass. Commits `b5f5e8f` → `7dcb4da` → `89d3f45`.

✅ **Phase 1032 — Live Staging Proof + Baton-Transfer Closure — CLOSED** (2026-03-31)

Closed all deferred live-flow proofs and resolved two source-of-truth gaps found during the proof pass.

**Code fixes:**
- `fb5b3ea`: Trigger race fix — `fn_guard_assignment_priority_uniqueness` exempted from UPDATE operations; atomic Backup→Primary promotion now works.
- `6eedbda`: `POST /staff/assignments` 500 fix — PostgREST upsert was sending NULL `priority`, violating `chk_priority_positive`. Now always included in payload.
- `a414a8c`: `GET /permissions/me` endpoint added — returns caller's own `tenant_permissions` row including `comm_preference._promotion_notice`. Was silently 404, causing worker banner to never render.

**Proven on staging:**
- Baton-transfer E2E: KPG-500 CLEANING lane — Joey demoted (Backup), แพรวา promoted (Primary). `staff_property_assignments` confirmed in DB.
- Promotion notice JSONB: `_promotion_notice` present, `acknowledged: false` in Supabase.
- `GET /permissions/me`: HTTP 200, returns notice correctly.
- Worker promotion banner: ⭐ "You are now the Primary Worker" rendered in `/worker` UI for `praewatanphan@gmail.com` (screenshot confirmed).
- `POST /staff/assignments` existing-row: HTTP 201 (was 500).

**Final staging state (real, caused by proof pass):**
- KPG-500 CLEANING: แพรวา = Primary (priority=1), Joey = Backup (priority=2).

**Open (not blocking closure):**
- Promotion notice acknowledgement PATCH (worker dismiss banner → `acknowledged: true`) not built.
- Legacy KPG-500 task distribution (7 Backup / 2 Primary) is a pre-guard artifact, not a current write-path failure.

Commits: `fb5b3ea` → `6eedbda` → `a414a8c`. Branch: `checkpoint/supabase-single-write-20260305-1747`.

✅ **Phase 1033 — Canonical Task Timing Hardening — CLOSED** (2026-04-01)

Implementation landed across multiple workstreams. Documentation closure was incomplete at first — now completed via this pass.

**BUILT + STAGING-PROVEN:**
- `src/tasks/timing.py` — `compute_task_timing()`: hour-level UTC timing gates. `ack_allowed_at` = due−24h, `start_allowed_at` = due−2h. CRITICAL bypass. MAINTENANCE/GENERAL no start gate.
- `src/api/worker_router.py` — `/worker/tasks` enriched with 4 timing fields; `/acknowledge` + `/start` enforce gates; `ACKNOWLEDGE_TOO_EARLY` / `START_TOO_EARLY` structured errors returned.
- `src/tasks/task_writer.py` — `due_time` written at task creation (kind-default map); preserved on amendment reschedule.
- `WorkerTaskCard.tsx` — `AckButton` + `StartButton` server-driven; "Opens in Xh Ym" flash; `computeOpensIn()` replaces local math.
- `cleaner/page.tsx`, `checkout/page.tsx`, `checkin/page.tsx` — 4 timing fields extended and threaded through.
- Staging proofs: check-in timing ✅ check-out timing ✅

**BUILT, SURFACED — not screenshot-proven:**
- OM shell + Hub (cockpit-first), Alerts, Stream, Team, Bookings, Calendar pages (`/manager/...`).
- `task_takeover_router.py` expanded: `/manager/alerts`, `/manager/team-overview`, `/tasks/{id}/notes`.
- Act As / Preview As: person-specific (`name` + `user_id`); banners show "Role · [Person Name]".
- Staff onboarding: manager validation, role lock, approval history, Work Permit rule, combined checkin+checkout tile.
- Auth fixes: `/act-as` + `/preview` in `PUBLIC_PREFIXES`; `apiFetch` logout on 401 only.
- Maintenance timing gate: built but staging proof 🔲 (no live task available during session).

**OPEN (carried into Phase 1034+):**
- `ManagerTaskCard.tsx` intervention component — not built.
- Dedicated `POST /tasks/{id}/takeover-start` bypass route — not built.
- Reassign Tier 1/Tier 2 UI panel — not built.
- Note inline input UI — not built.
- Promotion notice acknowledgement PATCH — deferred from Phase 1032.

**Product decision locked:** Worker layer = Acknowledge/Start/Complete. Manager layer = Monitor/Takeover/Reassign/Note. `ManagerTaskCard` is drill-down/intervention only — not replacing Hub/Stream/Alerts/Team.
Commits: `305a083` → `e79adb2` → `cd8a04a` → `1480f03`. Branch: `checkpoint/supabase-single-write-20260305-1747`.

✅ **Phase 1034 — OM-1: Manager Task Intervention Model — CLOSED** (2026-04-01)

- `POST /tasks/{id}/takeover-start`: timing-gate bypass, atomic PENDING→IN_PROGRESS, `task_actions` audit.
- `POST /tasks/{id}/reassign`: property-scoped workers, `handoff_note` → `tasks.notes[source=handoff]`, `task_actions` audit.
- `POST /tasks/{id}/notes`: source-typed note append (manager_note | handoff).
- `ManagerTaskCard.tsx` + `ManagerTaskDrawer`: read-only timing strip, Takeover/Reassign/Note. No worker execution buttons.
- `ReassignPanel`: kind-compatible named workers, collapsed manual fallback.
- Bug fixes: `jwt_auth`/`jwt_identity` mixed use (was causing 500 on note save); `task_id`/`id` field normalization.
- Backend-proven in DB: property name resolution (`KPG-500 → "Emuna Villa"`), handoff note, worker endpoint.
- End-to-end UI proof: pending (reassign execution, worker handoff card visibility).

✅ **Phase 1035 — OM-1: Stream Redesign — CLOSED** (2026-04-01, backend proven)

- Stream migrated from `audit_events` (history) to live `tasks` + `bookings` tables.
- Tasks: `GET /manager/tasks`, urgency sort (overdue→today→upcoming→future).
- Bookings: `GET /manager/stream/bookings`, yesterday→+7d, confirmed only.
- Sessions tab: removed from OM Stream.
- Property name resolution bug fixed: was joining `properties.id` (bigint), now `properties.property_id` (text code).
- `ReassignPanel` empty state fixed: human-readable, no raw `.` string.
- DB SQL proofs pass. UI visual proof pending.

✅ **Phase 1036 — OM-1: Stream Hardening — CLOSED** (2026-04-01)

- `POST /tasks/adhoc`: ad-hoc task creation for managers. CHECKIN_PREP/CHECKOUT_VERIFY blocked. 409 duplicate guardrail + `?force=true` override. Lane-aware auto-assign. Audit log.
- Stream: canonical ordering (CHECKOUT→CLEAN→CHECKIN same property+day). `KindSequenceBadge`. Add Task in header. Conflict guardrail UI. Scope-aware booking empty state.
- Build clean. Deployed `054c83a`.

✅ **Phase 1037 — Staff Onboarding Access Hardening — CLOSED** (2026-04-02)

Four sub-commits: 1037a=manual create with real auth UUID; 1037b=SMTP bypass via generate_link; 1037c=true hard delete from auth.users; 1037d=bulletproof two-pass auth (7 exist-signal variants, never raw 500). Orphaned `esweb3@gmail.com` cleaned. Commits: `0a8fc27` → `0300bdd` → `92eba9d` → `d006702`.

✅ **Phase 1038 — Supervisory Role Assignment Hardening — CLOSED** (2026-04-02)

- Root cause fixed: `POST /staff/assignments` was applying worker-lane validation to supervisory roles (manager/admin/owner) — now bypasses with `priority=100`.
- `GET /staff/property-lane/{id}` returns `supervisors[]` alongside worker lanes.
- Frontend: property rows branch on role. Supervisory → supervisor name chips (👤 Name). Worker rows unchanged (Primary/Backup).
- Real backend errors surfaced in UI: `apiFetch` reads body before throw; `handleSave` catch uses `e.message`.
- Orphaned `0330` tenant_permissions + staff_assignments rows cleaned.
- Commit: `b4150cf`.

✅ **Phase 1038b — Mobile Stream Responsive Hardening + Multi-Supervisor Chips — CLOSED** (2026-04-02)

- `activeTab` persisted to `sessionStorage` — survives orientation change, no more Bookings→Tasks reset.
- `BookingRow` isMobile prop: mobile portrait renders vertical 3-row card layout; desktop unchanged.
- Supervisor chip strip: shows ALL supervisors for property. First 2 as chips, `+N` overflow. Current user's chip = purple. Others = amber. `No supervisor yet` only when truly empty.
- Commit: `eae8705`. Build clean. Deployed to Vercel staging.

🔵 **Phase 1039 — OM Role & Assignment Inline Help — ACTIVE** (2026-04-02)

Add human-readable inline explanatory text and help UI on the Role & Assignment screen for supervisory roles, especially Operational Manager.

Operator must be able to understand directly from the UI:
- Operational Manager is a supervisory scope role (not a worker lane)
- One OM can supervise multiple villas
- Multiple OMs can be assigned to the same villa
- Primary/Backup does not apply to OM
- The names shown on property rows are the OMs already assigned to that villa
- Assigning an OM gives managerial scope, not worker-lane task ownership

**Scope:** UI only. No backend changes required. Inline help block, info tooltip, or styled info card on the Role & Assignment tab of the staff detail page (`[userId]/page.tsx`). Must be visible when `role === 'manager'` and when supervisory property rows are rendered.


- System reset to zero-state (Phase 830)
- Auth E2E proven: dev-login → JWT → API access
- Task lifecycle policy: no production delete, CANCELLED + canceled_reason
- Cleaner role added across auth + routing stack (Phase 831)
- Worker task start endpoint + guest_name enrichment (Phase 832)
- First property + manual booking E2E proven (Phase 833)
- iCal intake E2E proven incl. dedup + overlap blocking (Phase 834)
- iCal task cascade fix — same operational behavior as manual (Phase 835)
- Guest access model investigated, token/QR proven (Phase 836 — Readiness-Closed)
- Guest portal data binding fixed, auto-issuance added, real QR image (Phase 837)
- Mobile-accessible language control on all critical surfaces (Phase 838)
- RTL guard fix + login/auth + worker surface fully localized EN/TH/HE (Phase 839)
- Property Settings Surface + OTA Management (Phase 840)
- Worker Role Scoping JSONB Array Evolution (Phase 843)
- Worker App UI Overhaul & Brand Alignment (Phase 844)
- Worker App Functionality Polish & Date Formatting (Phase 845)

✅ **Staging & Auth Readiness — COMPLETE** (Phases 855A–855E)
- Staging frontend (Vercel) + backend (Railway) + Supabase connectivity proven (855A)
- Password auth E2E proven on staging (855A)
- Google OAuth setup + redirect flow proven (855B)
- Google OAuth full E2E sign-in proven (855C)
- Auth identity model designed — deferred as over-engineered (855D)
- Existing onboarding pipelines audited, 6 Google OAuth conflicts identified (855E)
- Auto-provision vulnerability identified in `/auth/register/profile` (855E)

### Next Phase Sequence
```
──── Checkpoint: One Property, End-to-End ────                 ← REACHED
──── Checkpoint: Guest Access E2E Proven ────                  ← REACHED
──── Checkpoint: Language Control Accessible ────              ← REACHED
──── Wave 2: Mobile/Worker Surface & Admin Preview As ────     ← CLOSED
──── Staging & Auth Readiness ────                             ← CLOSED
Phase 843 — Worker Role Scoping JSONB Array Evolution          ← CLOSED
Phase 844 — Worker App UI Overhaul & Brand Alignment           ← CLOSED
Phase 845 — Worker App Functionality Polish & Date Formatting  ← CLOSED
Phase 846–854 — Various verification + features               ← CLOSED
Phase 855 — LINE Integration E2E Proof                        ← CLOSED
Phase 855A — Staging Runtime Verification                     ← CLOSED
Phase 855B — Google OAuth Staging Setup                       ← CLOSED
Phase 855C — Google OAuth E2E Proof                           ← CLOSED
Phase 855D — Auth Identity Model Design (deferred)            ← CLOSED
Phase 855E — Onboarding Pipeline Audit                        ← CLOSED
Phase 857 — Onboarding Remediation Wave (7 fixes)             ← CLOSED
Phase 858 — Product Language Correction + Google Path          ← CLOSED
Phase 859 — Admin Intake + Login UX + Draft Expiration         ← CLOSED
Phase 860 — Landing Page UI Fixes & Mobile Scrolling          ← CLOSED
Phase 861 — Identity Merge & Auth Linking Closure              ← CLOSED
Phase 862 — Staff Onboarding Data Mapping + mailto UX         ← CLOSED
Phase 863 — Media Storage Remediation + Canonical Retention   ← CLOSED
Phase 864 — Next Phase                                        ← CLOSED (merged into later phases)
Phase 979 — Guest Dossier & Worker Check-in Hardening         ← CLOSED
Phase 981 — Test Suite Full Green (7,975 passed)              ← CLOSED
Phase 1003 — Canonical Block Classification & Bookings UX     ← CLOSED
Phase 1021 — Owner Bridge Flow                                ← CLOSED
Phase 1022 — Operational Manager Takeover Gate                ← CLOSED
Phase 1028 — Primary/Backup Model Decision & Baton-Transfer Architecture  ← CLOSED
Phase 1029 — Default Worker Task Filter COMPLETED Exclusion Hardened      ← CLOSED
Phase 1030 — Task Lifecycle & Assignment Hardening                         ← CLOSED
Phase 1031 — Assignment Priority Normalization & Canonical Lane Protection   ← CLOSED
Phase 1032 — Live Staging Proof + Baton-Transfer Closure                    ← CLOSED
Phase 1033 — Canonical Task Timing Hardening (+ OM Surface, Act As)         ← CLOSED
Phase 1034 — OM-1: Manager Task Intervention Model                          ← CLOSED
Phase 1035 — OM-1: Operational Manager Stream Redesign                       ← CLOSED (backend proven)
Phase 1036 — OM-1: Stream Hardening (Canonical Ordering, Add Task, Scope)    ← CLOSED
Phase 1037 — Staff Onboarding Access Hardening                               ← CLOSED
Phase 1038 — Supervisory Role Assignment Hardening                           ← CLOSED
Phase 1038b — Mobile Stream Responsive Hardening + Multi-Supervisor Chips    ← CLOSED
Phase 1039 — OM Role & Assignment Inline Help (Supervisory Model)            ← CLOSED
Phase 1040 — P0: System Closure, Regression, Docs Alignment                   ← CLOSED
Phase 1041–1046 — OM Hub Depth, Morning Briefing, Task Board, Checkout Audit  ← CLOSED
Phase 1047A — Guest Portal Foundation Repair                                   ← CLOSED
Phase 1047A-name — Guest Portal No-Leak + Schema Alignment                     ← EFFECTIVELY CLOSED
Phase 1047B — Guest Portal Host Identity Block                                 ← PROVEN (2026-04-03)
Phase 1047C — Guest Messaging Honesty + Schema Repair                          ← PROVEN (2026-04-03)
Phase 1047E — Host Photo Upload                                                ← BUILT + SURFACED
Phase 1047-polish — Note Area Persistence + Photo Asset Card                   ← PROVEN (2026-04-03)
Phase 1048 — Guest Chat Model (OM Routing + Dossier Thread + Inbox)            ← SURFACED (2026-04-03)
Phase 1049B — Guests List In-Stay Indicator                                    ← SURFACED (2026-04-03)
Phase 1050 — Guest Dossier Chat Tab                                            ← SURFACED (2026-04-03)
Phase 1051 — Operational Guest Inbox UI                                        ← SURFACED (2026-04-03)
Phase 1052 — Host Reply Path                                                   ← PROVEN (2026-04-03)
Phase 1053 — Guest Portal Thread View                                          ← BUILT + SURFACED (proof pending)
Phase 1058 — PKA-Bridge Audit Closure + Backend Authorization Hardening         ← CLOSED (2026-04-04)
```

### Staging Deployment Truth (Proven 855A)

| Component | URL / Platform | Status |
|-----------|---------------|--------|
| Frontend | `https://domaniqo-staging.vercel.app` (Vercel) | ✅ Live |
| Backend | Railway | ✅ Live |
| Database | Supabase (`reykggmlcehswrxjviup`) | ✅ Connected |
| CORS | Railway `IHOUSE_CORS_ORIGINS` | ✅ Configured |
| Password Auth | `admin@domaniqo.com` | ✅ E2E Proven |
| Google OAuth | Supabase Google provider | ✅ E2E Proven |

### Auth & Identity Status (Proven 855B–855E)

| Item | State |
|------|-------|
| Google OAuth provider | ✅ Enabled in Supabase |
| Site URL | `https://domaniqo-staging.vercel.app` |
| Redirect URL | `https://domaniqo-staging.vercel.app/auth/callback` |
| Google E2E sign-in | ✅ Proven |
| Admin email strategy | Recommended: change Supabase email to Gmail |
| Auto-provision vulnerability | ✅ Fixed (Phase 856A) — `/auth/register/profile` returns 403, no provisioning |
| Linked identity tables | ⏸ Deferred — not needed for current scope |
| Existing invite pipelines | ✅ Audited, no changes needed |

## Deferred Items — Open Items Registry

> Must be reviewed and updated at every phase closure.

| Phase | Title | Status | Reason | Unblock Condition | Planned Phase |
|-------|-------|--------|--------|-------------------|---------------|
| 614 | Pre-Arrival Email (SMTP) | 🟡 Deferred | Requires live SMTP config | `SMTP_HOST/PORT/USER/PASS` env vars configured | TBD — email infra |
| 617 | Wire Form → Checkin Router | 🟡 Deferred | Requires live booking flow | Real check-in data flowing | TBD — live check-in |
| 618 | Wire QR → Checkin Response | 🟡 Deferred | Same blocker as 617 | Same as 617 | TBD — with 617 |
| — | Supabase Storage Buckets | ✅ Resolved (Phase 764) | 4 buckets created | N/A | Resolved |
| — | PMS / Channel Manager Layer | 🟡 Deferred | Operational Core gaps identified | After "One Property End-to-End" checkpoint | Post Operational Core wave |
| A-1 | Reference Photos upload UI | 🟠 Phase A gap | Backend CRUD ready, frontend has list+group but no upload widget | Add file picker + POST to `/properties/{id}/reference-photos` | Phase A follow-up |
| A-2 | Tasks tab — read-only | 🟠 Phase A gap | Tasks display works but no create/assign/status change from property detail | Wire task mutation actions to property context | Phase D or separate |
| A-3 | Issues tab — placeholder | 🟠 Phase A gap | `problem_reports` table exists but no API endpoints or UI | Build Issues API + wire to tab | Phase F |
| A-4 | Audit tab — data flow unproven | 🟠 Phase A gap | Table structure renders but property-linked audit entries may not exist | Verify audit `entity_id` filtering works with real data | Phase A follow-up |

> **Phase A Status: Usable Foundation** — House Info (16 editable fields) and Overview (6 live cards) are fully deep. Photos, Tasks, Issues, and Audit tabs are structural but not spec-complete. See gaps A-1 through A-4 above.

| B-1 | Worker-to-property assignment missing | 🟠 Phase B gap | Workers are global per tenant, no way to assign worker to specific properties | Build `worker_property_assignments` table + UI assignment surface | Phase D or separate |
| B-2 | Role is label-only, no role-specific behavior | 🟠 Phase B gap | Cleaner/CheckIn/Maintenance get same UI and permissions — role doesn't drive behavior | Wire role to route guards + role-specific dashboards | Phase C/D |
| B-3 | Communication channel config not surfaced | 🟠 Phase B gap | `worker_preferences` API exists but Manage Users doesn't show/edit channel per worker | Add channel selector (LINE/WhatsApp/SMS) to User Detail panel | Phase D/E |
| B-4 | No avatar / profile photo | 🟠 Phase B gap | No visual identity for workers — harder to identify in operations | Add photo upload to User Detail + display in table | Follow-up |
| B-5 | UUID-only users need display_name | 🟠 Phase B gap | 4 of 6 users show as raw UUIDs because display_name is empty | Populate via data migration or require on invite | Data cleanup task |

> **Phase B Status: Usable User Management Foundation** — Role+permission CRUD works (invite, edit role, toggle permissions, deactivate). Not operational staff management yet: no property assignment, no channel config, no role-specific behavior, no avatar. See gaps B-1 through B-5 above.

| D-1 | Passport capture — dev bypass active, no camera/storage | 🟠 Phase D gap | `DEV_PASSPORT_BYPASS=true` in page.tsx: number + photo both skippable. **Production rule**: number + photo BOTH required before Continue. Flip flag to `false` when camera capture + storage are wired. | Build passport_documents table + upload API + camera integration, then set `DEV_PASSPORT_BYPASS=false` | Phase D deepening |
| D-2 | Deposit handling — no persistence/audit | 🟠 Phase D gap | Deposit method/amount selected in UI only — no record saved | Build deposit_payments table + POST endpoint + audit trail | Phase D deepening |
| D-3 | Welcome info — no real messaging integration | 🟠 Phase D gap | LINE/Telegram/WhatsApp buttons show toast but send nothing | Wire to messaging provider APIs (LINE first) + message log | Phase D/E deepening |
| D-4 | Navigate button — no-op | 🟠 Phase D gap | 📍 button does nothing — should open Maps with property GPS coordinates | Wire to `gps_latitude`/`gps_longitude` from property record → Google Maps | Quick fix |
| D-5 | Property state not changed on complete | 🟠 Phase D gap | Complete Check-in only PATCHes booking status, not property state → Occupied | Add property state transition in complete handler | Phase D deepening |
| D-6 | No audit event on check-in completion | 🟠 Phase D gap | Spec requires audit event written on completion — not implemented | POST audit event on Complete Check-in | Phase D deepening |
| D-7 | Check-out flow not built | 🔴 Phase D gap | 4-step check-out (Inspection → Issues → Deposit Resolution → Complete) entirely missing | Build checkout flow as separate view or tab in /ops/checkin | Phase D or Phase F |

> **Phase D Status: Usable Mobile Check-in UI Foundation** — 6-step flow renders with real booking data (50 bookings from tenant). Only the final status PATCH is wired to backend. Passport, deposit, welcome, navigation, property state change, and audit are all UI-only. Check-out flow not built. See gaps D-1 through D-7 above.

## Permanent Workflow Principles (Locked)

1. **Architecture-aware product build** — always check `.agent/architecture/` and `docs/vision/` before building
2. **PMS deferred, not discarded** — all PMS code/docs/schemas remain; resumes after Operational Core
3. **UI walkthrough checkpoints every 1–3 phases** — no invisible progress without surfaced product proof
4. **Docs-first alignment before major wave changes** — full gap analysis required before starting new waves
5. **Gap prevention checklist at every audit** — cross-reference architecture docs, Supabase tables, and frontend pages

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only — no updates, no deletes ever
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical (Phase 36)
- `reservation_ref` normalized by `normalize_reservation_ref()` before use (Phase 68)
- HTTP endpoint routes through `ingest_provider_event` → pipeline → `apply_envelope`
- `tenant_id` from verified JWT `sub` claim only — NEVER from payload body (Phase 61+)
- `booking_state` is a read model ONLY — must NEVER contain financial calculations
- All financial read endpoints query `booking_financial_facts` ONLY — never `booking_state`
- Deduplication rule: most-recent `recorded_at` per `booking_id`
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated endpoints.
- Management fee applied AFTER OTA commission on net_to_property (Phase 121)
- OTA_COLLECTING net NEVER included in owner_net_total — honesty invariant (Phase 121)
- External channels (LINE, WhatsApp, Telegram, SMS, Email) are escalation fallbacks ONLY — never source of truth
- **No global fallback chain**: each worker has their preferred `channel_type` in `notification_channels`
- CRITICAL_ACK_SLA_MINUTES = 5 (locked)
- PII documents (passport photos, signatures, cash deposit photos) retained minimum 1 year from check-out, admin-only access, audit-logged. No auto-deletion.
- `GET /checkin-form` NEVER returns raw PII URLs — always redacted. Admin uses `GET /admin/pii-documents/{form_id}` exclusively.
- **INV-MEDIA-01**: No binary data in Postgres. All files in Supabase Storage only.
- **INV-MEDIA-02**: Staff files always go to `staff-documents` (private). Never to `property-photos` (public). Upload routing enforced in `staff_onboarding_router.py`.
- **INV-STORAGE-01**: Guest identity docs (passport, check-in ID) — 90-day auto-delete after checkout. Staff employment docs — retained while employed + 12 months, never auto-deleted.
- **INV-STORAGE-02**: `cleaning-photos` bucket is private. Signed URLs only.
- **INV-STORAGE-03**: Archive verification before live event_log deletion.
- Property delete cascades to Storage: `DELETE /properties/{id}` removes all objects under `property-photos/{id}/`.

## Key Files — Channel Layer (Phases 124, 168, 177, 196, 203, 212, 213)

| File | Role |
|------|------|
| `src/channels/line_escalation.py` | LINE pure module — should_escalate, build_line_message, HMAC-SHA256 verify |
| `src/api/line_webhook_router.py` | GET+POST /line/webhook |
| `src/channels/whatsapp_escalation.py` | WhatsApp pure module — same pattern as LINE |
| `src/api/whatsapp_router.py` | GET+POST /whatsapp/webhook |
| `src/channels/telegram_escalation.py` | Telegram pure module — should_escalate, build_telegram_message (Phase 203) |
| `src/channels/sms_escalation.py` | SMS pure module — mirrors LINE/WhatsApp/Telegram pattern (Phase 212) |
| `src/api/sms_router.py` | GET challenge + POST inbound ACK via Twilio form fields |
| `src/channels/email_escalation.py` | Email pure module — one-click ACK token flow (Phase 213) |
| `src/api/email_router.py` | GET /email/webhook health + GET /email/ack token ACK |
| `src/channels/notification_dispatcher.py` | Core dispatcher — routes by worker's channel_type. No global chain. |
| `src/channels/sla_dispatch_bridge.py` | SLA → dispatcher bridge. Per-worker routing. |
| `src/channels/notification_delivery_writer.py` | Best-effort delivery log writer |

## Key Files — Financial API Layer (Phases 116–122, 191)

| File | Role |
|------|------|
| `src/api/financial_aggregation_router.py` | Ring 1: summary / by-provider / by-property / lifecycle-distribution / multi-currency-overview |
| `src/api/financial_dashboard_router.py` | Ring 2–3: status card, revpar, lifecycle-by-property |
| `src/api/reconciliation_router.py` | Ring 3: Exception-first reconciliation inbox |
| `src/api/cashflow_router.py` | Ring 3: Weekly inflow buckets, 30/60/90-day projection |
| `src/api/owner_statement_router.py` | Ring 4: Per-booking line items + PDF export (Phase 188) |
| `src/api/ota_comparison_router.py` | Ring 3: Per-OTA commission rate, net-to-gross, revenue share |
| `src/api/revenue_report_router.py` | Phase 215: GET /revenue-report/portfolio + GET /revenue-report/{id} |
| `src/api/portfolio_dashboard_router.py` | Phase 216: GET /portfolio/dashboard — occupancy+revenue+tasks+sync per property |
| `src/api/integration_management_router.py` | Phase 217: GET /admin/integrations + /admin/integrations/summary |

## Key Files — Task Layer (Phases 111–117, 206–207)

| File | Role |
|------|------|
| `src/tasks/task_model.py` | TaskKind (6 kinds incl GUEST_WELCOME), TaskStatus, TaskPriority, WorkerRole, Task dataclass |
| `src/tasks/task_automator.py` | Pure tasks_for_booking_created / canceled / amended |
| `src/tasks/pre_arrival_tasks.py` | Pure tasks_for_pre_arrival — GUEST_WELCOME + enriched CHECKIN_PREP (Phase 206) |
| `src/tasks/task_writer.py` | Supabase upsert/cancel/reschedule — wired into service.py |
| `src/tasks/task_router.py` | GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status, POST /tasks/pre-arrival/{booking_id} |
| `src/tasks/sla_engine.py` | evaluate() — ACK_SLA_BREACH + COMPLETION_SLA_BREACH. CRITICAL_ACK_SLA_MINUTES=5. |
| `src/api/worker_router.py` | GET /worker/tasks, PATCH /acknowledge, PATCH /complete |
| `src/services/conflict_auto_resolver.py` | Phase 207 — run_auto_check() — auto-conflict on BOOKING_CREATED/AMENDED |

## Key Files — AI Copilot Layer (Phases 222–227, 230–231)

| File | Role |
|------|------|
| `src/api/ai_context_router.py` | GET /ai/context/property/{id} + GET /ai/context/operations-day |
| `src/api/manager_copilot_router.py` | POST /ai/copilot/morning-briefing — 5 languages, LLM + heuristic |
| `src/api/financial_explainer_router.py` | GET /ai/copilot/financial/explain/{booking_id} + reconciliation-summary |
| `src/api/task_recommendation_router.py` | POST /ai/copilot/task-recommendations — deterministic scoring |
| `src/api/anomaly_alert_broadcaster.py` | POST /ai/copilot/anomaly-alerts — 3-domain health scanner |
| `src/api/guest_messaging_copilot.py` | POST /ai/copilot/guest-message-draft — 6 intents, 5 langs, 3 tones |
| `src/api/ai_audit_log_router.py` | Phase 230: GET /ai/audit-log — AI decision audit trail |
| `src/api/worker_copilot_router.py` | Phase 231: POST /ai/copilot/worker-assist — mobile contextual assists |
| `src/services/llm_client.py` | Provider-agnostic LLM client (OpenAI) |
| `src/services/ai_audit_log.py` | AI audit log writer |

## Key Files — Recent Additions (Phases 232–238)

| File | Role |
|------|------|
| `src/services/pre_arrival_scanner.py` | Phase 232: Guest pre-arrival automation chain |
| `src/api/revenue_forecast_router.py` | Phase 233: Revenue forecast engine |
| `src/api/worker_availability_router.py` | Phase 234: Shift & Availability Scheduler — worker_shifts table |
| `src/api/conflicts_router.py` | Phase 235: Enhanced — GET /admin/conflicts/dashboard |
| `src/api/guest_messages_router.py` | Phase 236: POST+GET /guest-messages/{booking_id} |
| `docker-compose.staging.yml` | Phase 237: Staging environment |
| `src/adapters/ota/tripcom.py` | Phase 238: Ctrip/Trip.com enhanced adapter |

## Key Files — Recent Additions (Phases 246–304)

| File | Role |
|------|------|
| `src/api/rate_card_router.py` | Phase 246: GET/POST /properties/{id}/rate-cards |
| `src/api/guest_feedback_router.py` | Phase 247: GET/POST/DELETE /admin/guest-feedback |
| `src/api/task_template_router.py` | Phase 248: GET/POST/DELETE /admin/task-templates |
| `src/adapters/outbound/bookingcom_content.py` | Phase 250: Booking.com content push builder |
| `src/api/content_push_router.py` | Phase 250: POST /admin/content/push/{property_id} |
| `src/services/pricing_engine.py` | Phase 251: Pure suggest_prices() + PriceSuggestion |
| `src/api/pricing_suggestion_router.py` | Phase 251: GET /pricing/suggestion/{property_id} |
| `src/api/owner_financial_report_v2_router.py` | Phase 252: GET /owner/financial-report |
| `src/api/staff_performance_router.py` | Phase 253: GET /admin/staff/performance + /{worker_id} |
| `src/services/bulk_operations.py` | Phase 255: bulk_cancel_bookings, bulk_assign_tasks, bulk_trigger_sync |
| `src/api/bulk_operations_router.py` | Phase 255: POST /admin/bulk/cancel, /tasks/assign, /sync/trigger |
| `src/services/webhook_event_log.py` | Phase 261: append-only event log, no PII, max 5000 entries |
| `src/api/webhook_event_log_router.py` | Phase 261: GET /admin/webhook-log, /stats; POST /test |
| `src/services/guest_portal.py` | Phase 262: GuestBookingView, token validation, stub_lookup |
| `src/api/guest_portal_router.py` | Phase 262: GET /guest/booking/{ref}, /wifi, /rules |
| `src/services/monitoring.py` | Phase 263: record_request(), latency histogram, health metrics |
| `src/api/monitoring_router.py` | Phase 263: GET /admin/monitor, /health, /latency |
| `src/services/analytics.py` | Phase 264: top_properties(), ota_mix(), revenue_summary() |
| `src/api/analytics_router.py` | Phase 264: GET /admin/analytics/top-properties, /ota-mix, /revenue-summary |
| `tests/conftest.py` | Phase 283: Session-scoped env var management, rate limiter reset |
| `deploy_checklist.sh` | Phase 286: Production Docker hardening validation script |
| `src/api/org_router.py` | Phase 296: GET/POST /org endpoints |
| `src/api/auth_router.py` | Phase 297: POST /auth/login, /auth/refresh, /auth/logout |
| `src/api/session_router.py` | Phase 297: GET /session/me, session validation |
| `src/api/guest_token_router.py` | Phase 298: POST /guest/verify-token, issue/verify HMAC tokens |
| `src/api/notification_router.py` | Phase 299: POST /notifications/send-sms, /send-email, /guest-token-send, GET /notifications/log |
| `src/services/owner_portal_data.py` | Phase 301: 6 functions for owner portal rich summary |
| `tests/test_guest_token_e2e.py` | Phase 302: 7 test suites, real HMAC crypto, live Supabase integration |
| `src/scripts/seed_owner_portal.py` | Phase 303: deterministic booking seeder (20 bookings, 3 properties) |

## Key Files — SSE Event Bus + Frontend Real Data (Phases 306-314)

| File | Role |
|------|------|
| `src/channels/sse_broker.py` | Phase 306: 6 named channels (tasks, bookings, sync, alerts, financial, system), convenience publishers |
| `src/api/sse_router.py` | Phase 306: GET /events/stream?channels= filtering |
| `ihouse-ui/app/admin/notifications/page.tsx` | Phase 311: NEW — Admin notification delivery dashboard |
| `ihouse-ui/app/manager/page.tsx` | Phase 312: Morning briefing widget, language selector, LLM/heuristic badge |
| `src/main.py` | Phase 313: CORSMiddleware added (IHOUSE_CORS_ORIGINS) |
| `docker-compose.production.yml` | Phase 313: Frontend Next.js service added |

## Key Files — Frontend (ihouse-ui/, Phases 287–291)

| File | Role |
|------|------|
| `ihouse-ui/app/layout.tsx` | Root layout — Domaniqo branding, sidebar |
| `ihouse-ui/app/dashboard/page.tsx` | Operations dashboard — portfolio grid, 60s auto-refresh |
| `ihouse-ui/app/bookings/page.tsx` | Booking management — list, filters |
| `ihouse-ui/app/bookings/[id]/page.tsx` | Booking detail view |
| `ihouse-ui/app/tasks/page.tsx` | Worker task list |
| `ihouse-ui/app/tasks/[id]/page.tsx` | Task detail view |
| `ihouse-ui/app/financial/page.tsx` | Financial dashboard — OTA donut, cashflow |
| `ihouse-ui/app/financial/statements/page.tsx` | Owner statements |
| `ihouse-ui/app/calendar/page.tsx` | Booking calendar |
| `ihouse-ui/app/guests/page.tsx` | Guest profiles |
| `ihouse-ui/app/guests/[id]/page.tsx` | Guest detail |
| `ihouse-ui/app/worker/page.tsx` | Worker mobile view |
| `ihouse-ui/app/owner/page.tsx` | Owner portal |
| `ihouse-ui/app/manager/page.tsx` | Manager activity feed |
| `ihouse-ui/app/admin/page.tsx` | Admin settings |
| `ihouse-ui/app/admin/dlq/page.tsx` | DLQ replay UI |
| `ihouse-ui/app/login/page.tsx` | Login page |

## Key Files — HTTP API Layer (Phases 58–64)

| File | Role |
|------|------|
| `src/main.py` | FastAPI app entrypoint (all routers registered here) |
| `src/api/webhooks.py` | `POST /webhooks/{provider}` |
| `src/api/auth.py` | JWT auth dependency |
| `src/api/rate_limiter.py` | Per-tenant rate limiting |
| `src/api/health.py` | Dependency health checks (Phase 64) |
| `src/api/financial_router.py` | `GET /financial/{booking_id}` (Phase 67) |
| `src/schemas/responses.py` | OpenAPI Pydantic response models (Phase 63) |

## Environment Variables

| Var | Default | Effect |
|-----|---------|--------|
| `IHOUSE_WEBHOOK_SECRET_{PROVIDER}` | unset | sig verification skipped when unset |
| `IHOUSE_JWT_SECRET` | unset | 503 if unset and IHOUSE_DEV_MODE≠true |
| `IHOUSE_API_KEY` | unset | API key for external integrations |
| `IHOUSE_DEV_MODE` | unset | "true" = skip JWT auth, return dev-tenant. MUST be false in production (Phase 276) |
| `IHOUSE_RATE_LIMIT_RPM` | 60 | req/min per tenant, 0 = disabled |
| `IHOUSE_ENV` | "development" | health response label |
| `IHOUSE_TENANT_ID` | unset | production tenant UUID |
| `SUPABASE_URL` | required | Supabase project URL |
| `SUPABASE_KEY` | required | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | required | Used by all financial/admin routers (Phases 116+) |
| `IHOUSE_LINE_SECRET` | unset | LINE channel secret (sig verify) |
| `IHOUSE_LINE_CHANNEL_TOKEN` | unset | LINE channel access token |
| `IHOUSE_WHATSAPP_TOKEN` | unset | production WhatsApp dispatch |
| `IHOUSE_WHATSAPP_PHONE_NUMBER_ID` | unset | Meta Cloud API phone ID |
| `IHOUSE_WHATSAPP_APP_SECRET` | unset | HMAC sig verification |
| `IHOUSE_WHATSAPP_VERIFY_TOKEN` | unset | Meta webhook challenge token |
| `IHOUSE_TELEGRAM_BOT_TOKEN` | unset | Telegram bot API token |
| `IHOUSE_SMS_TOKEN` | unset | SMS provider API token (Phase 212) |
| `IHOUSE_EMAIL_TOKEN` | unset | Email provider API token (Phase 213) |
| `IHOUSE_DRY_RUN` | unset | skip real outbound API calls |
| `IHOUSE_THROTTLE_DISABLED` | unset | skip rate limiting in outbound |
| `IHOUSE_RETRY_DISABLED` | unset | skip exponential backoff |
| `IHOUSE_SYNC_LOG_DISABLED` | unset | skip persistence of sync results |
| `IHOUSE_SYNC_CALLBACK_URL` | unset | webhook URL for sync.ok events |
| `IHOUSE_SCHEDULER_ENABLED` | unset | enable APScheduler jobs (Phase 221) |
| `IHOUSE_SLA_SWEEP_INTERVAL` | 120 | SLA sweep interval in seconds |
| `IHOUSE_DLQ_ALERT_INTERVAL` | 600 | DLQ alert check interval in seconds |
| `OPENAI_API_KEY` | unset | OpenAI API key for AI copilot endpoints |
| `SENTRY_DSN` | unset | Sentry error tracking DSN |
| `PORT` | 8000 | uvicorn port |
| `UVICORN_WORKERS` | 1 | number of uvicorn worker processes |
| `IHOUSE_GUEST_TOKEN_SECRET` | required | HMAC-SHA256 secret for guest portal tokens (Phase 298) |
| `IHOUSE_TWILIO_SID` | unset | Twilio Account SID (Phase 299) |
| `IHOUSE_TWILIO_TOKEN` | unset | Twilio Auth Token (Phase 299) |
| `IHOUSE_TWILIO_FROM` | unset | Sending phone number E.164 (Phase 299) |
| `IHOUSE_SENDGRID_KEY` | unset | SendGrid API key (Phase 299) |
| `IHOUSE_SENDGRID_FROM` | unset | Sending email address (Phase 299) |
| `IHOUSE_CORS_ORIGINS` | unset | Comma-separated allowed CORS origins for frontend (Phase 313) |

## Tests

**8,138 passed, 52 failed (pre-existing mock stubs), 22 skipped. TypeScript 0 errors. Phases 981–1058 closed. Active: Phase 1059.**

> The 52 failures are pre-existing mock mismatches in wave7/wave5/wave3/task model/router/system/guest portal/reconciliation suites. None introduced by Phase 1058. Test contract files updated: `test_dlq_e2e.py`, `test_admin_audit_log_contract.py`, `test_admin_properties_e2e.py`.
