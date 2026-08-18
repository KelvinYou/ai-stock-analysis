-- Deployment safety for the durable analysis queue.
--
-- This migration is append-only: it adds atomic admission, observable
-- heartbeats, and lease renewal without rewriting the initial schema history.

alter table public.analysis_runs
    add column if not exists heartbeat_at timestamptz;

-- Admission is serialized in Postgres so API restarts and multiple API
-- replicas cannot bypass the daily cost limit. Idempotency is checked before
-- the quota so a client retry does not consume another slot. Queue depth is
-- durable and workers, rather than enqueue admission, control actual parallelism.
create or replace function public.enqueue_analysis_run(
    p_symbol text,
    p_market text default 'US',
    p_as_of_date date default current_date,
    p_settings jsonb default '{}'::jsonb,
    p_request_idempotency_key text default null,
    p_max_daily_runs integer default 10,
    p_quota_timezone text default 'Asia/Kuala_Lumpur'
)
returns setof public.analysis_runs
language plpgsql
security definer
set search_path = public
as $$
declare
    v_symbol text := upper(trim(p_symbol));
    v_market text := upper(trim(coalesce(p_market, 'US')));
    v_quota_timezone text := coalesce(
        nullif(trim(p_quota_timezone), ''),
        'Asia/Kuala_Lumpur'
    );
    v_request_date date := coalesce(p_as_of_date, (now() at time zone v_quota_timezone)::date);
    v_request_settings jsonb := coalesce(p_settings, '{}'::jsonb);
    v_run_id uuid := gen_random_uuid();
    v_existing public.analysis_runs;
    v_daily_count integer;
    v_quota_day_start timestamptz;
begin
    if v_symbol !~ '^[A-Z0-9][A-Z0-9.-]{0,14}$' then
        raise exception using
            errcode = 'P0001',
            message = 'analysis_invalid_symbol';
    end if;

    -- Same idempotency key must be linearized before the global admission
    -- lock, otherwise two concurrent retries could both pass the pre-check.
    if p_request_idempotency_key is not null then
        perform pg_advisory_xact_lock(
            hashtext('ai-stock-analysis-idempotency:' || p_request_idempotency_key)
        );
        select * into v_existing
        from public.analysis_runs
        where request_idempotency_key = p_request_idempotency_key;
        if found then
            if v_existing.symbol is distinct from v_symbol
                or v_existing.market is distinct from v_market
                or v_existing.as_of_date is distinct from v_request_date
                or v_existing.settings is distinct from v_request_settings
            then
                raise exception using
                    errcode = 'P0001',
                    message = 'analysis_idempotency_conflict',
                    detail = 'idempotency key is already bound to a different analysis request';
            end if;
            return next v_existing;
            return;
        end if;
    end if;

    perform pg_advisory_xact_lock(hashtext('ai-stock-analysis-admission'));

    v_quota_day_start := date_trunc(
        'day',
        now() at time zone v_quota_timezone
    ) at time zone v_quota_timezone;

    select count(*) into v_daily_count
    from public.analysis_runs
    where requested_at >= v_quota_day_start;

    if v_daily_count >= greatest(1, p_max_daily_runs) then
        raise exception using
            errcode = 'P0001',
            message = 'analysis_daily_quota_exceeded',
            detail = format('daily quota is %s run(s)', p_max_daily_runs);
    end if;

    -- The ticker must exist before analysis_runs because of the real FK.
    insert into public.tickers (symbol, market, updated_at)
    values (v_symbol, v_market, now())
    on conflict (symbol) do update
        set market = excluded.market,
            updated_at = excluded.updated_at;

    insert into public.analysis_runs (
        id,
        symbol,
        market,
        as_of_date,
        status,
        settings,
        request_idempotency_key,
        requested_at
    ) values (
        v_run_id,
        v_symbol,
        v_market,
        v_request_date,
        'pending',
        v_request_settings,
        p_request_idempotency_key,
        now()
    );

    return query
    select * from public.analysis_runs where id = v_run_id;
end;
$$;

-- A worker must renew before the lease expires and must prove that it still
-- owns the row. Returning false tells the worker to cancel its pipeline and
-- avoid competing with a reclaimed worker.
create or replace function public.renew_analysis_run_lease(
    p_run_id uuid,
    p_worker_id text,
    p_lease_seconds integer default 900
)
returns table (renewed boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
    v_renewed boolean := false;
begin
    update public.analysis_runs
    set lease_until = now() + make_interval(secs => greatest(60, p_lease_seconds)),
        heartbeat_at = now()
    where id = p_run_id
      and worker_id = p_worker_id
      and status = 'running'
      and (lease_until is null or lease_until > now())
    returning true into v_renewed;

    return query select v_renewed;
end;
$$;

-- Keep the existing queue claim contract, adding the first heartbeat.
create or replace function public.claim_analysis_run(
    p_worker_id text,
    p_lease_seconds integer default 900,
    p_max_attempts integer default 3
)
returns setof public.analysis_runs
language plpgsql
security definer
set search_path = public
as $$
begin
    update public.analysis_runs r
    set status = 'failed',
        completed_at = coalesce(r.completed_at, now()),
        lease_until = null,
        error = coalesce(
            r.error,
            format('abandoned after %s attempt(s) without completing', r.attempts)
        )
    where r.status = 'running'
      and (r.lease_until is null or r.lease_until < now())
      and r.attempts >= greatest(1, p_max_attempts);

    return query
    with candidate as (
        select r.id
        from public.analysis_runs r
        where r.attempts < greatest(1, p_max_attempts)
          and (
              r.status = 'pending'
              or (r.status = 'running' and (r.lease_until is null or r.lease_until < now()))
          )
        order by r.requested_at
        for update skip locked
        limit 1
    )
    update public.analysis_runs r
    set status = 'running',
        worker_id = p_worker_id,
        attempts = r.attempts + 1,
        started_at = coalesce(r.started_at, now()),
        lease_until = now() + make_interval(secs => greatest(60, p_lease_seconds)),
        heartbeat_at = now()
    from candidate claim
    where r.id = claim.id
    returning r.*;
end;
$$;

revoke execute on function public.enqueue_analysis_run(text, text, date, jsonb, text, integer, text)
    from public, anon, authenticated;
grant execute on function public.enqueue_analysis_run(text, text, date, jsonb, text, integer, text)
    to service_role;

revoke execute on function public.renew_analysis_run_lease(uuid, text, integer)
    from public, anon, authenticated;
grant execute on function public.renew_analysis_run_lease(uuid, text, integer)
    to service_role;

revoke execute on function public.claim_analysis_run(text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.claim_analysis_run(text, integer, integer)
    to service_role;
