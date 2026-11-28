"use client";
import { useState } from "react";
import { Download } from "lucide-react";
import { SectionCard } from "@/components/shared/section-card";
import type { Holding, StrategyComparison } from "@/lib/allocation-types";
const PAGE = 20;
const pct = (n: number) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;
const median = (xs: number[]) => { const s = [...xs].sort((a, b) => a - b); const m = s.length >> 1; return s.length ? (s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2) : 0; };
const why = (h: Holding) => h.exit_reason === "backtest_end" ? "Backtest end" : "Dropped from selection";
const csv = (rows: Holding[]) => ["date,ticker,action,adjusted_open_price,note",
  ...rows.flatMap(h => [`${h.entry_date},${h.ticker},BUY,${h.entry_price.toFixed(4)},entered selection`, `${h.exit_date},${h.ticker},SELL,${h.exit_price.toFixed(4)},${why(h)}`])
    .sort()].join("\n") + "\n";
export function TradeLog({experiment: e}: {experiment: StrategyComparison}) {
  const strategies = e.rows.filter(r => r.id !== e.benchmark_id);
  const [ruleId, setRuleId] = useState("ma_distance");
  const [ticker, setTicker] = useState("");
  const [all, setAll] = useState(false);
  const row = strategies.find(r => r.id === ruleId) ?? strategies[0];
  const tickers = Array.from(new Set(row.holdings.map(h => h.ticker))).sort();
  const shown = row.holdings.filter(h => !ticker || h.ticker === ticker).sort((a, b) => b.entry_date.localeCompare(a.entry_date) || a.ticker.localeCompare(b.ticker));
  const rows = all ? shown : shown.slice(0, PAGE);
  const returns = shown.map(h => h.price_return);
  const download = () => {
    const url = URL.createObjectURL(new Blob([csv(shown)], {type: "text/csv"}));
    const a = document.createElement("a");
    a.href = url; a.download = `${e.id}-${row.id}-trades.csv`; a.click(); URL.revokeObjectURL(url);
  };
  return <SectionCard title="Trade log" description="When each rule bought and sold in the backtest. One row per stay in a stock.">
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap gap-4">
          <div><label htmlFor="trade-rule" className="eyebrow block">Rule</label><select id="trade-rule" value={row.id} onChange={ev => {setRuleId(ev.target.value); setTicker(""); setAll(false);}} className="mt-2 max-w-full rounded border bg-card px-3 py-2 text-sm text-ink focus-visible:outline-action">{strategies.map(r => <option key={r.id} value={r.id}>{r.label}</option>)}</select></div>
          <div><label htmlFor="trade-ticker" className="eyebrow block">Stock</label><select id="trade-ticker" value={ticker} onChange={ev => {setTicker(ev.target.value); setAll(false);}} className="mt-2 rounded border bg-card px-3 py-2 text-sm text-ink focus-visible:outline-action"><option value="">All stocks</option>{tickers.map(t => <option key={t} value={t}>{t}</option>)}</select></div>
        </div>
        <button type="button" onClick={download} disabled={!shown.length} className="flex items-center gap-2 rounded border px-3 py-2 text-sm text-ink hover:bg-secondary focus-visible:outline-action disabled:opacity-50"><Download className="size-4" aria-hidden />Download CSV</button>
      </div>
      <p className="text-micro text-graphite">{row.rule}</p>
      <div className="grid gap-5 border-y py-4 sm:grid-cols-4">
        <div><p className="eyebrow">Stays</p><p className="num mt-2 text-xl text-ink">{shown.length}</p></div>
        <div><p className="eyebrow">Median days held</p><p className="num mt-2 text-xl text-ink">{shown.length ? Math.round(median(shown.map(h => h.days_held))) : "—"}</p></div>
        <div><p className="eyebrow">Median price return</p><p className="num mt-2 text-xl text-ink">{shown.length ? pct(median(returns)) : "—"}</p></div>
        <div><p className="eyebrow">Worst stay</p><p className="num mt-2 text-xl text-bear">{shown.length ? pct(Math.min(...returns)) : "—"}</p></div>
      </div>
      <div role="region" aria-label="Trade log table" tabIndex={0} className="overflow-x-auto rounded border"><table className="w-full min-w-[720px] text-sm">
        <thead className="border-b bg-secondary text-left text-micro text-graphite"><tr>{["Stock", "Bought", "Sold", "Days", "Price return", "Why sold"].map(h => <th key={h} className="px-3 py-3 font-medium">{h}</th>)}</tr></thead>
        <tbody>{rows.length ? rows.map(h => <tr key={`${h.ticker}-${h.entry_date}`} className="border-b last:border-0">
          <th className="px-3 py-2 text-left font-medium text-ink">{h.ticker}</th>
          <td className="num px-3 py-2 text-ink">{h.entry_date} <span className="text-graphite">@ {h.entry_price.toFixed(2)}</span></td>
          <td className="num px-3 py-2 text-ink">{h.exit_date} <span className="text-graphite">@ {h.exit_price.toFixed(2)}</span></td>
          <td className="num px-3 py-2 text-graphite">{h.days_held}</td>
          <td className={`num px-3 py-2 ${h.price_return < 0 ? "text-bear" : "text-ink"}`}>{pct(h.price_return)}</td>
          <td className="px-3 py-2 text-micro text-graphite">{why(h)}</td></tr>) : <tr><td colSpan={6} className="px-3 py-4 text-graphite">This rule never held that stock.</td></tr>}</tbody></table></div>
      {shown.length > PAGE && <button type="button" onClick={() => setAll(v => !v)} className="text-sm text-action underline underline-offset-4 focus-visible:outline-action">{all ? "Show the latest 20" : `Show all ${shown.length} stays`}</button>}
      <ul className="space-y-1 text-micro text-graphite">
        <li>• Prices are provider-adjusted opens used by the backtest, not what a live account would have paid; splits and dividends are folded in.</li>
        <li>• Price return is per stay, before the {e.cost_bps} bps per side cost, and ignores any resizing while the stock stayed selected.</li>
        <li>• Trades run at the open after each month-end decision. A stock that stays selected is not traded.</li>
        <li>• Open stays at the backtest end ({e.end}) are shown as sold there; that sale is a modelling step, not a rule signal.</li>
      </ul>
    </div>
  </SectionCard>;
}
