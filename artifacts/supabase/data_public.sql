SET session_replication_role = replica;

--
-- PostgreSQL database dump
--

-- \restrict 5CXwkQDkqrKY5rB8WCOqyFfV4mvMqSLfAXlgeG0h9gh4a1gvgIK1LhS9Z8UJOH6

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: booking_overrides; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."booking_overrides" ("override_id", "booking_id", "property_id", "status", "required_approver_role", "conflicts_json", "request_id", "created_at_ms", "updated_at_ms") FROM stdin;
\.


--
-- Data for Name: event_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."event_log" ("event_id", "kind", "occurred_at", "payload_json", "envelope_id") FROM stdin;
test_16b_booking_created_0003	BOOKING_CREATED	2026-03-02 12:31:16.217074+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "phase_16b_test_event_3"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_0003", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_16b_booking_created_0003"}}, "idempotency": {"request_id": "test_16b_booking_created_0003"}, "occurred_at": "2026-03-02T12:31:16.217074Z"}	test_16b_booking_created_0003
test_16b_booking_created_0005	BOOKING_CREATED	2026-03-02 12:50:37.743565+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "phase_16b_test_event_5"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_0005", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_16b_booking_created_0005"}}, "idempotency": {"request_id": "test_16b_booking_created_0005"}, "occurred_at": "2026-03-02T12:50:37.743565Z"}	test_16b_booking_created_0005
test_16b_booking_created_0006	BOOKING_CREATED	2026-03-02 12:56:41.124355+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "phase_16b_test_event_6"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_0006", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_16b_booking_created_0006"}, "occurred_at": "2026-03-02T12:00:00Z"}, "idempotency": {"request_id": "test_16b_booking_created_0006"}, "occurred_at": "2026-03-02T12:56:41.124355Z"}	test_16b_booking_created_0006
test_direct_key_0001	BOOKING_CREATED	2026-03-02 13:20:24.575741+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "direct_key_test"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_direct_0001", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_direct_key_0001"}}, "idempotency": {"request_id": "test_direct_key_0001"}, "occurred_at": "2026-03-02T13:20:24.575741Z"}	test_direct_key_0001
test_noop_0002	BOOKING_CREATED	2026-03-02 13:33:06.97466+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "noop"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_noop_0002", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_noop_0002"}}, "idempotency": {"request_id": "test_noop_0002"}, "occurred_at": "2026-03-02T13:33:06.974660Z"}	test_noop_0002
test_noop_0003	BOOKING_CREATED	2026-03-02 13:38:29.746225+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "noop"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_noop_0003", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_noop_0003"}}, "idempotency": {"request_id": "test_noop_0003"}, "occurred_at": "2026-03-02T13:38:29.746225Z"}	test_noop_0003
test_noop_0004	BOOKING_CREATED	2026-03-02 13:41:03.620267+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "noop"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_noop_0004", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_noop_0004"}}, "idempotency": {"request_id": "test_noop_0004"}, "occurred_at": "2026-03-02T13:41:03.620267Z"}	test_noop_0004
c638abe6-4b68-4995-8019-fb54220d273f	envelope_received	2026-03-02 14:16:40.084907+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "idem_1"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_idem_0001", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_noop_idem_0001"}}, "envelope_id": "test_noop_idem_0001", "idempotency": {"request_id": "test_noop_idem_0001"}, "occurred_at": "2026-03-02T14:16:40.084907Z"}	test_noop_idem_0001
test_noop_idem_0001	BOOKING_CREATED	2026-03-02 14:16:41.456932+00	{"type": "BOOKING_CREATED", "actor": {"role": "test", "actor_id": "system_test"}, "payload": {"data": {"note": "idem_2"}, "actor": {"role": "test", "actor_id": "system_test"}, "source": "test", "entity_id": "booking_test_idem_0001", "tenant_id": "TENANT_TEST", "idempotency": {"request_id": "test_noop_idem_0001"}}, "idempotency": {"request_id": "test_noop_idem_0001"}, "occurred_at": "2026-03-02T14:16:41.456932Z"}	test_noop_idem_0001
8c632e1e-33d8-4859-81e8-0a4cd56c1d99	BOOKING_CREATED	2026-03-02 15:16:58.937134+00	{"kind": "BOOKING_CREATED", "booking_id": "b_test_0001"}	phase16c_gate_test_0001
manual-002:envelope_received	envelope_received	2026-03-03 14:51:49.340063+00	{"actor": {"role": "system", "actor_id": "system"}, "idempotency": {"request_id": "manual-002"}, "occurred_at": "2026-03-03 14:51:49.340063+00"}	manual-002
sql-smoke-001:envelope_received	envelope_received	2026-03-03 12:56:14.297133+00	{"idempotency": {"request_id": "sql-smoke-001"}, "occurred_at": "2026-03-03 12:56:14.297133+00"}	sql-smoke-001
sql-smoke-001:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 12:56:14.297133+00	{"type": "BOOKING_CREATED", "payload": {"booking_id": "demo-1"}, "occurred_at": "2026-03-03 12:56:14.297133+00"}	sql-smoke-001
smoke-001:envelope_received	envelope_received	2026-03-03 13:48:26.033561+00	{"type": "BOOKING_CREATED", "actor": {"role": "system", "actor_id": "system"}, "payload": {"actor": {"role": "system", "actor_id": "system"}, "booking_id": "demo-1", "idempotency": {"request_id": "smoke-001"}}, "envelope_id": "smoke-001", "idempotency": {"request_id": "smoke-001"}, "occurred_at": "2026-03-03T13:48:25.048144Z"}	smoke-001
manual-001:envelope_received	envelope_received	2026-03-03 13:56:24.860594+00	{"actor": {"role": "system", "actor_id": "system"}, "envelope_id": "manual-001", "idempotency": {"request_id": "manual-001"}, "occurred_at": "2026-03-03 13:56:24.860594+00"}	manual-001
manual-001:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 13:56:24.860594+00	{"type": "BOOKING_CREATED", "payload": {"booking_id": "manual-1"}, "occurred_at": "2026-03-03 13:56:24.860594+00"}	manual-001
manual-002:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 14:51:49.340063+00	{"type": "BOOKING_CREATED", "payload": {"booking_id": "manual-2"}, "occurred_at": "2026-03-03 14:51:49.340063+00"}	manual-002
manual-002:STATE_UPSERT	STATE_UPSERT	2026-03-03 14:51:49.340063+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "manual-2", "state_json": {"status": "created", "booking_id": "manual-2"}, "expected_last_event_id": null}, "occurred_at": "2026-03-03 14:51:49.340063+00"}	manual-002
self-003:envelope_received	envelope_received	2026-03-03 15:13:52.759645+00	{"actor": {"role": "self_booking", "actor_id": "user_1"}, "idempotency": {"request_id": "self-003"}, "occurred_at": "2026-03-03 15:13:52.759645+00"}	self-003
self-003:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 15:13:52.759645+00	{"type": "BOOKING_CREATED", "payload": {"tags": ["self", "test"], "notes": "test self booking", "adults": 2, "source": "self_booking", "status": "confirmed", "infants": 0, "check_in": "2026-03-10", "children": 0, "currency": "THB", "timezone": "Asia/Bangkok", "check_out": "2026-03-14", "tenant_id": "acme", "booking_id": "bk_self_003", "created_at": "2026-03-03 15:13:52.759645+00", "created_by": "user_1", "guest_name": "John Doe", "source_ref": "admin_panel", "guest_email": "john@example.com", "guest_phone": "+66XXXXXXXXX", "paid_amount": 0, "property_id": "villa_044", "total_amount": 18000, "payment_status": "unpaid", "reservation_ref": "bk_self_003"}, "occurred_at": "2026-03-03 15:13:52.759645+00"}	self-003
self-004:envelope_received	envelope_received	2026-03-03 15:37:55.172787+00	{"actor": {"role": "self_booking", "actor_id": "user_1"}, "idempotency": {"request_id": "self-004"}, "occurred_at": "2026-03-03 15:37:55.172787+00"}	self-004
self-004:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 15:37:55.172787+00	{"type": "BOOKING_CREATED", "payload": {"tags": ["self", "test"], "notes": "test canonical", "adults": 2, "source": "self_booking", "status": "confirmed", "infants": 0, "check_in": "2026-03-10", "children": 0, "currency": "THB", "timezone": "Asia/Bangkok", "check_out": "2026-03-14", "tenant_id": "acme", "booking_id": "bk_self_004", "created_at": "2026-03-03 15:37:55.172787+00", "created_by": "user_1", "guest_name": "John Doe", "source_ref": "admin_panel", "guest_email": "john@example.com", "guest_phone": "+66XXXXXXXXX", "paid_amount": 0, "property_id": "villa_044", "total_amount": 18000, "payment_status": "unpaid", "reservation_ref": "bk_self_004"}, "occurred_at": "2026-03-03 15:37:55.172787+00"}	self-004
self-004:STATE_UPSERT	STATE_UPSERT	2026-03-03 15:37:55.172787+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_self_004", "state_json": {"status": "confirmed", "booking_id": "bk_self_004"}, "expected_last_event_id": null}, "occurred_at": "2026-03-03 15:37:55.172787+00"}	self-004
self-005:envelope_received	envelope_received	2026-03-03 15:44:48.546409+00	{"actor": {"role": "self_booking", "actor_id": "user_123"}, "idempotency": {"request_id": "self-005"}, "occurred_at": "2026-03-03 15:44:48.546409+00"}	self-005
self-005:BOOKING_CREATED	BOOKING_CREATED	2026-03-03 15:44:48.546409+00	{"type": "BOOKING_CREATED", "payload": {"booking_id": "bk_self_005"}, "occurred_at": "2026-03-03 15:44:48.546409+00"}	self-005
self-005:STATE_UPSERT	STATE_UPSERT	2026-03-03 15:44:48.546409+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_self_005", "state_json": {"booking": {"booking_id": "bk_self_005"}, "booking_id": "bk_self_005", "source_event_id": "self-005:BOOKING_CREATED"}}, "occurred_at": "2026-03-03 15:44:48.546409+00"}	self-005
env_test_17c_001:envelope_received	envelope_received	2026-03-03 17:50:11.129503+00	{"idempotency": {"request_id": "env_test_17c_001"}}	env_test_17c_001
env_test_17c_001:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 00:00:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_001", "property_id": "prop_001", "reservation_ref": "ref_001"}, "occurred_at": "2026-03-04T00:00:00Z"}	env_test_17c_001
env_test_17c_001:STATE_UPSERT	STATE_UPSERT	2026-03-03 17:50:11.129503+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_17c_001", "state_json": {"booking": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_001", "property_id": "prop_001", "reservation_ref": "ref_001"}, "booking_id": "bk_test_17c_001", "source_event_id": "env_test_17c_001:BOOKING_CREATED"}}, "occurred_at": "2026-03-03 17:50:11.129503+00"}	env_test_17c_001
env_test_17c_b2_first_ok:envelope_received	envelope_received	2026-03-03 18:12:02.49614+00	{"idempotency": {"request_id": "env_test_17c_b2_first_ok"}}	env_test_17c_b2_first_ok
env_test_17c_b2_first_ok:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 00:01:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "check_in": "2026-03-10", "check_out": "2026-03-12", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_b2a", "property_id": "prop_001", "reservation_ref": "ref_b2a"}, "occurred_at": "2026-03-04T00:01:00Z"}	env_test_17c_b2_first_ok
env_test_17c_b2_first_ok:STATE_UPSERT	STATE_UPSERT	2026-03-03 18:12:02.49614+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_17c_b2a", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-10", "check_out": "2026-03-12", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_b2a", "property_id": "prop_001", "reservation_ref": "ref_b2a"}, "booking_id": "bk_test_17c_b2a", "source_event_id": "env_test_17c_b2_first_ok:BOOKING_CREATED"}}, "occurred_at": "2026-03-03 18:12:02.49614+00"}	env_test_17c_b2_first_ok
env_test_18_create_active_1:envelope_received	envelope_received	2026-03-04 05:17:42.86325+00	{"idempotency": {"request_id": "env_test_18_create_active_1"}}	env_test_18_create_active_1
env_test_18_create_active_1:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 05:00:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_a", "property_id": "prop_001", "reservation_ref": "ref_18_a"}, "occurred_at": "2026-03-04T05:00:00Z"}	env_test_18_create_active_1
env_test_18_create_active_1:STATE_UPSERT	STATE_UPSERT	2026-03-04 05:17:42.86325+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_18_a", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_a", "property_id": "prop_001", "reservation_ref": "ref_18_a"}, "booking_id": "bk_test_18_a", "source_event_id": "env_test_18_create_active_1:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 05:17:42.86325+00"}	env_test_18_create_active_1
env_test_18_cancel_1:envelope_received	envelope_received	2026-03-04 05:19:36.445632+00	{"idempotency": {"request_id": "env_test_18_cancel_1"}}	env_test_18_cancel_1
env_test_18_cancel_1:BOOKING_CANCELED	BOOKING_CANCELED	2026-03-04 05:20:00+00	{"type": "BOOKING_CANCELED", "payload": {"booking_id": "bk_test_18_a"}, "occurred_at": "2026-03-04T05:20:00Z"}	env_test_18_cancel_1
env_test_18_cancel_1:STATE_UPSERT:BOOKING_CANCELED	STATE_UPSERT	2026-03-04 05:19:36.445632+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_18_a", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_a", "property_id": "prop_001", "reservation_ref": "ref_18_a"}, "booking_id": "bk_test_18_a", "source_event_id": "env_test_18_cancel_1:BOOKING_CANCELED"}}, "occurred_at": "2026-03-04 05:19:36.445632+00"}	env_test_18_cancel_1
env_test_18_overlap_after_cancel:envelope_received	envelope_received	2026-03-04 05:20:48.104245+00	{"idempotency": {"request_id": "env_test_18_overlap_after_cancel"}}	env_test_18_overlap_after_cancel
env_test_18_overlap_after_cancel:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 05:25:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "check_in": "2026-03-21", "check_out": "2026-03-23", "tenant_id": "tenant_1", "booking_id": "bk_test_18_b", "property_id": "prop_001", "reservation_ref": "ref_18_b"}, "occurred_at": "2026-03-04T05:25:00Z"}	env_test_18_overlap_after_cancel
env_test_18_overlap_after_cancel:STATE_UPSERT	STATE_UPSERT	2026-03-04 05:20:48.104245+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_18_b", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-21", "check_out": "2026-03-23", "tenant_id": "tenant_1", "booking_id": "bk_test_18_b", "property_id": "prop_001", "reservation_ref": "ref_18_b"}, "booking_id": "bk_test_18_b", "source_event_id": "env_test_18_overlap_after_cancel:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 05:20:48.104245+00"}	env_test_18_overlap_after_cancel
env_test_19_biz_1:envelope_received	envelope_received	2026-03-04 05:25:34.496162+00	{"idempotency": {"request_id": "env_test_19_biz_1"}}	env_test_19_biz_1
env_test_19_biz_1:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 06:00:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_19_a", "property_id": "prop_002", "reservation_ref": "ref_19_same"}, "occurred_at": "2026-03-04T06:00:00Z"}	env_test_19_biz_1
env_test_19_biz_1:STATE_UPSERT	STATE_UPSERT	2026-03-04 05:25:34.496162+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_19_a", "state_json": {"booking": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_19_a", "property_id": "prop_002", "reservation_ref": "ref_19_same"}, "booking_id": "bk_test_19_a", "source_event_id": "env_test_19_biz_1:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 05:25:34.496162+00"}	env_test_19_biz_1
env_test_19_biz_2:envelope_received	envelope_received	2026-03-04 05:25:58.816629+00	{"idempotency": {"request_id": "env_test_19_biz_2"}}	env_test_19_biz_2
env_test_19_biz_2:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 06:01:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_19_b", "property_id": "prop_002", "reservation_ref": "ref_19_same"}, "occurred_at": "2026-03-04T06:01:00Z"}	env_test_19_biz_2
env_test_18_cancel_b:envelope_received	envelope_received	2026-03-04 05:48:44.485129+00	{"idempotency": {"request_id": "env_test_18_cancel_b"}}	env_test_18_cancel_b
env_test_18_cancel_b:BOOKING_CANCELED	BOOKING_CANCELED	2026-03-04 05:31:00+00	{"type": "BOOKING_CANCELED", "payload": {"booking_id": "bk_test_18_b"}, "occurred_at": "2026-03-04T05:31:00Z"}	env_test_18_cancel_b
env_test_18_cancel_b:STATE_UPSERT:BOOKING_CANCELED	STATE_UPSERT	2026-03-04 05:48:44.485129+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_18_b", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-21", "check_out": "2026-03-23", "tenant_id": "tenant_1", "booking_id": "bk_test_18_b", "property_id": "prop_001", "reservation_ref": "ref_18_b"}, "booking_id": "bk_test_18_b", "source_event_id": "env_test_18_cancel_b:BOOKING_CANCELED"}}, "occurred_at": "2026-03-04 05:48:44.485129+00"}	env_test_18_cancel_b
env_test_18_overlap_after_cancel_b:envelope_received	envelope_received	2026-03-04 05:49:08.747622+00	{"idempotency": {"request_id": "env_test_18_overlap_after_cancel_b"}}	env_test_18_overlap_after_cancel_b
env_test_18_overlap_after_cancel_b:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 05:32:00+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_pass", "property_id": "prop_001", "reservation_ref": "ref_pass_18"}, "occurred_at": "2026-03-04T05:32:00Z"}	env_test_18_overlap_after_cancel_b
env_test_18_overlap_after_cancel_b:STATE_UPSERT	STATE_UPSERT	2026-03-04 05:49:08.747622+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_test_18_pass", "state_json": {"booking": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_pass", "property_id": "prop_001", "reservation_ref": "ref_pass_18"}, "booking_id": "bk_test_18_pass", "source_event_id": "env_test_18_overlap_after_cancel_b:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 05:49:08.747622+00"}	env_test_18_overlap_after_cancel_b
phase19_test_missing_version:envelope_received	envelope_received	2026-03-04 12:24:56.656391+00	{"idempotency": {"request_id": "phase19_test_missing_version"}}	phase19_test_missing_version
phase19_test_missing_version:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 12:24:56.656391+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_1", "property_id": "prop_test_1", "reservation_ref": "ref_test_1"}, "occurred_at": "2026-03-04T12:24:56.656391+00:00"}	phase19_test_missing_version
phase19_test_missing_version:STATE_UPSERT	STATE_UPSERT	2026-03-04 12:24:56.656391+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_phase19_test_1", "state_json": {"booking": {"source": "manual", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_1", "property_id": "prop_test_1", "reservation_ref": "ref_test_1"}, "booking_id": "bk_phase19_test_1", "source_event_id": "phase19_test_missing_version:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 12:24:56.656391+00"}	phase19_test_missing_version
phase19_test_ok:envelope_received	envelope_received	2026-03-04 12:26:00.180368+00	{"idempotency": {"request_id": "phase19_test_ok"}}	phase19_test_ok
phase19_test_ok:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 12:26:00.180368+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual", "check_in": "2026-04-01", "check_out": "2026-04-05", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_2", "property_id": "prop_test_1", "reservation_ref": "ref_test_2"}, "occurred_at": "2026-03-04T12:26:00.180368+00:00", "event_version": 1}	phase19_test_ok
phase19_test_ok:STATE_UPSERT	STATE_UPSERT	2026-03-04 12:26:00.180368+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "bk_phase19_test_2", "state_json": {"booking": {"source": "manual", "check_in": "2026-04-01", "check_out": "2026-04-05", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_2", "property_id": "prop_test_1", "reservation_ref": "ref_test_2"}, "booking_id": "bk_phase19_test_2", "source_event_id": "phase19_test_ok:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 12:26:00.180368+00"}	phase19_test_ok
phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:envelope_received	envelope_received	2026-03-04 13:32:18.762566+00	{"idempotency": {"request_id": "phase19_t3_ok_8baec5b66f39408b9d996971f69a975d"}}	phase19_t3_ok_8baec5b66f39408b9d996971f69a975d
phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 13:32:18.762566+00	{"type": "BOOKING_CREATED", "payload": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "property_id": "p_phase19", "reservation_ref": "r_b_d0e077ab7d8c4eb3813030ed39ae5ec6"}, "occurred_at": "2026-03-04 13:32:18.762566+00"}	phase19_t3_ok_8baec5b66f39408b9d996971f69a975d
phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:STATE_UPSERT	STATE_UPSERT	2026-03-04 13:32:18.762566+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "state_json": {"booking": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "property_id": "p_phase19", "reservation_ref": "r_b_d0e077ab7d8c4eb3813030ed39ae5ec6"}, "booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "source_event_id": "phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 13:32:18.762566+00"}	phase19_t3_ok_8baec5b66f39408b9d996971f69a975d
phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:envelope_received	envelope_received	2026-03-04 13:32:18.762566+00	{"idempotency": {"request_id": "phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8"}}	phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8
phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 13:32:18.762566+00	{"type": "BOOKING_CREATED", "payload": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "property_id": "p_phase19", "reservation_ref": "r_e5571cdb26d94672a4244defab0c1cde"}, "occurred_at": "2026-03-04 13:32:18.762566+00", "event_version": 999}	phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8
phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:STATE_UPSERT	STATE_UPSERT	2026-03-04 13:32:18.762566+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "state_json": {"booking": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "property_id": "p_phase19", "reservation_ref": "r_e5571cdb26d94672a4244defab0c1cde"}, "booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "source_event_id": "phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 13:32:18.762566+00"}	phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8
phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:envelope_received	envelope_received	2026-03-04 15:16:20.305322+00	{"idempotency": {"request_id": "phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c"}}	phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c
phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 15:16:20.305322+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_09c99f0718416d6cc170d9222172e71d", "booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "property_id": "p_618400124a152e834e372afd6b1419a9", "reservation_ref": "r_c7931fcc32fb04fad12505f83fb493de"}, "occurred_at": "2026-03-04 15:16:20.305322+00"}	phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c
phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:STATE_UPSERT	STATE_UPSERT	2026-03-04 15:16:20.305322+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "state_json": {"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_09c99f0718416d6cc170d9222172e71d", "booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "property_id": "p_618400124a152e834e372afd6b1419a9", "reservation_ref": "r_c7931fcc32fb04fad12505f83fb493de"}, "booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "source_event_id": "phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 15:16:20.305322+00"}	phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c
phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:envelope_received	envelope_received	2026-03-04 15:56:47.831684+00	{"idempotency": {"request_id": "phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77"}}	phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77
phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 15:56:47.831684+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_fe78c7176d02ebda0c55517492cdec81", "booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "property_id": "p_dd15d8a4501638352dfdff13025830d9", "reservation_ref": "r_27e98f5e2973c40faaab5be8be35c5d7"}, "occurred_at": "2026-03-04 15:56:47.831684+00"}	phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77
phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:STATE_UPSERT	STATE_UPSERT	2026-03-04 15:56:47.831684+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "state_json": {"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_fe78c7176d02ebda0c55517492cdec81", "booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "property_id": "p_dd15d8a4501638352dfdff13025830d9", "reservation_ref": "r_27e98f5e2973c40faaab5be8be35c5d7"}, "booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "source_event_id": "phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 15:56:47.831684+00"}	phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77
phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:envelope_received	envelope_received	2026-03-04 17:31:37.197535+00	{"idempotency": {"request_id": "phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22"}}	phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22
phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 17:31:37.197535+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_f4fd1ab993e56add90fd56ee33e105e7", "booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "property_id": "p_e73a53aa7f4304b292df9e2293676e36", "reservation_ref": "r_f3c691b49c871350a2b0364082e6cdc3"}, "occurred_at": "2026-03-04 17:31:37.197535+00"}	phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22
phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:STATE_UPSERT	STATE_UPSERT	2026-03-04 17:31:37.197535+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "state_json": {"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_f4fd1ab993e56add90fd56ee33e105e7", "booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "property_id": "p_e73a53aa7f4304b292df9e2293676e36", "reservation_ref": "r_f3c691b49c871350a2b0364082e6cdc3"}, "booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "source_event_id": "phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 17:31:37.197535+00"}	phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22
phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:envelope_received	envelope_received	2026-03-04 17:38:01.494723+00	{"idempotency": {"request_id": "phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d"}}	phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d
phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:BOOKING_CREATED	BOOKING_CREATED	2026-03-04 17:38:01.494723+00	{"type": "BOOKING_CREATED", "payload": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_81eed5c9b7aab74f128df5ab75710432", "booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "property_id": "p_8dffcbb3462e5349d4c9e0a8bdef6394", "reservation_ref": "r_0561d470b9084c965bb06d7b53a11c48"}, "occurred_at": "2026-03-04 17:38:01.494723+00"}	phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d
phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:STATE_UPSERT	STATE_UPSERT	2026-03-04 17:38:01.494723+00	{"type": "STATE_UPSERT", "payload": {"booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "state_json": {"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_81eed5c9b7aab74f128df5ab75710432", "booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "property_id": "p_8dffcbb3462e5349d4c9e0a8bdef6394", "reservation_ref": "r_0561d470b9084c965bb06d7b53a11c48"}, "booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "source_event_id": "phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:BOOKING_CREATED"}}, "occurred_at": "2026-03-04 17:38:01.494723+00"}	phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d
\.


--
-- Data for Name: booking_state; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."booking_state" ("booking_id", "version", "state_json", "updated_at_ms", "last_event_id", "last_envelope_id", "tenant_id", "source", "reservation_ref", "property_id", "check_in", "check_out", "status") FROM stdin;
b_sup_test_001	1	{"state": {"status": "confirmed", "end_date": "2026-06-03", "booking_id": "b_sup_test_001", "guest_name": "Supabase Bob", "start_date": "2026-06-01", "property_id": "p1", "external_ref": "airbnb:ext_sup_001"}, "version": 1, "booking_id": "b_sup_test_001"}	1772306511017	\N	\N	\N	\N	\N	\N	\N	\N	\N
manual-2	1	{"status": "created", "booking_id": "manual-2"}	1772549509340	manual-002:STATE_UPSERT	manual-002	\N	\N	\N	\N	\N	\N	\N
bk_self_003	1	{"tags": ["self", "test"], "guest": {"name": "John Doe", "email": "john@example.com", "phone": "+66XXXXXXXXX"}, "notes": "test self booking", "adults": "2", "source": "self_booking", "status": "confirmed", "infants": "0", "check_in": "2026-03-10", "children": "0", "currency": "THB", "timezone": "Asia/Bangkok", "check_out": "2026-03-14", "tenant_id": "acme", "booking_id": "bk_self_003", "created_at": "2026-03-03 15:13:52.759645+00", "created_by": "user_1", "source_ref": "admin_panel", "paid_amount": "0", "property_id": "villa_044", "total_amount": "18000", "payment_status": "unpaid", "reservation_ref": "bk_self_003"}	1772550832760	self-003:BOOKING_CREATED	self-003	\N	\N	\N	\N	\N	\N	\N
bk_self_004	1	{"status": "confirmed", "booking_id": "bk_self_004"}	1772552275173	self-004:STATE_UPSERT	self-004	\N	\N	\N	\N	\N	\N	\N
bk_self_005	1	{"booking": {"booking_id": "bk_self_005"}, "booking_id": "bk_self_005", "source_event_id": "self-005:BOOKING_CREATED"}	1772552688546	self-005:STATE_UPSERT	self-005	\N	\N	\N	\N	\N	\N	\N
bk_test_17c_001	1	{"booking": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_001", "property_id": "prop_001", "reservation_ref": "ref_001"}, "booking_id": "bk_test_17c_001", "source_event_id": "env_test_17c_001:BOOKING_CREATED"}	1772560211130	env_test_17c_001:STATE_UPSERT	env_test_17c_001	tenant_1	manual	ref_001	prop_001	\N	\N	\N
bk_test_17c_b2a	1	{"booking": {"source": "manual", "check_in": "2026-03-10", "check_out": "2026-03-12", "tenant_id": "tenant_1", "booking_id": "bk_test_17c_b2a", "property_id": "prop_001", "reservation_ref": "ref_b2a"}, "booking_id": "bk_test_17c_b2a", "source_event_id": "env_test_17c_b2_first_ok:BOOKING_CREATED"}	1772561522496	env_test_17c_b2_first_ok:STATE_UPSERT	env_test_17c_b2_first_ok	tenant_1	manual	ref_b2a	prop_001	2026-03-10	2026-03-12	\N
bk_test_18_a	2	{"booking": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_a", "property_id": "prop_001", "reservation_ref": "ref_18_a"}, "booking_id": "bk_test_18_a", "source_event_id": "env_test_18_cancel_1:BOOKING_CANCELED"}	1772601576446	env_test_18_cancel_1:STATE_UPSERT:BOOKING_CANCELED	env_test_18_cancel_1	tenant_1	manual	ref_18_a	prop_001	2026-03-20	2026-03-22	canceled
bk_test_19_a	1	{"booking": {"source": "manual", "tenant_id": "tenant_1", "booking_id": "bk_test_19_a", "property_id": "prop_002", "reservation_ref": "ref_19_same"}, "booking_id": "bk_test_19_a", "source_event_id": "env_test_19_biz_1:BOOKING_CREATED"}	1772601934496	env_test_19_biz_1:STATE_UPSERT	env_test_19_biz_1	tenant_1	manual	ref_19_same	prop_002	\N	\N	active
bk_test_18_b	2	{"booking": {"source": "manual", "check_in": "2026-03-21", "check_out": "2026-03-23", "tenant_id": "tenant_1", "booking_id": "bk_test_18_b", "property_id": "prop_001", "reservation_ref": "ref_18_b"}, "booking_id": "bk_test_18_b", "source_event_id": "env_test_18_cancel_b:BOOKING_CANCELED"}	1772603324485	env_test_18_cancel_b:STATE_UPSERT:BOOKING_CANCELED	env_test_18_cancel_b	tenant_1	manual	ref_18_b	prop_001	2026-03-21	2026-03-23	canceled
bk_test_18_pass	1	{"booking": {"source": "manual", "check_in": "2026-03-20", "check_out": "2026-03-22", "tenant_id": "tenant_1", "booking_id": "bk_test_18_pass", "property_id": "prop_001", "reservation_ref": "ref_pass_18"}, "booking_id": "bk_test_18_pass", "source_event_id": "env_test_18_overlap_after_cancel_b:BOOKING_CREATED"}	1772603348748	env_test_18_overlap_after_cancel_b:STATE_UPSERT	env_test_18_overlap_after_cancel_b	tenant_1	manual	ref_pass_18	prop_001	2026-03-20	2026-03-22	active
bk_phase19_test_1	1	{"booking": {"source": "manual", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_1", "property_id": "prop_test_1", "reservation_ref": "ref_test_1"}, "booking_id": "bk_phase19_test_1", "source_event_id": "phase19_test_missing_version:BOOKING_CREATED"}	1772627096656	phase19_test_missing_version:STATE_UPSERT	phase19_test_missing_version	tenant_test	manual	ref_test_1	prop_test_1	\N	\N	active
bk_phase19_test_2	1	{"booking": {"source": "manual", "check_in": "2026-04-01", "check_out": "2026-04-05", "tenant_id": "tenant_test", "booking_id": "bk_phase19_test_2", "property_id": "prop_test_1", "reservation_ref": "ref_test_2"}, "booking_id": "bk_phase19_test_2", "source_event_id": "phase19_test_ok:BOOKING_CREATED"}	1772627160180	phase19_test_ok:STATE_UPSERT	phase19_test_ok	tenant_test	manual	ref_test_2	prop_test_1	2026-04-01	2026-04-05	active
b_d0e077ab7d8c4eb3813030ed39ae5ec6	1	{"booking": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "property_id": "p_phase19", "reservation_ref": "r_b_d0e077ab7d8c4eb3813030ed39ae5ec6"}, "booking_id": "b_d0e077ab7d8c4eb3813030ed39ae5ec6", "source_event_id": "phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:BOOKING_CREATED"}	1772631138763	phase19_t3_ok_8baec5b66f39408b9d996971f69a975d:STATE_UPSERT	phase19_t3_ok_8baec5b66f39408b9d996971f69a975d	t_phase19	ota	r_b_d0e077ab7d8c4eb3813030ed39ae5ec6	p_phase19	\N	\N	active
b_2fa2e6fc5cec475bb6b647b34cf6d7dc	1	{"booking": {"source": "ota", "tenant_id": "t_phase19", "booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "property_id": "p_phase19", "reservation_ref": "r_e5571cdb26d94672a4244defab0c1cde"}, "booking_id": "b_2fa2e6fc5cec475bb6b647b34cf6d7dc", "source_event_id": "phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:BOOKING_CREATED"}	1772631138763	phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8:STATE_UPSERT	phase19_t3_badver_1b33a15bc4ab49c4a9c69657a4fc0ce8	t_phase19	ota	r_e5571cdb26d94672a4244defab0c1cde	p_phase19	\N	\N	active
b_82cd154560d2808d58ced52bb403a8bd	1	{"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_09c99f0718416d6cc170d9222172e71d", "booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "property_id": "p_618400124a152e834e372afd6b1419a9", "reservation_ref": "r_c7931fcc32fb04fad12505f83fb493de"}, "booking_id": "b_82cd154560d2808d58ced52bb403a8bd", "source_event_id": "phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:BOOKING_CREATED"}	1772637380305	phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c:STATE_UPSERT	phase19_t3_ok_954a99e0442b5774c6284c7da5a2319c	t_09c99f0718416d6cc170d9222172e71d	manual_admin	r_c7931fcc32fb04fad12505f83fb493de	p_618400124a152e834e372afd6b1419a9	2026-03-14	2026-03-16	active
b_ef12aaee275299d2fe8909c87fbe0194	1	{"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_fe78c7176d02ebda0c55517492cdec81", "booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "property_id": "p_dd15d8a4501638352dfdff13025830d9", "reservation_ref": "r_27e98f5e2973c40faaab5be8be35c5d7"}, "booking_id": "b_ef12aaee275299d2fe8909c87fbe0194", "source_event_id": "phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:BOOKING_CREATED"}	1772639807832	phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77:STATE_UPSERT	phase19_t3_ok_23cf5cd76b164fa4faa342001ffebd77	t_fe78c7176d02ebda0c55517492cdec81	manual_admin	r_27e98f5e2973c40faaab5be8be35c5d7	p_dd15d8a4501638352dfdff13025830d9	2026-03-14	2026-03-16	active
b_f268e9c2437edabbe707718ddd93ca70	1	{"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_f4fd1ab993e56add90fd56ee33e105e7", "booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "property_id": "p_e73a53aa7f4304b292df9e2293676e36", "reservation_ref": "r_f3c691b49c871350a2b0364082e6cdc3"}, "booking_id": "b_f268e9c2437edabbe707718ddd93ca70", "source_event_id": "phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:BOOKING_CREATED"}	1772645497198	phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22:STATE_UPSERT	phase19_t3_ok_6ee8833e0d43d44bf3843708d8e63f22	t_f4fd1ab993e56add90fd56ee33e105e7	manual_admin	r_f3c691b49c871350a2b0364082e6cdc3	p_e73a53aa7f4304b292df9e2293676e36	2026-03-14	2026-03-16	active
b_d5cab47342a2e3ceef7ab3817dd18fd6	1	{"booking": {"source": "manual_admin", "check_in": "2026-03-14", "check_out": "2026-03-16", "tenant_id": "t_81eed5c9b7aab74f128df5ab75710432", "booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "property_id": "p_8dffcbb3462e5349d4c9e0a8bdef6394", "reservation_ref": "r_0561d470b9084c965bb06d7b53a11c48"}, "booking_id": "b_d5cab47342a2e3ceef7ab3817dd18fd6", "source_event_id": "phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:BOOKING_CREATED"}	1772645881495	phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d:STATE_UPSERT	phase19_t3_ok_ee3d1ff7b8dfd6762cd31752e6112a4d	t_81eed5c9b7aab74f128df5ab75710432	manual_admin	r_0561d470b9084c965bb06d7b53a11c48	p_8dffcbb3462e5349d4c9e0a8bdef6394	2026-03-14	2026-03-16	active
\.


--
-- Data for Name: bookings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."bookings" ("booking_id", "property_id", "external_ref", "start_date", "end_date", "status", "guest_name", "created_at_ms", "updated_at_ms") FROM stdin;
\.


--
-- Data for Name: conflict_tasks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."conflict_tasks" ("conflict_task_id", "booking_id", "property_id", "status", "priority", "conflicts_json", "request_id", "created_at_ms", "updated_at_ms") FROM stdin;
\.


--
-- Data for Name: envelope_gate; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."envelope_gate" ("envelope_id", "received_at", "payload_json") FROM stdin;
test_noop_idem_0001	2026-03-02 14:16:40.084907+00	\N
test_noop_0004	2026-03-02 13:41:03.620267+00	\N
test_noop_0003	2026-03-02 13:38:29.746225+00	\N
test_noop_0002	2026-03-02 13:33:06.97466+00	\N
test_16b_booking_created_0006	2026-03-02 12:56:41.124355+00	\N
test_direct_key_0001	2026-03-02 13:20:24.575741+00	\N
test_16b_booking_created_0005	2026-03-02 12:50:37.743565+00	\N
test_16b_booking_created_0003	2026-03-02 12:31:16.217074+00	\N
phase16c_gate_test_0001	2026-03-02 15:16:58.937134+00	{"envelope_id": "phase16c_gate_test_0001", "occurred_at": "2026-03-02T15:16:58.937134+00:00"}
smoke-001	2026-03-03 06:35:11.234301+00	{"type": "BOOKING_CREATED", "actor": {"role": "system", "actor_id": "system"}, "payload": {"actor": {"role": "system", "actor_id": "system"}, "booking_id": "demo-1", "idempotency": {"request_id": "smoke-001"}}, "envelope_id": "smoke-001", "idempotency": {"request_id": "smoke-001"}, "occurred_at": "2026-03-03T06:35:11.234301Z"}
curl-001	2026-03-03 06:41:39.618309+00	{"type": "BOOKING_CREATED", "actor": {"role": "system", "actor_id": "system"}, "payload": {"actor": {"role": "system", "actor_id": "system"}, "booking_id": "demo-1", "idempotency": {"request_id": "curl-001"}}, "envelope_id": "curl-001", "idempotency": {"request_id": "curl-001"}, "occurred_at": "2026-03-03T06:41:39.618309Z"}
smoke-002	2026-03-03 06:41:39.855162+00	{"type": "BOOKING_CREATED", "actor": {"role": "system", "actor_id": "system"}, "payload": {"actor": {"role": "system", "actor_id": "system"}, "booking_id": "demo-2", "idempotency": {"request_id": "smoke-002"}}, "envelope_id": "smoke-002", "idempotency": {"request_id": "smoke-002"}, "occurred_at": "2026-03-03T06:41:39.855162Z"}
\.


--
-- Data for Name: event_kind_registry; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."event_kind_registry" ("event_kind", "version", "is_external", "is_active", "required_keys", "created_at") FROM stdin;
BOOKING_UPDATED	1	t	t	\N	2026-03-04 14:24:27.759561+00
STATE_UPSERT	1	f	t	\N	2026-03-04 15:15:51.467402+00
envelope_received	1	f	t	\N	2026-03-04 15:15:51.467402+00
envelope_applied	1	f	t	\N	2026-03-04 15:15:51.467402+00
envelope_rejected	1	f	t	\N	2026-03-04 15:15:51.467402+00
envelope_error	1	f	t	\N	2026-03-04 15:15:51.467402+00
BOOKING_CHECKED_IN	1	t	t	\N	2026-03-04 14:24:27.759561+00
BOOKING_CHECKED_OUT	1	t	t	\N	2026-03-04 14:24:27.759561+00
BOOKING_SYNC_ERROR	1	t	t	\N	2026-03-04 14:24:27.759561+00
AVAILABILITY_UPDATED	1	t	t	\N	2026-03-04 14:24:27.759561+00
RATE_UPDATED	1	t	t	\N	2026-03-04 14:24:27.759561+00
BOOKING_CREATED	1	t	t	{booking_id,tenant_id,source,reservation_ref,property_id}	2026-03-04 14:24:27.759561+00
BOOKING_CANCELED	1	t	t	{booking_id}	2026-03-04 14:24:27.759561+00
\.


--
-- Data for Name: event_kind_versions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."event_kind_versions" ("kind", "version", "required_payload_fields") FROM stdin;
BOOKING_CREATED	1	{booking_id,tenant_id,source,reservation_ref,property_id}
BOOKING_CANCELED	1	{booking_id}
\.


--
-- Data for Name: event_log_archive; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."event_log_archive" ("event_id", "envelope_id", "kind", "occurred_at", "payload_json") FROM stdin;
env_supabase_001	env_supabase_001	envelope_received	2026-03-01 00:00:00+00	{"type": "demo", "payload": {"x": 1}, "version": 1, "occurred_at": "2026-03-01T00:00:00Z"}
env_sup_http_001	env_sup_http_001	envelope_received	2026-02-28 19:52:20.459561+00	{"type": "demo", "payload": {"x": 1}, "version": 1, "occurred_at": "2026-02-28T19:52:20.459561Z"}
env_sup_http_002	env_sup_http_002	envelope_received	2026-02-28 21:09:40.197235+00	{"type": "demo", "payload": {"x": 1}, "version": 1, "occurred_at": "2026-02-28T21:09:40.197235Z"}
env_sup_http_003	env_sup_http_003	envelope_received	2026-03-01 06:38:49.801393+00	{"type": "demo", "payload": {"x": 2}, "version": 1, "occurred_at": "2026-03-01T06:38:49.801393Z"}
env_sup_http_004	env_sup_http_004	envelope_received	2026-03-01 06:55:36.878742+00	{"type": "demo", "payload": {"x": 2}, "version": 1, "occurred_at": "2026-03-01T06:55:36.878742Z"}
env_sup_http_005	env_sup_http_005	envelope_received	2026-03-01 07:01:56.445447+00	{"type": "demo", "payload": {"x": 3}, "version": 1, "occurred_at": "2026-03-01T07:01:56.445447Z"}
env_sup_http_006	env_sup_http_006	envelope_received	2026-03-01 07:12:25.982271+00	{"type": "demo", "payload": {"x": 11}, "version": 1, "occurred_at": "2026-03-01T07:12:25.982271Z"}
env_sup_http_007	env_sup_http_007	envelope_received	2026-03-01 07:18:00.070631+00	{"type": "demo", "payload": {"x": 42}, "version": 1, "occurred_at": "2026-03-01T07:18:00.070631Z"}
env_sup_http_008	env_sup_http_008	envelope_received	2026-03-01 07:23:09.942965+00	{"type": "demo", "payload": {"x": 99}, "version": 1, "occurred_at": "2026-03-01T07:23:09.942965Z"}
env_sup_http_009	env_sup_http_009	envelope_received	2026-03-01 07:34:10.70887+00	{"type": "demo", "payload": {"x": 123}, "version": 1, "occurred_at": "2026-03-01T07:34:10.708870Z"}
phase14_smoke_001	phase14_smoke_001	envelope_received	2026-03-01 08:51:15.158304+00	{"type": "BOOKING_SYNC_INGEST", "payload": {"provider": "airbnb", "property_id": "p1", "provider_payload": {"status": "confirmed", "end_date": "2026-03-05", "guest_name": "John Doe", "start_date": "2026-03-01"}, "external_booking_id": "ext123"}, "version": 1, "occurred_at": "2026-03-01T08:51:15.158304Z"}
phase14_smoke_002	phase14_smoke_002	envelope_received	2026-03-01 08:54:54.561242+00	{"type": "BOOKING_SYNC_INGEST", "payload": {"provider": "airbnb", "property_id": "p1", "provider_payload": {"status": "confirmed", "end_date": "2026-03-06", "guest_name": "Jane Doe", "start_date": "2026-03-02"}, "external_booking_id": "ext124"}, "version": 1, "occurred_at": "2026-03-01T08:54:54.561242Z"}
phase16-test-direct-0002	phase16-test-direct-0002	envelope_received	2026-03-01 17:06:32.842525+00	{"type": "booking_sync_ingest", "actor": {"role": "system", "actor_id": "test"}, "payload": {"actor": {"role": "system", "actor_id": "test"}, "provider": "airbnb", "idempotency": {"request_id": "phase16-test-direct-0002"}, "property_id": "p_001", "provider_payload": {"status": "confirmed", "end_date": "2026-04-05", "guest_name": "Alice", "start_date": "2026-04-01"}, "external_booking_id": "abc123"}, "idempotency": {"request_id": "phase16-test-direct-0002"}, "occurred_at": "2026-03-01T17:06:32.842525Z"}
phase16-test-direct-0003	phase16-test-direct-0003	envelope_received	2026-03-01 17:12:46.538873+00	{"type": "booking_sync_ingest", "actor": {"role": "system", "actor_id": "test"}, "payload": {"actor": {"role": "system", "actor_id": "test"}, "provider": "airbnb", "idempotency": {"request_id": "phase16-test-direct-0003"}, "property_id": "p_001", "provider_payload": {"status": "confirmed", "end_date": "2026-04-05", "guest_name": "Alice", "start_date": "2026-04-01"}, "external_booking_id": "abc123"}, "idempotency": {"request_id": "phase16-test-direct-0003"}, "occurred_at": "2026-03-01T17:12:46.538873Z"}
phase16-test-direct-0004	phase16-test-direct-0004	envelope_received	2026-03-02 05:08:26.131071+00	{"type": "booking_sync_ingest", "actor": {"role": "system", "actor_id": "test"}, "payload": {"actor": {"role": "system", "actor_id": "test"}, "provider": "airbnb", "idempotency": {"request_id": "phase16-test-direct-0004"}, "property_id": "p_001", "provider_payload": {"status": "confirmed", "end_date": "2026-04-05", "guest_name": "Alice", "start_date": "2026-04-01"}, "external_booking_id": "abc123"}, "idempotency": {"request_id": "phase16-test-direct-0004"}, "occurred_at": "2026-03-02T05:08:26.131071Z"}
\.


--
-- Data for Name: notifications; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."notifications" ("notification_id", "request_id", "kind", "action_type", "target", "reason", "property_id", "task_id", "created_at_ms") FROM stdin;
\.


--
-- Data for Name: outbox; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY "public"."outbox" ("outbox_id", "event_id", "event_type", "aggregate_type", "aggregate_id", "channel", "action_type", "target", "payload_json", "status", "attempt_count", "next_attempt_at_ms", "last_error", "claimed_by", "claimed_until_ms", "created_at_ms", "updated_at_ms") FROM stdin;
\.


--
-- PostgreSQL database dump complete
--

-- \unrestrict 5CXwkQDkqrKY5rB8WCOqyFfV4mvMqSLfAXlgeG0h9gh4a1gvgIK1LhS9Z8UJOH6

RESET ALL;
