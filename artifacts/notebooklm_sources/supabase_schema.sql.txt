


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


CREATE SCHEMA IF NOT EXISTS "public";


ALTER SCHEMA "public" OWNER TO "pg_database_owner";


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE TYPE "public"."event_kind" AS ENUM (
    'BOOKING_CREATED',
    'BOOKING_UPDATED',
    'BOOKING_CANCELED',
    'BOOKING_CHECKED_IN',
    'BOOKING_CHECKED_OUT',
    'BOOKING_SYNC_ERROR',
    'AVAILABILITY_UPDATED',
    'RATE_UPDATED',
    'STATE_UPSERT',
    'envelope_received',
    'envelope_applied',
    'envelope_rejected',
    'envelope_error'
);


ALTER TYPE "public"."event_kind" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."_t3_4_internal_missing_version"() RETURNS TABLE("test_name" "text", "ok" boolean, "detail" "text")
    LANGUAGE "plpgsql"
    AS $$
declare
  v_env text := 'phase19_t3_internal_' || md5(clock_timestamp()::text || random()::text);
begin
  begin
    perform public.apply_envelope(
      jsonb_build_object('idempotency', jsonb_build_object('request_id', v_env)),
      jsonb_build_array(
        jsonb_build_object(
          'type','STATE_UPSERT',
          'occurred_at', now()::text,
          'payload', jsonb_build_object('booking_id','b_x','state_json', jsonb_build_object())
        )
      )
    );
    test_name := 'T3.4 internal_missing_version';
    ok := false;
    detail := 'unexpected success';
    return next;
  exception when others then
    test_name := 'T3.4 internal_missing_version';
    ok := (sqlerrm like '%EVENT_VERSION_REQUIRED%');
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;
end;
$$;


ALTER FUNCTION "public"."_t3_4_internal_missing_version"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."_t3_tests"() RETURNS TABLE("test_name" "text", "ok" boolean, "detail" "text")
    LANGUAGE "plpgsql"
    AS $$
declare
  v_env_ok text := 'phase19_t3_ok_' || md5(clock_timestamp()::text || random()::text);
  v_env_badver text := 'phase19_t3_badver_' || md5(clock_timestamp()::text || random()::text);
  v_env_unknown text := 'phase19_t3_unknown_' || md5(clock_timestamp()::text || random()::text);

  v_booking_id text := 'b_' || md5(clock_timestamp()::text || random()::text);
  v_tenant_id text := 't_' || md5(clock_timestamp()::text || random()::text);
  v_property_id text := 'p_' || md5(clock_timestamp()::text || random()::text);
  v_source text := 'manual_admin';
  v_res_ref text := 'r_' || md5(clock_timestamp()::text || random()::text);

  r jsonb;
begin
  -- T3.1 missing_version should default to v1 ONLY for external allowlisted kinds (BOOKING_CREATED)
  begin
    r := public.apply_envelope(
      jsonb_build_object('idempotency', jsonb_build_object('request_id', v_env_ok)),
      jsonb_build_array(
        jsonb_build_object(
          'type','BOOKING_CREATED',
          'occurred_at', now()::text,
          'payload', jsonb_build_object(
            'booking_id', v_booking_id,
            'tenant_id', v_tenant_id,
            'property_id', v_property_id,
            'source', v_source,
            'reservation_ref', v_res_ref,
            'check_in', (current_date + 10)::text,
            'check_out', (current_date + 12)::text
          )
        )
      )
    );
    test_name := 'T3.1 missing_version';
    ok := (r->>'status') = 'APPLIED';
    detail := r::text;
    return next;
  exception when others then
    test_name := 'T3.1 missing_version';
    ok := false;
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;

  -- T3.2 unsupported_version should reject deterministically
  begin
    perform public.apply_envelope(
      jsonb_build_object('idempotency', jsonb_build_object('request_id', v_env_badver)),
      jsonb_build_array(
        jsonb_build_object(
          'type','BOOKING_CREATED',
          'event_version', 999,
          'occurred_at', now()::text,
          'payload', jsonb_build_object(
            'booking_id', 'b_' || md5(clock_timestamp()::text || random()::text),
            'tenant_id', v_tenant_id,
            'property_id', v_property_id,
            'source', v_source,
            'reservation_ref', 'r_' || md5(clock_timestamp()::text || random()::text),
            'check_in', (current_date + 20)::text,
            'check_out', (current_date + 22)::text
          )
        )
      )
    );
    test_name := 'T3.2 unsupported_version';
    ok := false;
    detail := 'unexpected success';
    return next;
  exception when others then
    test_name := 'T3.2 unsupported_version';
    ok := (sqlerrm like '%UNSUPPORTED_EVENT_VERSION%');
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;

  -- T3.3 unknown_kind should reject deterministically (no enum cast failure)
  begin
    perform public.apply_envelope(
      jsonb_build_object('idempotency', jsonb_build_object('request_id', v_env_unknown)),
      jsonb_build_array(
        jsonb_build_object(
          'type','NOT_A_KIND',
          'event_version', 1,
          'occurred_at', now()::text,
          'payload', jsonb_build_object('x','y')
        )
      )
    );
    test_name := 'T3.3 unknown_kind';
    ok := false;
    detail := 'unexpected success';
    return next;
  exception when others then
    test_name := 'T3.3 unknown_kind';
    ok := (sqlerrm like '%UNKNOWN_EVENT_KIND%');
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;
end;
$$;


