-- Queue admission contract fixes for an already deployed database.
--
-- 20260818000000 originally exposed a seventh integer argument for a running
-- job limit. That gate rejected valid pending work and was never a reliable
-- concurrency control across workers. Replace it with a timezone-aware quota
-- argument and bind idempotency keys to the full request identity.

drop function if exists public.enqueue_analysis_run(text, text, date, jsonb, text, integer, integer);

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

    -- Same idempotency key is safe to retry only when it means the same
    -- symbol/market/date/settings request. JSONB equality compares normalized
    -- object key ordering, so the request identity is deterministic.
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

    -- This is a cost quota: accepted attempts count even if a provider later
    -- fails. A failed request may already have consumed paid model tokens.
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

revoke execute on function public.enqueue_analysis_run(text, text, date, jsonb, text, integer, text)
    from public, anon, authenticated;
grant execute on function public.enqueue_analysis_run(text, text, date, jsonb, text, integer, text)
    to service_role;
