-- Phase 50: Step 2 — apply_envelope with BOOKING_AMENDED branch + ACTIVE-state guard
-- Run AFTER Step 1 in Supabase SQL Editor
-- Project: reykggmlcehswrxjviup

CREATE OR REPLACE FUNCTION public.apply_envelope(p_envelope jsonb, p_emit jsonb)
RETURNS jsonb
LANGUAGE plpgsql
AS $$
DECLARE
  v_request_id        text;
  v_envelope_id       text;
  v_type              text;
  v_tenant_id         text;
  v_now               timestamptz;
  v_now_ms            bigint;
  v_booking_id        text;
  v_current_state     jsonb;
  v_current_status    text;
  v_state_json        jsonb;
  v_state_event_id    text;
  v_kind_text         text;
  v_source            text;
  v_reservation_ref   text;
  v_property_id       text;
  v_check_in          date;
  v_check_out         date;
  v_check_in_text     text;
  v_check_out_text    text;
  v_overlap           boolean := false;
  e                   jsonb;
BEGIN
  v_request_id := nullif(trim(coalesce(p_envelope->'idempotency'->>'request_id','')), '');
  if v_request_id is null then raise exception 'REQUEST_ID_REQUIRED'; end if;

  if exists (
    select 1 from public.event_log
    where event_id = v_request_id
  ) then
    return jsonb_build_object('status','ALREADY_APPLIED','envelope_id',v_request_id);
  end if;

  v_now    := now();
  v_now_ms := extract(epoch from v_now)::bigint * 1000;
  v_type   := nullif(trim(coalesce(p_envelope->>'type','')), '');
  v_tenant_id := nullif(trim(coalesce(p_envelope->>'tenant_id', p_envelope->'payload'->>'tenant_id','')), '');

  if v_tenant_id is null then raise exception 'TENANT_ID_REQUIRED'; end if;

  v_kind_text := v_type;
  begin
    perform v_kind_text::public.event_kind;
  exception when invalid_text_representation then
    raise exception 'UNKNOWN_EVENT_KIND:%', v_type;
  end;

  v_envelope_id := coalesce(v_request_id, gen_random_uuid()::text);

  insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
  values (
    v_envelope_id,
    v_envelope_id,
    'envelope_received'::public.event_kind,
    v_now,
    jsonb_build_object(
      'type', 'envelope_received',
      'occurred_at', v_now::text,
      'payload', jsonb_build_object('envelope', p_envelope, 'emit', p_emit)
    )
  )
  on conflict (event_id) do nothing;

  FOR e IN SELECT jsonb_array_elements(p_emit)
  LOOP
    v_type := nullif(trim(coalesce(e->>'type','')), '');

    begin
      perform v_type::public.event_kind;
    exception when invalid_text_representation then
      raise exception 'UNKNOWN_EVENT_KIND:%', v_type;
    end;

    v_kind_text := v_type;

    -- ================================================================
    -- BOOKING_CREATED
    -- ================================================================
    if v_type = 'BOOKING_CREATED' then

      v_booking_id := nullif(trim(coalesce(
        e->'payload'->>'booking_id',
        (e->'payload'->>'source') || '_' || (e->'payload'->>'reservation_id'),
        ''
      )), '');
      if v_booking_id is null then raise exception 'BOOKING_ID_REQUIRED'; end if;

      if exists (select 1 from public.booking_state where booking_id = v_booking_id) then
        return jsonb_build_object('status','ALREADY_EXISTS_BUSINESS','envelope_id',v_envelope_id,'booking_id',v_booking_id);
      end if;

      v_source          := nullif(trim(coalesce(e->'payload'->>'source', p_envelope->'payload'->>'provider','')), '');
      v_reservation_ref := nullif(trim(coalesce(e->'payload'->>'reservation_id','')), '');
      v_property_id     := nullif(trim(coalesce(e->'payload'->>'property_id', p_envelope->'payload'->>'property_id','')), '');

      v_check_in_text  := nullif(trim(coalesce(e->'payload'->'provider_payload'->>'check_in', e->'payload'->>'check_in','')), '');
      v_check_out_text := nullif(trim(coalesce(e->'payload'->'provider_payload'->>'check_out', e->'payload'->>'check_out','')), '');

      v_check_in  := null;
      v_check_out := null;

      if (v_check_in_text is not null) or (v_check_out_text is not null) then
        if v_check_in_text is null then raise exception 'CHECK_IN_REQUIRED_WHEN_CHECK_OUT_PRESENT'; end if;
        if v_check_out_text is null then raise exception 'CHECK_OUT_REQUIRED_WHEN_CHECK_IN_PRESENT'; end if;

        begin v_check_in := v_check_in_text::date;
        exception when others then raise exception 'CHECK_IN_INVALID_DATE'; end;

        begin v_check_out := v_check_out_text::date;
        exception when others then raise exception 'CHECK_OUT_INVALID_DATE'; end;

        if v_check_out <= v_check_in then raise exception 'CHECK_OUT_MUST_BE_AFTER_CHECK_IN'; end if;

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

        if found then raise exception 'OVERLAP_NOT_ALLOWED'; end if;
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
          'payload', jsonb_build_object('booking_id', v_booking_id, 'state_json', v_state_json)
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

    -- ================================================================
    -- BOOKING_CANCELED
    -- ================================================================
    elsif v_type = 'BOOKING_CANCELED' then

      v_booking_id := nullif(trim(coalesce(e->'payload'->>'booking_id','')), '');
      if v_booking_id is null then raise exception 'BOOKING_ID_REQUIRED'; end if;

      v_current_state := null;

      select bs.state_json
      into v_current_state
      from public.booking_state bs
      where bs.booking_id = v_booking_id
      for update;

      if not found then raise exception 'BOOKING_NOT_FOUND'; end if;

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
          'payload', jsonb_build_object('booking_id', v_booking_id, 'state_json', v_state_json)
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

    -- ================================================================
    -- BOOKING_AMENDED
    -- ================================================================
    elsif v_type = 'BOOKING_AMENDED' then

      -- 1. Extract booking_id
      v_booking_id := nullif(trim(coalesce(e->'payload'->>'booking_id','')), '');
      if v_booking_id is null then raise exception 'BOOKING_ID_REQUIRED'; end if;

      -- 2. Load current state with row-level lock
      select bs.state_json, bs.status
      into v_current_state, v_current_status
      from public.booking_state bs
      where bs.booking_id = v_booking_id
      for update;

      if not found then raise exception 'BOOKING_NOT_FOUND'; end if;

      -- 3. ACTIVE-state lifecycle guard
      --    A canceled booking cannot be amended.
      if v_current_status = 'canceled' then
        raise exception 'AMENDMENT_ON_CANCELED_BOOKING';
      end if;

      -- 4. Extract new dates (optional — only update if provided)
      v_check_in_text  := nullif(trim(coalesce(e->'payload'->>'new_check_in','')), '');
      v_check_out_text := nullif(trim(coalesce(e->'payload'->>'new_check_out','')), '');

      v_check_in  := null;
      v_check_out := null;

      if v_check_in_text is not null then
        begin v_check_in := v_check_in_text::date;
        exception when others then raise exception 'AMENDMENT_CHECK_IN_INVALID_DATE'; end;
      end if;

      if v_check_out_text is not null then
        begin v_check_out := v_check_out_text::date;
        exception when others then raise exception 'AMENDMENT_CHECK_OUT_INVALID_DATE'; end;
      end if;

      if v_check_in is not null and v_check_out is not null then
        if v_check_out <= v_check_in then
          raise exception 'AMENDMENT_CHECK_OUT_MUST_BE_AFTER_CHECK_IN';
        end if;
      end if;

      -- 5. Build updated state_json — embed amendment payload
      v_state_event_id := v_envelope_id || ':STATE_UPSERT:BOOKING_AMENDED';

      v_state_json :=
        jsonb_set(
          coalesce(v_current_state, '{}'::jsonb),
          '{source_event_id}',
          to_jsonb(v_envelope_id || ':BOOKING_AMENDED'),
          true
        );

      v_state_json := v_state_json || jsonb_build_object('amendment', e->'payload');

      -- 6. Write STATE_UPSERT to event_log (append-only)
      insert into public.event_log(event_id, envelope_id, kind, occurred_at, payload_json)
      values (
        v_state_event_id,
        v_envelope_id,
        'STATE_UPSERT'::public.event_kind,
        v_now,
        jsonb_build_object(
          'type','STATE_UPSERT',
          'occurred_at', v_now::text,
          'payload', jsonb_build_object('booking_id', v_booking_id, 'state_json', v_state_json)
        )
      )
      on conflict (event_id) do nothing;

      -- 7. Update booking_state
      --    - Apply new dates only if provided (coalesce keeps existing if null)
      --    - status stays 'active' (amendment does NOT change lifecycle status)
      update public.booking_state
      set
        state_json       = v_state_json,
        version          = version + 1,
        updated_at_ms    = v_now_ms,
        last_event_id    = v_state_event_id,
        last_envelope_id = v_envelope_id,
        check_in         = coalesce(v_check_in, check_in),
        check_out        = coalesce(v_check_out, check_out)
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