ALTER FUNCTION "public"."_t3_tests"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_envelope"("p_envelope" "jsonb", "p_emit" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql"
    AS $$
declare
  v_envelope_id text;
  v_now timestamptz := now();
  v_now_ms bigint := (extract(epoch from now()) * 1000)::bigint;

  e jsonb;
  v_type text;

  v_booking_id text;
  v_state_json jsonb;
  v_exists boolean;

  v_tenant_id text;
  v_source text;
  v_reservation_ref text;
  v_property_id text;

  v_check_in_text text;
  v_check_out_text text;
  v_check_in date;
  v_check_out date;
  v_overlap boolean;

  v_existing_booking_id text;

  v_current_state jsonb;
  v_state_event_id text;

  v_policy text := 'TRANSITIONAL_DEFAULT_V1';

  v_kind_text text;
  v_version int;

  v_seen_types text[] := '{}'::text[];
begin
  v_envelope_id := nullif(trim(coalesce(p_envelope->'idempotency'->>'request_id', '')), '');

  if v_envelope_id is null then
    raise exception 'envelope_id missing';
  end if;

  insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
  values (
    v_envelope_id || ':envelope_received',
    v_envelope_id,
    'envelope_received'::public.event_kind,
    v_now,
    p_envelope
  )
  on conflict (event_id) do nothing;

  if not found then
    return jsonb_build_object(
      'status','ALREADY_APPLIED',
      'envelope_id',v_envelope_id,
      'occurred_at',v_now
    );
  end if;

  if p_emit is null then
    p_emit := '[]'::jsonb;
  end if;

  if jsonb_typeof(p_emit) <> 'array' then
    raise exception 'p_emit must be array';
  end if;

  for e in
    select value from jsonb_array_elements(p_emit)
  loop
    v_type := coalesce(e->>'type','');

    if v_type = '' then
      raise exception 'event type missing';
    end if;

    if v_type = any(v_seen_types) then
      raise exception 'DUPLICATE_EVENT_KIND_IN_ENVELOPE';
    end if;
    v_seen_types := array_append(v_seen_types, v_type);

    -- Deterministic validation BEFORE any enum cast
    select out_kind, out_version
    into v_kind_text, v_version
    from public.validate_emitted_event(e, v_policy);

    insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
    values (
      v_envelope_id || ':' || v_type,
      v_envelope_id,
      v_kind_text::public.event_kind,
      coalesce((e->>'occurred_at')::timestamptz, v_now),
      e
    )
    on conflict (event_id) do nothing;

    if v_type = 'BOOKING_CREATED' then

      v_booking_id := nullif(trim(coalesce(e->'payload'->>'booking_id','')), '');
      if v_booking_id is null then
        raise exception 'BOOKING_ID_REQUIRED';
      end if;

      select true into v_exists
      from public.booking_state bs
      where bs.booking_id = v_booking_id
      for update;

      if found then
        return jsonb_build_object(
          'status','ALREADY_EXISTS',
          'envelope_id',v_envelope_id,
          'booking_id',v_booking_id,
          'occurred_at',v_now
        );
      end if;

      v_tenant_id := nullif(trim(coalesce(e->'payload'->>'tenant_id','')), '');
      v_source := nullif(trim(coalesce(e->'payload'->>'source','')), '');
      v_reservation_ref := nullif(trim(coalesce(e->'payload'->>'reservation_ref','')), '');
      v_property_id := nullif(trim(coalesce(e->'payload'->>'property_id','')), '');

      if v_tenant_id is null then raise exception 'TENANT_ID_REQUIRED'; end if;
      if v_source is null then raise exception 'SOURCE_REQUIRED'; end if;
      if v_reservation_ref is null then raise exception 'RESERVATION_REF_REQUIRED'; end if;
      if v_property_id is null then raise exception 'PROPERTY_ID_REQUIRED'; end if;

      v_existing_booking_id := null;

      select bs.booking_id
      into v_existing_booking_id
      from public.booking_state bs
      where bs.tenant_id = v_tenant_id
        and bs.source = v_source
        and bs.reservation_ref = v_reservation_ref
        and bs.property_id = v_property_id
      for update;

      if found then
        return jsonb_build_object(
          'status','ALREADY_EXISTS_BUSINESS',
          'envelope_id',v_envelope_id,
          'booking_id',v_existing_booking_id,
          'occurred_at',v_now
        );
      end if;

      v_check_in_text := nullif(trim(coalesce(e->'payload'->>'check_in','')), '');
      v_check_out_text := nullif(trim(coalesce(e->'payload'->>'check_out','')), '');

      v_check_in := null;
      v_check_out := null;

      if (v_check_in_text is not null) or (v_check_out_text is not null) then
        if v_check_in_text is null then raise exception 'CHECK_IN_REQUIRED_WHEN_CHECK_OUT_PRESENT'; end if;
        if v_check_out_text is null then raise exception 'CHECK_OUT_REQUIRED_WHEN_CHECK_IN_PRESENT'; end if;

        begin
          v_check_in := v_check_in_text::date;
        exception when others then
          raise exception 'CHECK_IN_INVALID_DATE';
        end;

        begin
          v_check_out := v_check_out_text::date;
        exception when others then
          raise exception 'CHECK_OUT_INVALID_DATE';
        end;

        if v_check_out <= v_check_in then
          raise exception 'CHECK_OUT_MUST_BE_AFTER_CHECK_IN';
        end if;

        select true into v_overlap
        from public.booking_state bs
        where bs.tenant_id = v_tenant_id
          and bs.property_id = v_property_id
          and (bs.status is null or bs.status <> 'canceled')
          and bs.check_in is not null
          and bs.check_out is not null
          and bs.check_in < v_check_out
          and v_check_in < bs.check_out
        limit 1;

        if found then
          raise exception 'OVERLAP_NOT_ALLOWED';
        end if;
      end if;

      v_state_json := jsonb_build_object(
        'booking_id', v_booking_id,
        'source_event_id', v_envelope_id || ':BOOKING_CREATED',
        'booking', e->'payload'
      );

      insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
      values (
        v_envelope_id || ':STATE_UPSERT',
        v_envelope_id,
        'STATE_UPSERT'::public.event_kind,
        v_now,
        jsonb_build_object(
          'type','STATE_UPSERT',
          'occurred_at', v_now::text,
          'payload', jsonb_build_object(
            'booking_id', v_booking_id,
            'state_json', v_state_json
          )
        )
      )
      on conflict (event_id) do nothing;

      insert into public.booking_state(
        booking_id, version, state_json, updated_at_ms, last_event_id, last_envelope_id,
        tenant_id, source, reservation_ref, property_id,
        check_in, check_out, status
      )
      values (
        v_booking_id, 1, v_state_json, v_now_ms, v_envelope_id || ':STATE_UPSERT', v_envelope_id,
        v_tenant_id, v_source, v_reservation_ref, v_property_id,
        v_check_in, v_check_out, 'active'
      );

    elsif v_type = 'BOOKING_CANCELED' then

      v_booking_id := nullif(trim(coalesce(e->'payload'->>'booking_id','')), '');
      if v_booking_id is null then
        raise exception 'BOOKING_ID_REQUIRED';
      end if;

      v_current_state := null;

      select bs.state_json
      into v_current_state
      from public.booking_state bs
      where bs.booking_id = v_booking_id
      for update;

      if not found then
        raise exception 'BOOKING_NOT_FOUND';
      end if;

      v_state_event_id := v_envelope_id || ':STATE_UPSERT:BOOKING_CANCELED';

      v_state_json :=
        jsonb_set(
          coalesce(v_current_state, '{}'::jsonb),
          '{source_event_id}',
          to_jsonb(v_envelope_id || ':BOOKING_CANCELED'),
          true
        );

      insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
      values (
        v_state_event_id,
        v_envelope_id,
        'STATE_UPSERT'::public.event_kind,
        v_now,
        jsonb_build_object(
          'type','STATE_UPSERT',
          'occurred_at', v_now::text,
          'payload', jsonb_build_object(
            'booking_id', v_booking_id,
            'state_json', v_state_json
          )
        )
      )
      on conflict (event_id) do nothing;

      update public.booking_state
      set
        status = 'canceled',
        state_json = v_state_json,
        version = version + 1,
        updated_at_ms = v_now_ms,
        last_event_id = v_state_event_id,
        last_envelope_id = v_envelope_id
      where booking_id = v_booking_id;

    end if;
  end loop;

  return jsonb_build_object(
    'status','APPLIED',
    'envelope_id',v_envelope_id,
    'occurred_at',v_now,
    'state_upsert_found', true
  );
