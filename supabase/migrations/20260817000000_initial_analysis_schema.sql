-- AI Stock Analysis: cloud-first persistence
--
-- Pydantic owns the JSON payload shape. These tables own lifecycle, query
-- indexes, idempotency, visibility, and the point-in-time semantics used by
-- the Python pipeline.

create extension if not exists pgcrypto;

create table if not exists public.tickers (
    symbol text primary key,
    market text not null default 'US' check (market in ('US', 'MY')),
    name text,
    sector text,
    industry text,
    currency text,
    watch_group text check (watch_group in ('tracked', 'candidate')),
    theme text,
    enabled boolean not null default true,
    latest_run_id uuid,
    updated_at timestamptz not null default now()
);

create table if not exists public.price_bars (
    symbol text not null references public.tickers(symbol) on delete cascade,
    bar_date date not null,
    open double precision not null,
    high double precision not null,
    low double precision not null,
    close double precision not null,
    volume bigint not null,
    primary key (symbol, bar_date)
);

-- No (symbol, bar_date desc) index here: the primary key already covers it.
-- Btree scans backwards at the same cost, and `explain analyze` on
-- latest_ticker_summary picks price_bars_pkey for the per-ticker `order by
-- bar_date desc limit 2`. A second index would only add write cost.

create table if not exists public.market_snapshots (
    symbol text not null references public.tickers(symbol) on delete cascade,
    as_of_date date not null,
    fetched_at timestamptz not null default now(),
    fundamentals jsonb not null default '{}'::jsonb,
    technicals jsonb,
    primary key (symbol, as_of_date)
);

-- Same as price_bars: primary key (symbol, as_of_date) already serves the
-- latest-snapshot lookup, in either direction.

create table if not exists public.analysis_runs (
    id uuid primary key default gen_random_uuid(),
    symbol text not null references public.tickers(symbol) on delete cascade,
    market text not null default 'US' check (market in ('US', 'MY')),
    as_of_date date not null,
    status text not null default 'pending'
        check (status in ('pending', 'running', 'completed', 'failed')),
    settings jsonb not null default '{}'::jsonb,
    request_idempotency_key text unique,
    worker_id text,
    attempts integer not null default 0 check (attempts >= 0),
    requested_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    lease_until timestamptz,
    error text
);

create index if not exists analysis_runs_queue_idx
    on public.analysis_runs (status, requested_at);

create index if not exists analysis_runs_symbol_date_idx
    on public.analysis_runs (symbol, as_of_date desc, completed_at desc);

alter table public.tickers
    drop constraint if exists tickers_latest_run_id_fkey;

alter table public.tickers
    add constraint tickers_latest_run_id_fkey
    foreign key (latest_run_id) references public.analysis_runs(id) on delete set null;

create table if not exists public.analysis_artifacts (
    run_id uuid not null references public.analysis_runs(id) on delete cascade,
    symbol text not null references public.tickers(symbol) on delete cascade,
    stage text not null check (
        stage in ('analyst_reports', 'debate_result', 'research_verdict', 'briefing')
    ),
    as_of_date date not null,
    schema_version integer not null default 1 check (schema_version > 0),
    payload jsonb not null,
    is_public boolean not null default true,
    created_at timestamptz not null default now(),
    primary key (run_id, stage)
);

create index if not exists analysis_artifacts_symbol_stage_idx
    on public.analysis_artifacts (symbol, stage, as_of_date desc);

create table if not exists public.outcomes (
    symbol text not null references public.tickers(symbol) on delete cascade,
    as_of_date date not null,
    horizon_days integer not null check (horizon_days > 0),
    signal text not null check (
        signal in ('strong_buy', 'buy', 'neutral', 'sell', 'strong_sell')
    ),
    conviction_score double precision not null check (conviction_score between -1 and 1),
    signal_convergence double precision not null check (signal_convergence between 0 and 1),
    entry_price double precision,
    exit_date date,
    exit_price double precision,
    realized_return double precision,
    source text not null default 'backtest',
    note text,
    created_at timestamptz not null default now(),
    primary key (symbol, as_of_date, horizon_days, source)
);

