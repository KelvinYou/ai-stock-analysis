"use client";
import { useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, BarChart, Bar, Cell, LabelList, ReferenceLine } from "recharts";
import { ArrowUpRight, Layers } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import type { CurrentRanking, RankingRow, RankingRule } from "@/lib/allocation-types";
const axis = "hsl(var(--graphite))", grid = "hsl(var(--rule))";
const tip = {background: "hsl(var(--card))", border: "1px solid hsl(var(--rule))", borderRadius: 6, color: "hsl(var(--ink))", fontSize: 12};
const fmt = (rule: RankingRule, v: number | null) => v === null ? "n/a" : rule.unit === "pct" ? `${v >= 0 && rule.higher_is_better ? "+" : ""}${(v * 100).toFixed(1)}%` : v.toFixed(2);
const weight = (w: number) => w <= 0 ? "—" : `${(w * 100).toFixed(1)}%`;
const status = (r: RankingRow) => r.weight > 0 ? "Selected" : r.value === null ? "Ineligible" : "Skipped";
export function CurrentRankingPanel({ranking, experimentId}: {ranking: CurrentRanking; experimentId: string}) {
  const [ruleId, setRuleId] = useState("ma_distance");
  const [picked, setPicked] = useState<string | null>(null);
  if (ranking.status === "unavailable") return <SectionCard title="Current ranking" description="What each price rule would pick at the last completed session.">
    <div className="rounded border p-6"><Layers className="size-6 text-graphite" aria-hidden /><p role="status" className="mt-3 max-w-xl text-sm text-graphite">{ranking.reason}</p><p className="mt-3 text-micro text-graphite">Historical comparison below is unaffected. A stale ranking is never shown as current.</p></div></SectionCard>;
  const block = ranking.experiments[experimentId];
  if (!block) return null;
  const rule = block.rules.find(r => r.id === ruleId) ?? block.rules[0];
  const chosen = rule.ranking.filter(r => r.weight > 0);
  const focus = picked && rule.ranking.some(r => r.ticker === picked) ? picked : (chosen[0] ?? rule.ranking[0]).ticker;
  const s = ranking.series[focus];
  const line = s.dates.map((d, i) => ({date: d, close: s.close[i], sma21: s.sma21[i], sma200: s.sma200[i]}));
  const families = Array.from(new Set(block.rules.map(r => r.family)));
  const focusRow = rule.ranking.find(r => r.ticker === focus)!;
  return <SectionCard title="Current ranking" description={`Completed session ${ranking.as_of}. Price only, no AI. Month-end preview, not a trading signal.`}>
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><label htmlFor="ranking-rule" className="eyebrow block">Rule</label><select id="ranking-rule" value={rule.id} onChange={e => {setRuleId(e.target.value); setPicked(null);}} className="mt-2 max-w-full rounded border bg-card px-3 py-2 text-sm text-ink focus-visible:outline-action">{families.map(f => <optgroup key={f} label={f}>{block.rules.filter(r => r.family === f).map(r => <option key={r.id} value={r.id}>{r.label}</option>)}</optgroup>)}</select></div>
        <p className="max-w-md text-micro text-graphite">{rule.rule}{!rule.higher_is_better ? " Ranked lowest value first." : ""}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3" aria-label="Names this rule selects">
        <span className="eyebrow">Selects</span>
        {chosen.length ? chosen.map(r => <a key={r.ticker} href={`/${r.ticker}`} className="flex items-center gap-3 rounded border px-4 py-2 text-sm text-ink hover:bg-secondary"><span className="num font-medium">{r.ticker}</span><span className="num text-graphite">{weight(r.weight)}</span><ArrowUpRight className="size-3" aria-hidden /></a>) : <span className="text-sm text-graphite">Nothing: all cash</span>}
        {rule.cash_weight > 0.0001 && <span className="rounded bg-secondary px-3 py-2 text-micro text-graphite">Cash {(rule.cash_weight * 100).toFixed(0)}%</span>}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <p className="eyebrow mb-2">{rule.metric}, by rank</p>
          <div className="w-full" style={{height: 26 * rule.ranking.length + 24}} role="img" aria-label={`${rule.metric} for each stock in rank order; selected names highlighted`}>
            <ResponsiveContainer width="100%" height="100%"><BarChart data={rule.ranking} layout="vertical" margin={{left: 4, right: 56, top: 4, bottom: 4}} barCategoryGap={4}>
              <CartesianGrid stroke={grid} horizontal={false} />
              <XAxis type="number" domain={[(min: number) => (min < 0 ? min * 1.5 : 0), (max: number) => (max > 0 ? max * 1.25 : 0)]} tickFormatter={v => rule.unit === "pct" ? `${(v * 100).toFixed(0)}%` : v.toFixed(1)} tick={{fontSize: 11, fill: axis}} />
              <YAxis type="category" dataKey="ticker" width={64} tick={{fontSize: 11, fill: axis}} />
              {rule.unit === "pct" && <ReferenceLine x={0} stroke={axis} />}
              <Tooltip itemStyle={{color: "hsl(var(--ink))"}} cursor={{fill: "hsl(var(--secondary))"}} contentStyle={tip} formatter={(v: number | string) => [fmt(rule, Number(v)), rule.metric]} />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false} onClick={(d: {ticker?: string}) => d.ticker && setPicked(d.ticker)}>
                {rule.ranking.map(r => <Cell key={r.ticker} fill={r.weight > 0 ? "var(--series-1)" : "hsl(var(--graphite) / 0.45)"} cursor="pointer" />)}
                <LabelList dataKey="value" position="right" formatter={(v: number | string | null) => v === null ? "" : fmt(rule, Number(v))} style={{fontSize: 11, fill: "hsl(var(--ink))"}} />
              </Bar>
            </BarChart></ResponsiveContainer>
          </div>
          <p className="mt-2 text-micro text-graphite"><span style={{color: "var(--series-1)"}}>■</span> Selected · <span className="text-graphite">■</span> Skipped. Click a bar or row to inspect its prices.</p>
        </div>
        <div>
          <div role="region" aria-label="Current ranking table" tabIndex={0} className="overflow-x-auto rounded border"><table className="w-full min-w-[360px] text-sm">
            <thead className="border-b bg-secondary text-left text-micro text-graphite"><tr>{["#", "Stock", rule.metric, "Weight", "Status"].map(h => <th key={h} className="px-3 py-3 font-medium">{h}</th>)}</tr></thead>
            <tbody>{rule.ranking.map(r => <tr key={r.ticker} aria-selected={r.ticker === focus} onClick={() => setPicked(r.ticker)} className={`cursor-pointer border-b last:border-0 hover:bg-secondary ${r.ticker === focus ? "bg-secondary" : ""}`}>
              <td className="num px-3 py-2 text-graphite">{r.rank}</td>
              <th className="px-3 py-2 text-left font-medium"><button type="button" onClick={() => setPicked(r.ticker)} className="text-ink underline-offset-4 hover:underline focus-visible:outline-action">{r.ticker}</button></th>
              <td className={`num px-3 py-2 ${r.value !== null && r.value < 0 && rule.unit === "pct" && rule.higher_is_better ? "text-bear" : "text-ink"}`}>{fmt(rule, r.value)}</td>
              <td className="num px-3 py-2 text-graphite">{weight(r.weight)}</td>
              <td className="px-3 py-2 text-micro text-graphite">{status(r)}</td></tr>)}</tbody></table></div>
        </div>
      </div>

      <SelectionHistory rule={rule} />
      <div>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><p className="eyebrow">{focus} · price with moving averages</p><p className="text-micro text-graphite">Rank {focusRow.rank} · {rule.metric} {fmt(rule, focusRow.value)} · {status(focusRow)}</p></div>
        <div className="mb-2 flex flex-wrap gap-4 text-micro text-graphite"><span><span style={{color: "var(--series-1)"}}>━</span> Close</span><span><span style={{color: "var(--series-2)"}}>━</span> 21-day average</span><span><span style={{color: "var(--series-3)"}}>━</span> 200-day average</span></div>
        <div className="h-64 w-full" role="img" aria-label={`${focus} close with 21-day and 200-day averages over the last year`}>
          <ResponsiveContainer width="100%" height="100%"><LineChart data={line} margin={{left: 0, right: 12, top: 5, bottom: 0}}>
            <CartesianGrid stroke={grid} vertical={false} />
            <XAxis dataKey="date" tickFormatter={x => String(x).slice(0, 7)} minTickGap={48} tick={{fontSize: 11, fill: axis}} />
            <YAxis width={52} domain={["auto", "auto"]} tickFormatter={v => Number(v).toFixed(0)} tick={{fontSize: 11, fill: axis}} />
            <Tooltip itemStyle={{color: "hsl(var(--ink))"}} contentStyle={tip} formatter={(v: unknown, n: string) => [typeof v === "number" ? v.toFixed(2) : "n/a", n]} />
            <Line type="linear" dataKey="close" name="Close" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="linear" dataKey="sma21" name="21-day average" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
            <Line type="linear" dataKey="sma200" name="200-day average" stroke="var(--series-3)" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls={false} />
          </LineChart></ResponsiveContainer>
        </div>
      </div>
      <p className="text-micro text-graphite">Captured {ranking.captured_at_utc}. Adjusted provider prices; fees, taxes and your existing holdings are not considered. Research output, not investment advice.</p>
    </div>
  </SectionCard>;
}