end;
$$;


ALTER FUNCTION "public"."apply_envelope"("p_envelope" "jsonb", "p_emit" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb" DEFAULT '[]'::"jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
declare
  v_event_id text;
  v_type text;
  v_kind public.event_kind;
  v_occurred_at timestamptz;

  v_em jsonb;
  v_emitted jsonb;
  v_em_kind public.event_kind;

  v_now_ms bigint;

  v_booking_id text;
  v_state_json jsonb;
  v_expected_last text;
  v_current_last text;
  v_row_exists boolean;

begin
  if p_event is null then
    raise exception 'EVENT_REQUIRED';
  end if;

  v_event_id := coalesce(p_event->>'event_id', '');
  v_type := coalesce(p_event->>'type', '');
  v_occurred_at := nullif(p_event->>'occurred_at','')::timestamptz;

  if v_event_id = '' then raise exception 'EVENT_ID_REQUIRED'; end if;
  if v_type = '' then raise exception 'EVENT_TYPE_REQUIRED'; end if;
  if v_occurred_at is null then raise exception 'EVENT_OCCURRED_AT_REQUIRED'; end if;

  begin
    v_kind := v_type::public.event_kind;
  exception when others then
    raise exception 'EVENT_KIND_INVALID';
  end;

  if p_emitted is null then
    v_emitted := '[]'::jsonb;
  else
    v_emitted := p_emitted;
  end if;

  if jsonb_typeof(v_emitted) <> 'array' then
    raise exception 'EMITTED_MUST_BE_ARRAY';
  end if;

  v_now_ms := (extract(epoch from now()) * 1000)::bigint;

  begin
    insert into public.event_log(event_id, kind, occurred_at, payload_json)
    values (v_event_id, v_kind, v_occurred_at, p_event);
  exception
    when unique_violation then
      return jsonb_build_object('status','DUPLICATE','event_id', v_event_id);
  end;

  for v_em in
    select value from jsonb_array_elements(v_emitted)
  loop
    if jsonb_typeof(v_em) <> 'object' then
      raise exception 'EMITTED_ITEM_MUST_BE_OBJECT';
    end if;

    if coalesce(v_em->>'event_id','') = '' then
      raise exception 'EMITTED_EVENT_ID_REQUIRED';
    end if;

    if coalesce(v_em->>'type','') = '' then
      raise exception 'EMITTED_TYPE_REQUIRED';
    end if;

    if nullif(v_em->>'occurred_at','') is null then
      raise exception 'EMITTED_OCCURRED_AT_REQUIRED';
    end if;

    begin
      v_em_kind := (v_em->>'type')::public.event_kind;
    exception when others then
      raise exception 'EMITTED_KIND_INVALID';
    end;

    insert into public.event_log(event_id, kind, occurred_at, payload_json)
    values (
      v_em->>'event_id',
      v_em_kind,
      (v_em->>'occurred_at')::timestamptz,
      v_em
    );

    if (v_em->>'type') = 'STATE_UPSERT' then
      v_booking_id := coalesce(v_em->'payload'->>'booking_id','');
      v_state_json := v_em->'payload'->'state_json';
      v_expected_last := nullif(v_em->'payload'->>'expected_last_event_id','');

      if v_booking_id = '' then raise exception 'STATE_UPSERT_BOOKING_ID_REQUIRED'; end if;
      if v_state_json is null then raise exception 'STATE_UPSERT_STATE_JSON_REQUIRED'; end if;

      v_row_exists := false;
      v_current_last := null;

      select bs.last_event_id
      into v_current_last
      from public.booking_state bs
      where bs.booking_id = v_booking_id
      for update;

      v_row_exists := found;

      if v_row_exists then
        if v_expected_last is null then
          raise exception 'EXPECTED_LAST_REQUIRED';
        end if;

        if v_current_last is distinct from v_expected_last then
          raise exception 'EXPECTED_LAST_MISMATCH';
        end if;

        update public.booking_state
        set
          state_json = v_state_json,
          version = version + 1,
          updated_at_ms = v_now_ms,
          last_event_id = (v_em->>'event_id')
        where booking_id = v_booking_id;

      else
        if v_expected_last is not null then
          raise exception 'EXPECTED_LAST_MUST_BE_NULL_ON_CREATE';
        end if;

        insert into public.booking_state(booking_id, version, state_json, updated_at_ms, last_event_id)
        values (v_booking_id, 1, v_state_json, v_now_ms, (v_em->>'event_id'));
      end if;
    end if;
  end loop;

  return jsonb_build_object('status','APPLIED','event_id', v_event_id);
end;
$$;


ALTER FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."read_booking_by_business_key"("p_tenant_id" "text", "p_source" "text", "p_reservation_ref" "text", "p_property_id" "text") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    AS $$
  select jsonb_build_object(
    'booking_id', bs.booking_id,
    'version', bs.version,
    'tenant_id', bs.tenant_id,
    'source', bs.source,
    'reservation_ref', bs.reservation_ref,
    'property_id', bs.property_id,
    'check_in', bs.check_in,
    'check_out', bs.check_out,
    'updated_at_ms', bs.updated_at_ms,
    'last_event_id', bs.last_event_id,
    'last_envelope_id', bs.last_envelope_id,
    'state_json', bs.state_json
  )
  from public.booking_state bs
  where bs.tenant_id = p_tenant_id
    and bs.source = p_source
    and bs.reservation_ref = p_reservation_ref
    and bs.property_id = p_property_id;
$$;


ALTER FUNCTION "public"."read_booking_by_business_key"("p_tenant_id" "text", "p_source" "text", "p_reservation_ref" "text", "p_property_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."read_booking_by_id"("p_booking_id" "text") RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    AS $$
  select jsonb_build_object(
    'booking_id', bs.booking_id,
    'version', bs.version,
    'tenant_id', bs.tenant_id,
    'source', bs.source,
    'reservation_ref', bs.reservation_ref,
    'property_id', bs.property_id,
    'check_in', bs.check_in,
    'check_out', bs.check_out,
    'updated_at_ms', bs.updated_at_ms,
    'last_event_id', bs.last_event_id,
    'last_envelope_id', bs.last_envelope_id,
    'state_json', bs.state_json
  )
  from public.booking_state bs
  where bs.booking_id = p_booking_id;
$$;


ALTER FUNCTION "public"."read_booking_by_id"("p_booking_id" "text") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."run_t3"() RETURNS TABLE("test_name" "text", "ok" boolean, "detail" "text")
    LANGUAGE "plpgsql"
    AS $$
declare
  v_env jsonb;
  v_emit jsonb;
  v_booking_id text;
  v_res jsonb;
  v_err text;
  v_envelope_id text;
begin
  -- T3.1 missing_version => should pass (external allowlist defaults to v1)
  begin
    v_booking_id := 't3_booking_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12);
    v_envelope_id := 'phase19_t3_ok_' || substr(md5(random()::text || clock_timestamp()::text), 1, 24);

    v_env := jsonb_build_object('idempotency', jsonb_build_object('request_id', v_envelope_id));
    v_emit := jsonb_build_array(
      jsonb_build_object(
        'type','BOOKING_CREATED',
        'occurred_at', now()::text,
        'payload', jsonb_build_object(
          'booking_id', v_booking_id,
          'tenant_id','t3_tenant',
          'source','t3_source',
          'reservation_ref','t3_ref_' || v_booking_id,
          'property_id','t3_property'
        )
      )
    );

    v_res := public.apply_envelope(v_env, v_emit);
    test_name := 'T3.1 missing_version';
    ok := (v_res->>'status' = 'APPLIED');
    detail := v_res::text;
    return next;
  exception when others then
    test_name := 'T3.1 missing_version';
    ok := false;
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;

  -- T3.2 unsupported_version => should reject with UNSUPPORTED_EVENT_VERSION
  begin
    v_booking_id := 't3_booking_' || substr(md5(random()::text || clock_timestamp()::text), 1, 12);
    v_envelope_id := 'phase19_t3_badver_' || substr(md5(random()::text || clock_timestamp()::text), 1, 24);

    v_env := jsonb_build_object('idempotency', jsonb_build_object('request_id', v_envelope_id));
    v_emit := jsonb_build_array(
      jsonb_build_object(
        'type','BOOKING_CREATED',
        'event_version', 999,
        'occurred_at', now()::text,
        'payload', jsonb_build_object(
          'booking_id', v_booking_id,
          'tenant_id','t3_tenant',
          'source','t3_source',
          'reservation_ref','t3_ref_' || v_booking_id,
          'property_id','t3_property'
        )
      )
    );

    v_res := public.apply_envelope(v_env, v_emit);
    test_name := 'T3.2 unsupported_version';
    ok := false;
    detail := 'unexpected success: ' || v_res::text;
    return next;
  exception when others then
    test_name := 'T3.2 unsupported_version';
    ok := (sqlerrm = 'UNSUPPORTED_EVENT_VERSION');
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;

  -- T3.3 unknown_kind => should reject with UNKNOWN_EVENT_KIND (not 22P02)
  begin
    v_envelope_id := 'phase19_t3_unknown_' || substr(md5(random()::text || clock_timestamp()::text), 1, 24);

    v_env := jsonb_build_object('idempotency', jsonb_build_object('request_id', v_envelope_id));
    v_emit := jsonb_build_array(
      jsonb_build_object(
        'type','NOT_A_KIND',
        'event_version', 1,
        'occurred_at', now()::text,
        'payload', jsonb_build_object('x',1)
      )
    );

    v_res := public.apply_envelope(v_env, v_emit);
    test_name := 'T3.3 unknown_kind';
    ok := false;
    detail := 'unexpected success: ' || v_res::text;
    return next;
  exception when others then
    test_name := 'T3.3 unknown_kind';
    ok := (sqlerrm = 'UNKNOWN_EVENT_KIND');
    detail := sqlstate || ' ' || sqlerrm;
    return next;
  end;
end;
$$;


ALTER FUNCTION "public"."run_t3"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."validate_emitted_event"("p_event" "jsonb", "p_policy" "text") RETURNS TABLE("out_kind" "text", "out_version" integer)
    LANGUAGE "plpgsql"
    AS $$
declare
  v_type_text text;
  v_ver_text text;
  v_version int;
  v_is_external boolean;
  v_is_active boolean;
  v_required_keys text[];
  k text;
  v_enum_exists boolean;
begin
  v_type_text := nullif(trim(coalesce(p_event->>'type','')), '');
  if v_type_text is null then
    raise exception 'EVENT_TYPE_REQUIRED';
  end if;

  select exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    where t.typname = 'event_kind'
      and e.enumlabel = v_type_text
  )
  into v_enum_exists;

  if not v_enum_exists then
    raise exception 'UNKNOWN_EVENT_KIND';
  end if;

  v_ver_text := nullif(trim(coalesce(p_event->>'event_version','')), '');

  -- Preload registry row for allowlist decision using default version 1
  select r.is_external, r.is_active, r.required_keys
  into v_is_external, v_is_active, v_required_keys
  from public.event_kind_registry r
  where r.event_kind = v_type_text::public.event_kind
    and r.version = 1;

  if not found then
    -- No registry row at all means the kind is not onboarded
    raise exception 'UNSUPPORTED_EVENT_VERSION';
  end if;

  if v_ver_text is null then
    if p_policy = 'STRICT' then
      raise exception 'EVENT_VERSION_REQUIRED';
    end if;

    if v_is_external then
      v_version := 1;
    else
      raise exception 'EVENT_VERSION_REQUIRED';
    end if;
  else
    begin
      v_version := v_ver_text::int;
    exception when others then
      raise exception 'INVALID_EVENT_VERSION';
    end;
  end if;

  -- Validate that kind+version is supported and active
  select r.is_external, r.is_active, r.required_keys
  into v_is_external, v_is_active, v_required_keys
  from public.event_kind_registry r
  where r.event_kind = v_type_text::public.event_kind
    and r.version = v_version;

  if not found or not v_is_active then
    raise exception 'UNSUPPORTED_EVENT_VERSION';
  end if;

  foreach k in array coalesce(v_required_keys, '{}'::text[])
  loop
    if not (coalesce(p_event->'payload','{}'::jsonb) ? k) then
      raise exception 'INVALID_PAYLOAD';
    end if;
  end loop;

  out_kind := v_type_text;
  out_version := v_version;
  return next;
end;
$$;


ALTER FUNCTION "public"."validate_emitted_event"("p_event" "jsonb", "p_policy" "text") OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."booking_overrides" (
    "override_id" "text" NOT NULL,
    "booking_id" "text" NOT NULL,
    "property_id" "text" NOT NULL,
    "status" "text" NOT NULL,
    "required_approver_role" "text",
    "conflicts_json" "text" NOT NULL,
    "request_id" "text",
    "created_at_ms" bigint NOT NULL,
    "updated_at_ms" bigint NOT NULL
);


ALTER TABLE "public"."booking_overrides" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."booking_state" (
    "booking_id" "text" NOT NULL,
    "version" integer NOT NULL,
    "state_json" "jsonb" NOT NULL,
    "updated_at_ms" bigint NOT NULL,
    "last_event_id" "text",
    "last_envelope_id" "text",
    "tenant_id" "text",
    "source" "text",
    "reservation_ref" "text",
    "property_id" "text",
    "check_in" "date",
    "check_out" "date",
    "status" "text"
);


ALTER TABLE "public"."booking_state" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."bookings" (
    "booking_id" "text" NOT NULL,
    "property_id" "text" NOT NULL,
    "external_ref" "text",
    "start_date" "text" NOT NULL,
    "end_date" "text" NOT NULL,
    "status" "text" NOT NULL,
    "guest_name" "text",
    "created_at_ms" bigint NOT NULL,
    "updated_at_ms" bigint NOT NULL
);


ALTER TABLE "public"."bookings" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."conflict_tasks" (
    "conflict_task_id" "text" NOT NULL,
    "booking_id" "text" NOT NULL,
    "property_id" "text" NOT NULL,
    "status" "text" NOT NULL,
    "priority" "text",
    "conflicts_json" "text" NOT NULL,
    "request_id" "text",
    "created_at_ms" bigint NOT NULL,
    "updated_at_ms" bigint NOT NULL
);


ALTER TABLE "public"."conflict_tasks" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."envelope_gate" (
    "envelope_id" "text" NOT NULL,
    "received_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "payload_json" "jsonb"
);


ALTER TABLE "public"."envelope_gate" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_kind_registry" (
    "event_kind" "public"."event_kind" NOT NULL,
    "version" integer NOT NULL,
    "is_external" boolean DEFAULT false NOT NULL,
    "is_active" boolean DEFAULT true NOT NULL,
    "required_keys" "text"[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."event_kind_registry" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_kind_versions" (
    "kind" "public"."event_kind" NOT NULL,
    "version" integer NOT NULL,
    "required_payload_fields" "text"[] DEFAULT '{}'::"text"[] NOT NULL
);


ALTER TABLE "public"."event_kind_versions" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_log" (
    "event_id" "text" NOT NULL,
    "kind" "public"."event_kind" NOT NULL,
    "occurred_at" timestamp with time zone NOT NULL,
    "payload_json" "jsonb" NOT NULL,
    "envelope_id" "text"
);