create index if not exists outcomes_visible_on_idx
    on public.outcomes (symbol, exit_date, as_of_date);

create table if not exists public.backtest_artifacts (
    id uuid primary key default gen_random_uuid(),
    mode text not null,
    symbols text[] not null default '{}',
    metadata jsonb not null default '{}'::jsonb,
    payload jsonb not null,
    markdown text not null,
    created_at timestamptz not null default now()
);

create index if not exists backtest_artifacts_created_idx
    on public.backtest_artifacts (created_at desc);

-- Promote only complete runs. A failed/partial run never replaces the latest
-- visible briefing, and an older backtest date cannot replace a newer one.
create or replace function public.promote_latest_analysis_run()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    if new.status = 'completed'
       and exists (
           select 1 from public.analysis_artifacts a
           where a.run_id = new.id and a.stage = 'briefing'
       ) then
        update public.tickers t
        set latest_run_id = new.id,
            updated_at = now()
        where t.symbol = new.symbol
          and (
              t.latest_run_id is null
              or not exists (
                  select 1
                  from public.analysis_runs current_run
                  where current_run.id = t.latest_run_id
                    and (
                        current_run.as_of_date > new.as_of_date
                        or (
                            current_run.as_of_date = new.as_of_date
                            and coalesce(current_run.completed_at, '-infinity'::timestamptz)
                                > coalesce(new.completed_at, '-infinity'::timestamptz)
                        )
                    )
              )
          );
    end if;
    return new;
end;
$$;

drop trigger if exists analysis_run_promotion_trigger on public.analysis_runs;
create trigger analysis_run_promotion_trigger
after update of status on public.analysis_runs
for each row execute function public.promote_latest_analysis_run();

-- Durable row-locking queue. A lease makes a crashed worker's job visible
-- again, while idempotent artifacts prevent duplicate stage rows on retries.
--
-- The attempt cap is load-bearing, not hygiene. A worker killed hard (OOM,
-- SIGKILL) never reaches its own `fail_run`, so the row stays 'running' with a
-- lease that will expire. Without a cap, the next claim re-runs a full
-- Opus debate, forever, on a job that cannot succeed.
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
    -- Retire exhausted runs first so they stop appearing as claimable and the
    -- reason is visible to the dashboard/operator instead of only in worker logs.
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
        lease_until = now() + make_interval(secs => greatest(60, p_lease_seconds))
    from candidate claim
    where r.id = claim.id
    returning r.*;
end;
$$;

-- Public reads are intentional for this public research dashboard. Writes are
-- reserved for the server-side service role. If private portfolio data is
-- ever added, it must use a separate table/project and user-scoped policies.
alter table public.tickers enable row level security;
alter table public.price_bars enable row level security;
alter table public.market_snapshots enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.analysis_artifacts enable row level security;
alter table public.outcomes enable row level security;
alter table public.backtest_artifacts enable row level security;

grant select on public.tickers to anon, authenticated;
grant select on public.price_bars to anon, authenticated;
grant select on public.market_snapshots to anon, authenticated;
grant select on public.analysis_runs to anon, authenticated;
grant select on public.analysis_artifacts to anon, authenticated;
grant select on public.outcomes to anon, authenticated;
grant select on public.backtest_artifacts to anon, authenticated;
grant all on all tables in schema public to service_role;
-- Without this, a table added by a later migration has no anon grant and the
-- web app fails with a 401 that looks like a key problem rather than a DDL one.
alter default privileges in schema public grant select on tables to anon, authenticated;
alter default privileges in schema public grant all on tables to service_role;
revoke execute on function public.claim_analysis_run(text, integer, integer)
    from public, anon, authenticated;
grant execute on function public.claim_analysis_run(text, integer, integer) to service_role;
revoke execute on function public.promote_latest_analysis_run()
    from public, anon, authenticated;

create policy "public tickers are readable"
    on public.tickers for select to anon, authenticated using (enabled);

