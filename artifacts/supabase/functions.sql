CREATE OR REPLACE FUNCTION public.apply_envelope(p_envelope jsonb, p_emit jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.apply_event(p_event jsonb, p_emitted jsonb DEFAULT '[]'::jsonb)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_event_id text;
  v_type text;
  v_kind public.event_kind;
  v_occurred_at timestamptz;

  v_em jsonb;
  v_emitted jsonb;
  v_em_kind public.event_kind;
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

    if (v_em->>'type') = 'STATE_UPSERT' then
      raise exception 'STATE_UPSERT_FORBIDDEN_IN_APPLY_EVENT';
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
  end loop;

  return jsonb_build_object('status','APPLIED','event_id', v_event_id);
end;
$function$;

CREATE OR REPLACE FUNCTION public.read_booking_by_business_key(p_tenant_id text, p_source text, p_reservation_ref text, p_property_id text)
 RETURNS jsonb
 LANGUAGE sql
 STABLE
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.read_booking_by_id(p_booking_id text)
 RETURNS jsonb
 LANGUAGE sql
 STABLE
AS $function$
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
$function$;

CREATE OR REPLACE FUNCTION public.rebuild_booking_state()
 RETURNS void
 LANGUAGE plpgsql
AS $function$
declare
  e record;
  v_booking_id text;
  v_state_json jsonb;
  v_ms bigint;
begin
  truncate table public.booking_state;

  for e in
    select
      event_id,
      envelope_id,
      occurred_at,
      payload_json
    from public.event_log
    where kind = 'STATE_UPSERT'::public.event_kind
    order by occurred_at asc, event_id asc
  loop
    v_booking_id := nullif(trim(coalesce(e.payload_json->'payload'->>'booking_id','')), '');
    v_state_json := e.payload_json->'payload'->'state_json';
    v_ms := (extract(epoch from e.occurred_at) * 1000)::bigint;

    if v_booking_id is null then
      raise exception 'REBUILD_STATE_UPSERT_BOOKING_ID_REQUIRED';
    end if;

    if v_state_json is null then
      raise exception 'REBUILD_STATE_UPSERT_STATE_JSON_REQUIRED';
    end if;

    if exists (
      select 1
      from public.booking_state bs
      where bs.booking_id = v_booking_id
    ) then
      update public.booking_state
      set
        state_json = v_state_json,
        version = version + 1,
        updated_at_ms = v_ms,
        last_event_id = e.event_id,
        last_envelope_id = e.envelope_id
      where booking_id = v_booking_id;
    else
      insert into public.booking_state(
        booking_id, version, state_json, updated_at_ms, last_event_id, last_envelope_id
      )
      values (
        v_booking_id, 1, v_state_json, v_ms, e.event_id, e.envelope_id
      );
    end if;
  end loop;
end;
$function$;

CREATE OR REPLACE FUNCTION public.validate_emitted_event(p_event jsonb, p_policy text)
 RETURNS TABLE(out_kind text, out_version integer)
 LANGUAGE plpgsql
AS $function$
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

  select r.is_external, r.is_active, r.required_keys
  into v_is_external, v_is_active, v_required_keys
  from public.event_kind_registry r
  where r.event_kind = v_type_text::public.event_kind
    and r.version = 1;

  if not found then
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
$function$;