ALTER TABLE "public"."event_log" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_log_archive" (
    "event_id" "text" NOT NULL,
    "envelope_id" "text" NOT NULL,
    "kind" "text" NOT NULL,
    "occurred_at" timestamp with time zone NOT NULL,
    "payload_json" "jsonb" NOT NULL
);


ALTER TABLE "public"."event_log_archive" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "notification_id" "text" NOT NULL,
    "request_id" "text",
    "kind" "text" NOT NULL,
    "action_type" "text",
    "target" "text",
    "reason" "text",
    "property_id" "text",
    "task_id" "text",
    "created_at_ms" bigint NOT NULL
);


ALTER TABLE "public"."notifications" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."outbox" (
    "outbox_id" "text" NOT NULL,
    "event_id" "text" NOT NULL,
    "event_type" "text" NOT NULL,
    "aggregate_type" "text",
    "aggregate_id" "text",
    "channel" "text" NOT NULL,
    "action_type" "text" NOT NULL,
    "target" "text",
    "payload_json" "text" NOT NULL,
    "status" "text" NOT NULL,
    "attempt_count" integer DEFAULT 0 NOT NULL,
    "next_attempt_at_ms" bigint DEFAULT 0 NOT NULL,
    "last_error" "text",
    "claimed_by" "text",
    "claimed_until_ms" bigint DEFAULT 0 NOT NULL,
    "created_at_ms" bigint NOT NULL,
    "updated_at_ms" bigint NOT NULL
);