create policy "public price bars are readable"
    on public.price_bars for select to anon, authenticated using (true);

create policy "public market snapshots are readable"
    on public.market_snapshots for select to anon, authenticated using (true);

create policy "completed runs are readable"
    on public.analysis_runs for select to anon, authenticated using (status = 'completed');

create policy "public artifacts from completed runs are readable"
    on public.analysis_artifacts for select to anon, authenticated using (
        is_public
        and exists (
            select 1 from public.analysis_runs r
            where r.id = analysis_artifacts.run_id and r.status = 'completed'
        )
    );

create policy "public outcomes are readable"
    on public.outcomes for select to anon, authenticated using (true);

create policy "public backtest artifacts are readable"
    on public.backtest_artifacts for select to anon, authenticated using (true);

-- One cheap row per ticker for the screener. Full JSON artifacts are fetched
-- only on the ticker detail page.
--
-- The last two bars come from a per-ticker lateral limit, not a window function
-- over all of price_bars. The screener renders on every homepage hit and
-- price_bars only grows, so `row_number() over (partition by symbol ...)` would
-- scan the whole table each time; the lateral form uses
-- price_bars_symbol_date_idx and touches two rows per ticker.
create or replace view public.latest_ticker_summary
with (security_invoker = true)
as
with latest_snapshots as (
    select distinct on (s.symbol) s.*
    from public.market_snapshots s
    order by s.symbol, s.as_of_date desc
),
latest_briefings as (
    select
        r.symbol,
        r.id as run_id,
        r.as_of_date,
        a.payload
    from public.analysis_runs r
    join public.analysis_artifacts a
      on a.run_id = r.id and a.stage = 'briefing' and a.is_public
    where r.status = 'completed'
      and r.id = (
          select t.latest_run_id from public.tickers t where t.symbol = r.symbol
      )
)
select
    t.symbol,
    t.market,
    t.name,
    t.sector,
    t.industry,
    t.currency,
    t.watch_group,
    t.theme,
    t.enabled,
    s.as_of_date as market_as_of_date,
    p.latest_price_date,
    (s.fundamentals->'info'->>'name') as info_name,
    (s.fundamentals->'info'->>'market_cap')::double precision as market_cap,
    (s.fundamentals->'info'->>'pe_ratio')::double precision as pe_ratio,
    coalesce((s.technicals->>'close')::double precision, p.latest_close) as price,
    p.previous_close as previous_price,
    (s.technicals->>'rsi_14')::double precision as rsi_14,
    (s.technicals->>'pct_from_52w_high')::double precision as pct_from_52w_high,
    b.run_id as latest_run_id,
    b.as_of_date as briefing_date,
    b.payload->>'overall_signal' as signal,
    (b.payload->'conviction'->>'score')::double precision as conviction,
    (b.payload->'conviction'->>'signal_convergence')::double precision as convergence,
    (b.payload->'action_plan'->>'entry_limit')::double precision as entry_limit,
    (b.payload->'action_plan'->>'stop_loss')::double precision as stop_loss,
    (b.payload->'action_plan'->>'take_profit_1')::double precision as take_profit_1,
    (b.payload->'risk_assessment'->>'risk_reward_ratio') as risk_reward
from public.tickers t
left join latest_snapshots s on s.symbol = t.symbol
left join lateral (
    -- No window function here on purpose: row_number() is evaluated over the
    -- whole partition before LIMIT applies, so it would read every bar for the
    -- symbol anyway. The inner LIMIT 2 walks the index and stops.
    select
        (array_agg(recent.close order by recent.bar_date desc))[1] as latest_close,
        (array_agg(recent.close order by recent.bar_date desc))[2] as previous_close,
        max(recent.bar_date) as latest_price_date
    from (
        select pb.bar_date, pb.close
        from public.price_bars pb
        where pb.symbol = t.symbol
        order by pb.bar_date desc
        limit 2
    ) recent
) p on true
left join latest_briefings b on b.symbol = t.symbol
where t.enabled;

grant select on public.latest_ticker_summary to anon, authenticated;
