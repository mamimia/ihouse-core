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
COPY "public"."event_kind_versions" ("kind", "version", "required_payload_fields") FROM stdin;
BOOKING_CREATED	1	{booking_id,tenant_id,source,reservation_ref,property_id}
BOOKING_CANCELED	1	{booking_id}
\.
