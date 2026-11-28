"use client";
import { useMemo, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { SectionCard } from "@/components/shared/section-card";
import { TradeLog } from "@/components/allocation/trade-log";
import { CurrentRankingPanel } from "@/components/allocation/current-ranking";
import type { CurrentRanking, StrategyComparison, StrategyRow } from "@/lib/allocation-types";
const pct = (n: number) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
const points = (n: number) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(0)} pp`;
const tone = (n: number) => n < 0 ? "text-bear" : "text-ink";
const MAX_LINES = 5;
// Categorical series tokens (validated; never status colours). A strategy keeps its
// slot while plotted, so deselecting another line never repaints the survivors.
const SLOTS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)"];
const grid = "hsl(var(--rule))", axis = "hsl(var(--graphite))";
export function StrategyComparisonDesk({experiments, ranking}: {experiments: StrategyComparison[]; ranking?: CurrentRanking}) {
  const [id, setId] = useState(experiments[0].id);
  const e = experiments.find(x => x.id === id)!;
  const hold = e.rows.find(r => r.id === e.benchmark_id)!;
  const ranked = useMemo(() => e.rows.filter(r => r.id !== e.benchmark_id).sort((a, b) => b.net_compound_return - a.net_compound_return), [e]);
  const initial = (c: StrategyComparison) => {
    const rows = c.rows.filter(r => r.id !== c.benchmark_id).sort((a, b) => b.net_compound_return - a.net_compound_return).map(r => r.id);
    return Array.from(new Set([...rows.slice(0, 3), "momentum_12m"])).slice(0, MAX_LINES);
  };
  // slots[i] holds the strategy plotted in colour slot i, or null when free.
  const [slotState, setSlotState] = useState<Record<string, (string | null)[]>>({});
  const slots = slotState[e.id] ?? Array.from({length: MAX_LINES}, (_, i) => initial(e)[i] ?? null);
  const selected = slots.filter((x): x is string => x !== null);
  const toggle = (rid: string) => setSlotState(p => {
    const cur = p[e.id] ?? slots;
    const at = cur.indexOf(rid);
    if (at >= 0) return {...p, [e.id]: cur.map((x, i) => i === at ? null : x)};
    const free = cur.indexOf(null);
    return free < 0 ? p : {...p, [e.id]: cur.map((x, i) => i === free ? rid : x)};
  });
  const data = e.curve_dates.map((d, i) => ({date: d, ...Object.fromEntries(Object.entries(e.curves).map(([k, v]) => [k, v[i]]))}));
  const colorOf = (rid: string) => SLOTS[Math.max(0, slots.indexOf(rid))];
  const beaten = ranked.filter(r => r.log_excess_ci_95 && r.log_excess_ci_95[0] > 0);
  const label = (r: StrategyRow) => e.rows.find(x => x.id === r.id)!.label;
  return <div className="space-y-8">
    <section className="flex flex-wrap items-end justify-between gap-4">
      <div><label htmlFor="strategy-experiment" className="eyebrow block">Universe</label><select id="strategy-experiment" value={id} onChange={ev => setId(ev.target.value)} className="mt-2 max-w-full rounded border bg-card px-3 py-2 text-sm text-ink focus-visible:outline-action">{experiments.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></div>
      <div className="text-right text-micro text-graphite"><p className="num">{e.start} → {e.end}</p><p>{e.periods} monthly periods · {e.cost_bps} bps / side · top {e.top_n} · {e.universe.length} stocks</p></div>
    </section>
    <div className="grid gap-5 border-y py-5 sm:grid-cols-3">
      <div><p className="eyebrow">Equal-weight hold</p><p className="num mt-2 text-2xl font-medium text-ink">{pct(hold.net_compound_return)}</p><p className="mt-1 text-micro text-graphite">The line every rule has to beat</p></div>
      <div><p className="eyebrow">Rules ahead of hold</p><p className="num mt-2 text-2xl font-medium text-ink">{ranked.filter(r => r.excess_vs_hold > 0).length} / {ranked.length}</p><p className="mt-1 text-micro text-graphite">Observed in this sample only</p></div>
      <div><p className="eyebrow">Statistically supported</p><p className="num mt-2 text-2xl font-medium text-ink">{beaten.length} / {ranked.length}</p><p className="mt-1 text-micro text-graphite">95% interval of monthly excess entirely above zero</p></div>
    </div>
    <aside aria-label="How to read this" className="rounded border p-4 text-sm text-graphite">
      <p className="font-medium text-ink">{beaten.length === 0 ? `No rule is statistically better than holding (0 / ${ranked.length}).` : `${beaten.length} of ${ranked.length} rules clear the 95% interval, before search correction.`}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-micro">
        <li>{ranked.filter(r => r.excess_vs_hold > 0).length} rules finished ahead of hold in this sample, but {e.n_strategies_tested} were tried, so the leader is partly luck (see the deflated Sharpe column).</li>
        <li>The {e.universe.length} stocks are a hand-picked watchlist of names that did well; a point-in-time index universe would likely narrow every gap.</li>
        <li>Past results, not a recommendation to buy or sell.</li>
      </ul>
    </aside>
    {ranking ? <CurrentRankingPanel ranking={ranking} experimentId={e.id} /> : null}
    <SectionCard title="Compare the rules" description={`Same universe, dates, fills and costs. ${e.n_strategies_tested} rules were tried, so the best one is partly luck. Tick up to ${MAX_LINES} rows to plot.`}>
      <div role="region" aria-label="Strategy comparison" tabIndex={0} className="overflow-x-auto rounded border"><table className="w-full min-w-[860px] text-sm">
        <thead className="border-b bg-secondary text-left text-micro text-graphite"><tr>{["Plot", "Strategy", "Net return", "Max drawdown", "Sharpe", "Exposure", "Excess vs hold", "95% interval (log / mo)", "DSR"].map(x => <th key={x} className="px-3 py-3 font-medium">{x}</th>)}</tr></thead>
        <tbody>{[hold, ...ranked].map(r => { const isHold = r.id === e.benchmark_id; const on = isHold || selected.includes(r.id); return <tr key={r.id} className="border-b last:border-0">
          <td className="px-3 py-3">{isHold ? <span aria-hidden className="text-graphite">┄</span> : <input type="checkbox" checked={on} onChange={() => toggle(r.id)} aria-label={`Plot ${r.label}`} disabled={!on && selected.length >= MAX_LINES} style={on ? {accentColor: colorOf(r.id)} : undefined} />}</td>
          <th className="px-3 py-3 text-left font-medium text-ink"><span>{r.label}</span><span className="block text-micro font-normal text-graphite">{r.family}</span></th>
          <td className={`num px-3 py-3 ${tone(r.net_compound_return)}`}>{pct(r.net_compound_return)}</td>
          <td className={`num px-3 py-3 ${tone(r.max_drawdown)}`}>{(r.max_drawdown * 100).toFixed(1)}%</td>
          <td className="num px-3 py-3 text-ink">{r.annualized_sharpe === null ? "n/a" : r.annualized_sharpe.toFixed(2)}</td>
          <td className="num px-3 py-3 text-graphite">{(r.mean_exposure * 100).toFixed(0)}%</td>
          <td className={`num px-3 py-3 ${isHold ? "text-graphite" : tone(r.excess_vs_hold)}`}>{isHold ? "—" : points(r.excess_vs_hold)}</td>
          <td className="num px-3 py-3 text-graphite">{isHold || !r.log_excess_ci_95 ? "—" : `[${r.log_excess_ci_95[0].toFixed(4)}, ${r.log_excess_ci_95[1].toFixed(4)}]`}</td>
          <td className="num px-3 py-3 text-graphite">{isHold || r.deflated_sharpe === null ? "—" : r.deflated_sharpe.toFixed(2)}</td></tr>; })}</tbody></table></div>
      <p className="mt-2 text-micro text-graphite">Sorted by net return. Interval and DSR measure monthly excess versus hold, not raw return; DSR needs about 0.95 to survive the {e.n_strategies_tested}-rule search. Drawdown: {e.drawdown_basis.toLowerCase()}.</p>
    </SectionCard>
    <SectionCard title="The path matters" description="Wealth starts at 100. Monthly observations, not a daily equity series.">
      <div className="mb-3 flex flex-wrap gap-4 text-micro text-graphite"><span>┄ {hold.label}</span>{selected.map(rid => <span key={rid}><span style={{color: colorOf(rid)}}>━</span> {label({id: rid} as StrategyRow)}</span>)}</div>
      <div className="h-72 w-full" role="img" aria-label="Cumulative wealth of the selected strategies versus equal-weight hold"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{left: 0, right: 12, top: 5, bottom: 0}}>
        <CartesianGrid stroke={grid} vertical={false} /><XAxis dataKey="date" tickFormatter={x => String(x).slice(0, 7)} minTickGap={40} tick={{fontSize: 11, fill: axis}} /><YAxis width={52} scale="log" domain={["auto", "auto"]} tick={{fontSize: 11, fill: axis}} />
        <Tooltip itemStyle={{color: "hsl(var(--ink))"}} contentStyle={{background: "hsl(var(--card))", border: "1px solid hsl(var(--rule))", borderRadius: 6, color: "hsl(var(--ink))", fontSize: 12}} formatter={(v: number | string, n: string) => [Number(v).toFixed(0), e.rows.find(r => r.id === n)?.label ?? n]} />
        <Line type="linear" dataKey={e.benchmark_id} stroke={axis} strokeDasharray="5 4" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        {selected.map(rid => <Line key={rid} type="linear" dataKey={rid} stroke={colorOf(rid)} dot={false} strokeWidth={2} isAnimationActive={false} />)}
      </LineChart></ResponsiveContainer></div>
      <p className="mt-2 text-micro text-graphite">Log scale: equal vertical distance means equal percentage change.</p>
    </SectionCard>
    <TradeLog key={e.id} experiment={e} />
    <SectionCard title="How to read this" description="Observed ranking, not a recommendation.">
      <ul className="space-y-2 text-sm text-graphite">{e.notes.map(n => <li key={n}>• {n}</li>)}</ul>
      <details className="mt-4 rounded border p-4"><summary className="cursor-pointer text-sm font-medium text-ink">Rule definitions and sources</summary><dl className="mt-4 space-y-3 text-micro text-graphite">{ranked.map(r => <div key={r.id}><dt className="font-medium text-ink">{r.label}</dt><dd>{r.rule} <span className="text-graphite">Source: {r.source}. Last selection: {r.last_selection.join(", ") || "cash"}.</span></dd></div>)}</dl><p className="mt-4 break-all num text-micro text-graphite">Universe: {e.universe.join(", ")} · Source SHA-256: {e.source_sha256}</p></details>
    </SectionCard>
  </div>;
}