ALTER TABLE "public"."outbox" OWNER TO "postgres";


ALTER TABLE ONLY "public"."booking_overrides"
    ADD CONSTRAINT "booking_overrides_pkey" PRIMARY KEY ("override_id");



ALTER TABLE ONLY "public"."booking_state"
    ADD CONSTRAINT "booking_state_pkey" PRIMARY KEY ("booking_id");



ALTER TABLE ONLY "public"."bookings"
    ADD CONSTRAINT "bookings_pkey" PRIMARY KEY ("booking_id");



ALTER TABLE ONLY "public"."conflict_tasks"
    ADD CONSTRAINT "conflict_tasks_pkey" PRIMARY KEY ("conflict_task_id");



ALTER TABLE ONLY "public"."envelope_gate"
    ADD CONSTRAINT "envelope_gate_pkey" PRIMARY KEY ("envelope_id");



ALTER TABLE ONLY "public"."event_kind_registry"
    ADD CONSTRAINT "event_kind_registry_pkey" PRIMARY KEY ("event_kind", "version");



ALTER TABLE ONLY "public"."event_kind_versions"
    ADD CONSTRAINT "event_kind_versions_pkey" PRIMARY KEY ("kind", "version");



ALTER TABLE ONLY "public"."event_log"
    ADD CONSTRAINT "event_log_pkey" PRIMARY KEY ("event_id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_pkey" PRIMARY KEY ("notification_id");



ALTER TABLE ONLY "public"."outbox"
    ADD CONSTRAINT "outbox_pkey" PRIMARY KEY ("outbox_id");



CREATE UNIQUE INDEX "booking_state_business_key_uq" ON "public"."booking_state" USING "btree" ("tenant_id", "source", "reservation_ref", "property_id") WHERE (("tenant_id" IS NOT NULL) AND ("source" IS NOT NULL) AND ("reservation_ref" IS NOT NULL) AND ("property_id" IS NOT NULL));



CREATE INDEX "event_kind_registry_external_active_idx" ON "public"."event_kind_registry" USING "btree" ("is_external", "is_active", "event_kind", "version");



CREATE INDEX "event_log_envelope_id_idx" ON "public"."event_log" USING "btree" ("envelope_id");



CREATE INDEX "idx_outbox_claimed_until" ON "public"."outbox" USING "btree" ("claimed_until_ms");



CREATE INDEX "idx_outbox_status_due_claim" ON "public"."outbox" USING "btree" ("status", "next_attempt_at_ms", "claimed_until_ms");



CREATE INDEX "idx_outbox_status_next_attempt" ON "public"."outbox" USING "btree" ("status", "next_attempt_at_ms");



CREATE INDEX "ix_booking_state_active_dates" ON "public"."booking_state" USING "btree" ("tenant_id", "property_id", "check_in", "check_out") WHERE (("status" = 'active'::"text") AND ("check_in" IS NOT NULL) AND ("check_out" IS NOT NULL));



CREATE INDEX "ix_booking_state_dates" ON "public"."booking_state" USING "btree" ("tenant_id", "property_id", "check_in", "check_out") WHERE (("check_in" IS NOT NULL) AND ("check_out" IS NOT NULL));



CREATE INDEX "ix_booking_state_last_event" ON "public"."booking_state" USING "btree" ("last_event_id");



CREATE INDEX "ix_booking_state_not_canceled_dates" ON "public"."booking_state" USING "btree" ("tenant_id", "property_id", "check_in", "check_out") WHERE ((("status" IS NULL) OR ("status" <> 'canceled'::"text")) AND ("check_in" IS NOT NULL) AND ("check_out" IS NOT NULL));



CREATE INDEX "ix_booking_state_updated" ON "public"."booking_state" USING "btree" ("updated_at_ms" DESC);



CREATE UNIQUE INDEX "ux_outbox_event_action" ON "public"."outbox" USING "btree" ("event_id", "channel", "action_type", COALESCE("target", ''::"text"));



ALTER TABLE ONLY "public"."booking_state"
    ADD CONSTRAINT "booking_state_last_event_fk" FOREIGN KEY ("last_event_id") REFERENCES "public"."event_log"("event_id") ON UPDATE RESTRICT ON DELETE RESTRICT;



GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";



GRANT ALL ON FUNCTION "public"."_t3_4_internal_missing_version"() TO "anon";
GRANT ALL ON FUNCTION "public"."_t3_4_internal_missing_version"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."_t3_4_internal_missing_version"() TO "service_role";



GRANT ALL ON FUNCTION "public"."_t3_tests"() TO "anon";
GRANT ALL ON FUNCTION "public"."_t3_tests"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."_t3_tests"() TO "service_role";



GRANT ALL ON FUNCTION "public"."apply_envelope"("p_envelope" "jsonb", "p_emit" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_envelope"("p_envelope" "jsonb", "p_emit" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_envelope"("p_envelope" "jsonb", "p_emit" "jsonb") TO "service_role";



REVOKE ALL ON FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."apply_event"("p_event" "jsonb", "p_emitted" "jsonb") TO "service_role";



GRANT ALL ON FUNCTION "public"."read_booking_by_business_key"("p_tenant_id" "text", "p_source" "text", "p_reservation_ref" "text", "p_property_id" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."read_booking_by_business_key"("p_tenant_id" "text", "p_source" "text", "p_reservation_ref" "text", "p_property_id" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."read_booking_by_business_key"("p_tenant_id" "text", "p_source" "text", "p_reservation_ref" "text", "p_property_id" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."read_booking_by_id"("p_booking_id" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."read_booking_by_id"("p_booking_id" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."read_booking_by_id"("p_booking_id" "text") TO "service_role";



GRANT ALL ON FUNCTION "public"."run_t3"() TO "anon";
GRANT ALL ON FUNCTION "public"."run_t3"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."run_t3"() TO "service_role";



GRANT ALL ON FUNCTION "public"."validate_emitted_event"("p_event" "jsonb", "p_policy" "text") TO "anon";
GRANT ALL ON FUNCTION "public"."validate_emitted_event"("p_event" "jsonb", "p_policy" "text") TO "authenticated";
GRANT ALL ON FUNCTION "public"."validate_emitted_event"("p_event" "jsonb", "p_policy" "text") TO "service_role";



GRANT ALL ON TABLE "public"."booking_overrides" TO "anon";
GRANT ALL ON TABLE "public"."booking_overrides" TO "authenticated";
GRANT ALL ON TABLE "public"."booking_overrides" TO "service_role";



GRANT ALL ON TABLE "public"."booking_state" TO "anon";
GRANT ALL ON TABLE "public"."booking_state" TO "authenticated";
GRANT ALL ON TABLE "public"."booking_state" TO "service_role";



GRANT ALL ON TABLE "public"."bookings" TO "anon";
GRANT ALL ON TABLE "public"."bookings" TO "authenticated";
GRANT ALL ON TABLE "public"."bookings" TO "service_role";



GRANT ALL ON TABLE "public"."conflict_tasks" TO "anon";
GRANT ALL ON TABLE "public"."conflict_tasks" TO "authenticated";
GRANT ALL ON TABLE "public"."conflict_tasks" TO "service_role";



GRANT ALL ON TABLE "public"."envelope_gate" TO "anon";
GRANT ALL ON TABLE "public"."envelope_gate" TO "authenticated";
GRANT ALL ON TABLE "public"."envelope_gate" TO "service_role";



GRANT ALL ON TABLE "public"."event_kind_registry" TO "anon";
GRANT ALL ON TABLE "public"."event_kind_registry" TO "authenticated";
GRANT ALL ON TABLE "public"."event_kind_registry" TO "service_role";



GRANT ALL ON TABLE "public"."event_kind_versions" TO "anon";
GRANT ALL ON TABLE "public"."event_kind_versions" TO "authenticated";
GRANT ALL ON TABLE "public"."event_kind_versions" TO "service_role";



GRANT ALL ON TABLE "public"."event_log" TO "anon";
GRANT ALL ON TABLE "public"."event_log" TO "authenticated";
GRANT ALL ON TABLE "public"."event_log" TO "service_role";



GRANT ALL ON TABLE "public"."event_log_archive" TO "anon";
GRANT ALL ON TABLE "public"."event_log_archive" TO "authenticated";
GRANT ALL ON TABLE "public"."event_log_archive" TO "service_role";



GRANT ALL ON TABLE "public"."notifications" TO "anon";
GRANT ALL ON TABLE "public"."notifications" TO "authenticated";
GRANT ALL ON TABLE "public"."notifications" TO "service_role";



GRANT ALL ON TABLE "public"."outbox" TO "anon";
GRANT ALL ON TABLE "public"."outbox" TO "authenticated";
GRANT ALL ON TABLE "public"."outbox" TO "service_role";



ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";







