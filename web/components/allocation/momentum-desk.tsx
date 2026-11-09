"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { SectionCard } from "@/components/shared/section-card";
import { Button } from "@/components/ui/button";
import { type MomentumDashboard, type PeriodKey, type PriceEvidence, type ComparisonReference } from "@/lib/momentum-types";
import { useMomentumSnapshot } from "@/lib/use-momentum-snapshot";

const pct = (v: number | null | undefined) => v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(2)}%`;
const price = (v: number) => v.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
const delta = (v: number | null) => v === null ? "—" : v === 0 ? "0" : v > 0 ? `↑ ${v}` : `↓ ${-v}`;
const periods: [PeriodKey, string][] = [["d1", "1 session"], ["m1", "1 month"], ["m3", "3 months"], ["m12", "12 months"]];
const cycleNames = {monthly_basket: "Monthly basket · reconstructed", equal_weight: "Long hold · fixed-universe equal weight", market: "Market reference"};

export function MomentumDesk({data: original}: {data: MomentumDashboard}) {
  const {data, refresh, refreshing, error, lastChecked} = useMomentumSnapshot(original);
  const {monthly, preview, price_evidence: evidence} = data;
  const context = data.context?.status === "available" ? data.context : null;
  const selected = monthly.status === "available" ? monthly.ranking.slice(0,3) : [];
  const mixed = !!evidence?.supplemental_source;
  const [hiddenSeries, setHiddenSeries] = useState<string[]>([]);
  const extraReferences = (context?.comparisons || []).filter((r): r is ComparisonReference & {status:"available"} => r.status === "available");
  const marketCurve = context?.market.status === "available" ? context.market.curve : [];
  const availableCurves = extraReferences.filter(r => marketCurve.length > 0 && r.curve.length === marketCurve.length && r.curve.every((p,i) => p.date === marketCurve[i].date));
  const momentum = context?.momentum_curve?.status === "available" ? context.momentum_curve : null;
  const momentumAligned = !!momentum && marketCurve.length > 0 && momentum.curve.length === marketCurve.length && momentum.curve.every((p,i)=>p.date===marketCurve[i].date);
  const chartData = context?.market.status === "available" ? context.market.curve.map((p,i) => ({...p,...Object.fromEntries(availableCurves.map(r => [r.ticker,r.curve[i].value])),...(momentumAligned && momentum ? {momentum:momentum.curve[i].value} : {})})) : [];
  const toggleSeries = (key:string) => setHiddenSeries(previous => previous.includes(key) ? previous.filter(k => k!==key) : [...previous,key]);
  return <div className="min-w-0 space-y-8">
    <header className="space-y-4 border-b pb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="eyebrow">US / USD · Fixed-rule portfolio</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink md:text-4xl">Momentum Allocation</h1><p className="mt-3 max-w-2xl text-sm text-graphite">Monthly targets, recent price moves and matched market references.</p></div>
        <Button variant="outline" className="min-h-11" disabled={refreshing} onClick={() => void refresh()}><RefreshCw className="size-4" aria-hidden />{refreshing ? "Checking…" : "Refresh snapshot"}</Button>
      </div>
      <p className="text-sm text-graphite">12-month momentum · Top 3 · Equal one-third weights · Research only</p>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-micro text-graphite">
        <span>Completed session: <span className="num font-medium text-ink">{data.data_sessions?.stocks_date || (preview.status === "available" ? preview.as_of : "Unavailable")}</span></span>
        <span>{evidence ? mixed ? "Mixed sources · replacements recorded" : "Source recorded" : "Source coverage unknown"}</span>
        <span>Daily closes · No live quotes</span>
      </div>
      <div aria-live="polite" className="space-y-1 text-sm text-ink">
        <p className={data.freshness?.status === "latest" ? "font-medium" : "font-medium text-halt"}>{data.freshness?.message || "Latest completed-session coverage is unverified."}</p>
        <p className="text-micro text-graphite">Expected completed session: <span className="num">{data.freshness?.expected_session || "unverified"}</span> · Actual stock session: <span className="num">{data.data_sessions?.stocks_date || "unavailable"}</span>.</p>
      </div>
      <p role="status" className="text-micro text-graphite">{error || (lastChecked ? `Published snapshot checked ${lastChecked}. This does not download new market quotes.` : "Checks for a published snapshot every 60 seconds and when you return to this tab.")}</p>
    </header>

    <SectionCard title="Monthly model basket" description={monthly.status === "available" ? `Decision close: ${monthly.as_of} · Model cycle: ${data.cycle_month}` : "Complete current prices are required."}>
      {monthly.status === "unavailable" ? <p role="status" className="text-sm text-graphite">{monthly.reason}</p> : <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">{selected.map(row => <div key={row.ticker} className="min-w-0 space-y-2">
          <a href={`/${row.ticker}`} className="inline-flex min-h-11 items-center gap-2 text-lg font-semibold text-action underline underline-offset-4">{row.ticker}<ArrowUpRight className="size-4" aria-hidden /></a>
          <p className="num text-3xl text-ink">33⅓%</p><p className="text-micro text-graphite">Decision-date 12m momentum <span className="num">{pct(row.score)}</span></p>
          {context && <p className="text-micro text-graphite">Since decision close <span className="num">{pct(context.stocks.find(s => s.ticker === row.ticker)?.return_since_monthly_close)}</span></p>}
        </div>)}</div>
        {context?.transition && <p className="text-sm text-graphite">Reconstructed change from {context.transition.from}: entered {context.transition.entries.join(", ") || "none"}; exited {context.transition.exits.join(", ") || "none"}. Same {data.strategy.universe.length}-stock universe throughout.</p>}
        <p className="text-micro text-graphite">{context ? `Next calendar month-end review: ${context.decision_month_end}. ` : "Review again at calendar month-end. "}Use the final completed common session, then execute at the next common-session open. Daily rank changes do not trigger intramonth trades.</p>
        <p className="text-micro text-graphite">Model sleeve weights, not your holdings or an order list. Reconstructed from current-vintage adjusted prices; changing the universe requires separate validation.</p>
      </div>}
    </SectionCard>

    <SectionCard title="Daily ranking and entry boundary" description={preview.status === "available" ? `${preview.as_of} · ${data.strategy.universe.length} stocks · third place defines the preview cutoff` : "The latest complete panel is unavailable."}>
      {preview.status === "unavailable" ? <p role="status" className="text-sm text-graphite">{preview.reason}</p> : <>
        <ScrollTable label="Daily momentum ranking"><thead><tr>{["Rank", "Stock", "12m momentum", "Vs #3 · pp", "Δ previous", "Δ month-end", "Monthly basket"].map(h => <Head key={h}>{h}</Head>)}</tr></thead><tbody>{preview.ranking.map((row,i) => {
          const stock = context?.stocks.find(s => s.ticker === row.ticker);
          return <tr key={row.ticker} className="border-t"><Cell>{i+1}</Cell><th className="px-3 py-3 text-left font-medium text-ink">{row.ticker}</th><Cell>{pct(row.score)}</Cell><Cell>{stock ? `${stock.gap_pp >= 0 ? "+" : ""}${stock.gap_pp.toFixed(2)}` : "—"}</Cell><Cell>{stock ? delta(stock.rank_change_previous) : "—"}</Cell><Cell>{stock ? delta(stock.rank_change_monthly) : "—"}</Cell><Cell>{selected.some(s => s.ticker === row.ticker) ? "Included" : "—"}</Cell></tr>;
        })}</tbody></ScrollTable>
        <p className="mt-3 text-micro text-graphite">Negative gap = momentum score below third place; positive = above it. Percentage-point gaps are not the stock-price rise needed to enter. Ties sort alphabetically. ↑ means improved rank.</p>
        {context && <p className="mt-2 text-micro text-graphite">Rank references: previous session {context.previous_rank_date || "unavailable"}; month-end {context.monthly_rank_date || "unavailable"}. Preview-only weights would be one-third for the first three.</p>}
      </>}
    </SectionCard>

    <SectionCard title="Recent moves and price anchors" description="Long-term momentum can remain positive during a sharp recent decline.">
      {!context ? <p className="text-sm text-graphite">{data.context?.status === "unavailable" ? data.context.reason : "Recent context was not recorded in this older snapshot."}</p> : <>
        <ScrollTable label="Recent price performance"><thead><tr>{["Stock", "Adj close · USD", "1 session", "1 month", "3 months", "Below 63-session high", "12m anchor · USD"].map(h => <Head key={h}>{h}</Head>)}</tr></thead><tbody>{context.stocks.map(s => <tr key={s.ticker} className="border-t"><th className="px-3 py-3 text-left font-medium text-ink">{s.ticker}</th><Cell>{price(s.close)}</Cell><Cell>{pct(s.returns.d1)}</Cell><Cell>{pct(s.returns.m1)}</Cell><Cell>{pct(s.returns.m3)}</Cell><Cell>{pct(s.drawdown_63)}</Cell><Cell><span>{price(s.lookback_close)}</span><span className="mt-1 block text-micro text-graphite">{s.lookback_date}</span></Cell></tr>)}</tbody></ScrollTable>
        <p className="mt-3 text-micro text-graphite">Adjusted USD closes as of {context.as_of}. 1 month starts {context.periods.m1.start || "unavailable"}; 3 months starts {context.periods.m3.start || "unavailable"}. — means insufficient evidence. Drawdown uses closing highs, not intraday highs. A change in the rolling 12m score is not a holding-period return.</p>
      </>}
    </SectionCard>

    <SectionCard title="Momentum vs market references" description="Same dates and adjusted-price basis · all five lines are gross, before trading fees.">
      {!context || context.market.status === "unavailable" ? <p className="text-sm text-graphite">{context?.market.status === "unavailable" ? context.market.reason : "Matched reference data was not recorded."}</p> : <>
        <ScrollTable label="Market and equal weight returns"><thead><tr><Head>Reference</Head>{periods.map(([key,label]) => <Head key={key}>{label}</Head>)}</tr></thead><tbody>{[[context.market.label, context.market.returns], ...extraReferences.map(r => [r.label,r.returns]), [`Long hold · ${data.strategy.universe.length} stocks`, context.market.equal_weight_returns]].map(([label,values]) => <tr key={String(label)} className="border-t"><th className="px-3 py-3 text-left font-medium text-ink">{String(label)}</th>{periods.map(([key]) => <Cell key={key}>{pct((values as Record<PeriodKey, number | null>)[key])}</Cell>)}</tr>)}</tbody></ScrollTable>
        <p className="mt-3 text-micro text-graphite">12m common anchor: {context.periods.m12.start || "unavailable"}; end {context.as_of}. Long hold buys all {data.strategy.universe.length} names at each displayed period’s start and holds without rebalancing. It does not backfill current top-three winners. Gross provider-adjusted returns; fees, tax and FX are excluded.</p>
        {(context.comparisons || []).filter(r => r.status === "unavailable").map(r => <p key={r.ticker} className="mt-2 text-micro text-halt">{r.label}: {r.status === "unavailable" ? r.reason : ""} No older reference is substituted.</p>)}
        <div role="group" aria-label="Comparison line visibility" className="mt-4 flex flex-wrap gap-2">{[...(momentumAligned ? [{key:"momentum",label:"Momentum"}] : []),{key:"market",label:context.market.ticker},...availableCurves.map(r=>({key:r.ticker,label:r.ticker})),{key:"equal_weight",label:"Long hold"}].map(item => <Button key={item.key} variant={hiddenSeries.includes(item.key) ? "outline" : "secondary"} className="min-h-11" aria-pressed={!hiddenSeries.includes(item.key)} onClick={()=>toggleSeries(item.key)}>{item.label}</Button>)}</div>
        {context.market.curve.length > 0 ? <div className="mt-5 h-64 w-full min-w-0" role="img" aria-label="Three-month indexed Momentum, SPY, VOO, VT and long-hold comparison"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{left:0,right:8,top:10,bottom:0}}><CartesianGrid stroke="hsl(var(--border))" vertical={false}/><XAxis dataKey="date" minTickGap={35} tick={{fontSize:10,fill:"hsl(var(--graphite))"}} tickFormatter={d => String(d).slice(5)}/><YAxis width={42} domain={["auto","auto"]} tick={{fontSize:10,fill:"hsl(var(--graphite))"}}/><Tooltip contentStyle={{background:"hsl(var(--card))",border:"1px solid hsl(var(--border))",color:"hsl(var(--ink))"}} formatter={v => Number(v).toFixed(2)}/><Legend wrapperStyle={{fontSize:11}}/>{momentumAligned && <Line name="Momentum" dataKey="momentum" hide={hiddenSeries.includes("momentum")} stroke="hsl(var(--ink))" strokeWidth={3} dot={false} isAnimationActive={false}/>}<Line name={context.market.ticker} dataKey="market" hide={hiddenSeries.includes("market")} stroke="hsl(var(--graphite))" strokeDasharray="3 3" strokeWidth={1.5} dot={false} isAnimationActive={false}/>{availableCurves.map((r,i) => <Line key={r.ticker} name={r.ticker} dataKey={r.ticker} hide={hiddenSeries.includes(r.ticker)} stroke="hsl(var(--ink))" strokeDasharray={i === 0 ? "2 3" : "10 4"} strokeWidth={2} dot={false} isAnimationActive={false}/>)}<Line name="Long hold" dataKey="equal_weight" hide={hiddenSeries.includes("equal_weight")} stroke="hsl(var(--graphite))" strokeDasharray="5 4" dot={false} isAnimationActive={false}/></LineChart></ResponsiveContainer></div> : <p className="mt-3 text-micro text-graphite">Indexed curve unavailable: complete synchronized daily history is required.</p>}
        {!momentumAligned && <p className="mt-3 text-sm text-halt">Momentum curve unavailable: {context.momentum_curve?.status === "unavailable" ? context.momentum_curve.reason : "Aligned historical execution evidence is required."}</p>}
        {momentumAligned && momentum && <details className="mt-3"><summary className="min-h-11 cursor-pointer text-sm text-ink">Momentum baskets used in this chart</summary><ul className="mt-2 space-y-2 text-micro text-graphite">{momentum.rebalances.map(r=><li key={r.execution_date}><span className="num">{r.decision_date}</span> decision → <span className="num">{r.execution_date}</span> open · {r.tickers.join(", ")}</li>)}</ul></details>}
        <p className="mt-2 text-micro text-graphite">Indexed to 100 at the three-month closing anchor. Momentum uses each historical month-end basket, executed at the next common-session adjusted open. All lines exclude trading fees, tax and FX; turnover costs can reduce Momentum more than buy-and-hold. This is a reconstruction under the current nine-stock universe, not your account return or validated alpha.</p>
      </>}
    </SectionCard>

    <SectionCard title="This cycle · execution reference" description="Reconstructed next-session-open comparison, not an authenticated trade or a historical backtest.">
      {!context || context.cycle.status === "unavailable" ? <p className="text-sm text-graphite">{context?.cycle.status === "unavailable" ? context.cycle.reason : "Cycle evidence was not recorded."}</p> : <>
        <p className="mb-3 text-sm text-graphite">Decision {context.cycle.decision_date}; adjusted open {context.cycle.start} → close {context.cycle.end}.</p>
        <ScrollTable label="Cycle gross and fee scenario returns"><thead><tr><Head>Portfolio</Head><Head>Gross return</Head><Head>After cost scenario</Head></tr></thead><tbody>{context.cycle.rows.map(row => <tr key={row.id} className="border-t"><th className="px-3 py-3 text-left font-medium text-ink">{cycleNames[row.id]}</th><Cell>{pct(row.gross)}</Cell><Cell>{pct(row.net_scenario)}</Cell></tr>)}{extraReferences.filter(r=>r.cycle.status === "available").map(r => <tr key={r.ticker} className="border-t"><th className="px-3 py-3 text-left font-medium text-ink">{r.label}</th><Cell>{r.cycle.status === "available" ? pct(r.cycle.gross) : "—"}</Cell><Cell>{r.cycle.status === "available" ? pct(r.cycle.net_scenario) : "—"}</Cell></tr>)}</tbody></ScrollTable>
        <p className="mt-3 text-micro text-graphite">Illustrative {context.cycle.cost_bps_per_side} bps per side on entry and hypothetical liquidation now, charged once each. Assumes fractional shares and full initial deployment. Excludes fixed fees, spreads beyond this assumption, taxes and FX. These are short-cycle observations, not evidence of alpha.</p>
      </>}
    </SectionCard>

    <SectionCard title="Rank history" description="Month-end rankings rebuilt under the current universe; not prospectively sealed signals.">
      {!context?.ranking_history.length ? <p className="text-sm text-graphite">Not enough aligned history is available.</p> : <ScrollTable label="Monthly momentum rank history"><thead><tr><Head>Stock</Head>{context.ranking_history.map(h => <Head key={h.as_of}>{h.as_of}</Head>)}<Head>Current</Head></tr></thead><tbody>{context.stocks.map(s => <tr key={s.ticker} className="border-t"><th className="px-3 py-3 text-left font-medium text-ink">{s.ticker}</th>{context.ranking_history.map(h => {const r=h.ranking.find(r => r.ticker===s.ticker);return <Cell key={h.as_of}>{r ? `#${r.rank} · ${pct(r.score)}` : "—"}</Cell>;})}<Cell>{preview.status === "available" ? `#${preview.ranking.findIndex(r => r.ticker===s.ticker)+1}` : "—"}</Cell></tr>)}</tbody></ScrollTable>}
    </SectionCard>

    <details className="rounded-lg border bg-card p-5"><summary className="min-h-11 cursor-pointer text-sm font-semibold text-ink">Data sources, coverage and strategy details</summary><div className="mt-4 space-y-5 text-sm text-graphite">
      <p className="break-words">Strategy <span className="num">{data.strategy.id}</span> · {data.strategy.universe.length} stocks: {data.strategy.universe.join(", ")}.</p>
      <p className="num break-all text-micro">Snapshot generated {data.generated_at_utc}</p>
      <Evidence title="Stock price evidence" evidence={evidence}/><Evidence title="Market reference evidence" evidence={data.reference_evidence}/>
      {Object.entries(data.comparison_evidence || {}).map(([ticker,e]) => <Evidence key={ticker} title={`${ticker} reference evidence`} evidence={e}/>)}
      <p>Freshness compares the actual stock and reference dates with completed XNYS sessions, including holidays, DST and early closes. Scheduled calendar source: <a href="https://www.nyse.com/trade/hours-calendars" className="text-action underline underline-offset-4">NYSE calendar</a>. Unexpected closures or later provider price corrections require refreshed source evidence.</p>
      <p>The configured download targets 09:15 Malaysia time daily after US close. Web checks fetch published snapshots, not new market quotes. Remote scheduling is only active after publication; local source files are refreshed by the CLI.</p>
      <p>All three picks can fall together. The rule stays invested even when all scores are negative. Historical eight-stock results do not validate a changed nine-stock universe.</p>
      <Link href="/allocation" className="inline-flex min-h-11 items-center gap-1 text-action underline underline-offset-4">Historical evidence and uncertainty<ArrowUpRight className="size-3" aria-hidden/></Link>
    </div></details>
  </div>;
}
function Evidence({title,evidence}:{title:string;evidence?:PriceEvidence}) {
  if (!evidence) return <div><p className="font-medium text-ink">{title}</p><p>Source and missing-session details were not recorded. Coverage is unknown.</p></div>;
  return <div className="space-y-2"><p className="font-medium text-ink">{title}</p><p>Primary source: {evidence.primary_source.url ? <a href={evidence.primary_source.url} className="text-action underline underline-offset-4">{evidence.primary_source.name}</a> : evidence.primary_source.name}.</p>
    {evidence.supplemental_source && <p>Supplemental source: {evidence.supplemental_source.url ? <a href={evidence.supplemental_source.url} className="text-action underline underline-offset-4">{evidence.supplemental_source.name}</a> : evidence.supplemental_source.name}. This snapshot combines sources.</p>}
    <p>Primary-source gaps: {evidence.missing_sessions.length ? evidence.missing_sessions.map(r => `${r.date} · ${r.tickers.join(", ")}`).join("; ") : "no excluded rows recorded; complete history is not independently verified"}.</p>
    <p>Filled from supplemental source: {evidence.supplemented_sessions.length ? evidence.supplemented_sessions.map(r => `${r.date} · ${r.tickers.join(", ")}`).join("; ") : "none recorded"}. Replacements are included; unfilled invalid or provisional rows are excluded.</p>
  </div>;
}
function ScrollTable({label,children}:{label:string;children:React.ReactNode}) {return <div role="region" aria-label={label} tabIndex={0} className="max-w-full overflow-x-auto rounded border"><table className="w-full min-w-[570px] text-sm">{children}</table></div>;}
function Head({children}:{children:React.ReactNode}) {return <th className="bg-secondary px-3 py-3 text-left text-micro font-medium text-graphite">{children}</th>;}
function Cell({children}:{children:React.ReactNode}) {return <td className="num whitespace-nowrap px-3 py-3 text-ink">{children}</td>;}
