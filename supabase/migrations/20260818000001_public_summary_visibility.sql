-- Keep the public screener from exposing a briefing artifact that has been
-- explicitly marked private. This is a separate migration because the initial
-- view may already exist in an installed Supabase project.

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