const monthLabel = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-US", {month: "short", timeZone: "UTC"});
function SelectionHistory({rule}: {rule: RankingRule}) {
  const hist = rule.history;
  if (hist.length < 2) return null;
  const everSelected = rule.ranking.map(r => r.ticker).filter(t => hist.some(h => h.selected.includes(t)));
  const moves = hist.slice(1).map((h, i) => h.selected.filter(t => !hist[i].selected.includes(t)).length);
  const avg = moves.reduce((a, b) => a + b, 0) / moves.length;
  const size = Math.max(...hist.map(h => h.selected.length));
  return <div>
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><p className="eyebrow">Selection history · last {hist.length - 1} month-ends</p>
      <p className="text-micro text-graphite">{size ? `On average ${avg.toFixed(1)} of ${size} names change each month.` : "Never invested."} Each past month uses only prices up to that date; the last column is the current preview.</p></div>
    <div role="region" aria-label={`${rule.label} selection history`} tabIndex={0} className="overflow-x-auto rounded border"><table className="w-full min-w-[640px] border-separate text-micro" style={{borderSpacing: 2}}>
      <thead><tr><th className="px-2 py-1 text-left font-medium text-graphite">Stock</th>{hist.map((h, i) => <th key={h.as_of} className="px-1 py-1 text-center font-medium text-graphite" title={h.as_of}>{i === hist.length - 1 ? "Now" : monthLabel(h.as_of)}</th>)}</tr></thead>
      <tbody>{everSelected.length ? everSelected.map(t => <tr key={t}>
        <th className="px-2 py-1 text-left font-medium text-ink">{t}</th>
        {hist.map(h => { const on = h.selected.includes(t); return <td key={h.as_of} title={`${t} · ${h.as_of} · ${on ? "selected" : "not selected"}`} className="h-6 rounded-sm text-center" style={on ? {background: "var(--series-1)", color: "#fff"} : {background: "hsl(var(--secondary))"}}><span aria-hidden>{on ? "●" : ""}</span><span className="sr-only">{on ? "Selected" : "Not selected"}</span></td>; })}
      </tr>) : <tr><td colSpan={hist.length + 1} className="px-2 py-3 text-graphite">No names were selected in this window.</td></tr>}</tbody></table></div>
  </div>;
}
