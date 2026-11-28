export type AllocationArm = {
  id: string; label: string; status: "available" | "not_tested";
  net_return: number | null; drawdown: number | null; mean_exposure: number | null;
};
export type AllocationExperiment = {
  id: string; label: string; kind: "monthly" | "episodes"; cost_bps: number; excess_vs_hold: number;
  universe: string[]; start: string; end: string; periods: number; effective_n: number;
  drawdown_basis: string; price_basis: string; fee_basis: string;
  reference_label: string; ci_reference: string; ci: [number, number] | null;
  curve: {date: string; allocator: number; reference: number; log_excess: number | null}[];
  last_selection: {as_of: string; tickers: string[]}; arms: AllocationArm[];
  notes: string[]; source_sha256: string;
};
export type Holding = {
  ticker: string; entry_date: string; entry_price: number; exit_date: string; exit_price: number;
  days_held: number; price_return: number; exit_reason: "dropped_from_selection" | "backtest_end";
};
export type StrategyRow = {
  id: string; label: string; family: string; rule: string; source: string;
  net_compound_return: number; max_drawdown: number; annualized_sharpe: number | null;
  mean_exposure: number; mean_monthly_turnover: number; excess_vs_hold: number;
  log_excess_ci_95: [number, number] | null; excess_p_value: number | null;
  deflated_sharpe: number | null; last_selection: string[]; holdings: Holding[];
};
export type StrategyComparison = {
  id: string; label: string; universe: string[]; start: string; end: string;
  periods: number; effective_n: number; cost_bps: number; top_n: number;
  n_strategies_tested: number; drawdown_basis: string; price_basis: string;
  notes: string[]; source_sha256: string; benchmark_id: string;
  rows: StrategyRow[]; curve_dates: string[]; curves: Record<string, number[]>;
};
export type RankingRow = {ticker: string; rank: number; value: number | null; weight: number};
export type RankingRule = {
  id: string; label: string; family: string; rule: string; metric: string;
  unit: "pct" | "score"; higher_is_better: boolean; cash_weight: number; ranking: RankingRow[];
  history: {as_of: string; selected: string[]}[];
};
export type TickerSeries = {dates: string[]; close: number[]; sma21: (number | null)[]; sma200: (number | null)[]};
export type CurrentRanking = {status: "unavailable"; reason: string} | {
  status: "available"; scope: "indicative_price_only"; as_of: string; captured_at_utc: string;
  source_sha256: string; top_n: number;
  experiments: Record<string, {universe: string[]; rules: RankingRule[]}>;
  series: Record<string, TickerSeries>;
};
export type AllocationResearch = {
  strategy_comparisons?: StrategyComparison[];
  current_ranking?: CurrentRanking;
  robustness: {rolling_wins: number; rolling_windows: number; rolling_min: number; omitted_months: number; omitted_allocator: number; omitted_hold: number};
  version: 1; generated_at_utc: string; default_id: string;
  experiments: AllocationExperiment[]; current_plan: {status: "unavailable"; reason: string};
  reliability_status: string; promotion_ready: false; limitations: string[];
  current_momentum?: CurrentMomentum;
};
export type CurrentMomentum = {status: "unavailable"; reason: string} | {
  status: "available"; scope: "indicative_price_only"; as_of: string;
  captured_at_utc: string; source_sha256: string; lookback_months: 12; top_n: 3;
  universe: string[];
  ranking: {ticker: string; score: number; lookback_date: string; target_weight: number}[];
};
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const nullable = (v: unknown) => v === null || finite(v);
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === "string");
const date = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
export function isCurrentMomentum(v: unknown): v is CurrentMomentum {
  if (!record(v)) return false;
  if (v.status === "unavailable") return typeof v.reason === "string" && v.reason.length > 0;
  if (v.status !== "available" || v.scope !== "indicative_price_only" || !date(v.as_of)
    || v.lookback_months !== 12 || v.top_n !== 3 || typeof v.captured_at_utc !== "string"
    || !/(Z|[+-]\d{2}:\d{2})$/.test(v.captured_at_utc) || !Number.isFinite(Date.parse(v.captured_at_utc))
    || typeof v.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(v.source_sha256)
    || !strings(v.universe) || v.universe.length < 3 || new Set(v.universe).size !== v.universe.length
    || !v.universe.every(t => /^[A-Z][A-Z0-9.-]*$/.test(t))
    || !Array.isArray(v.ranking) || v.ranking.length !== v.universe.length) return false;
  if (Date.parse(v.captured_at_utc) < Date.parse(String(v.as_of))) return false;
  const rows = v.ranking;
  if (!rows.every((r, i) => record(r) && typeof r.ticker === "string" && (v.universe as string[]).includes(r.ticker)
    && finite(r.score) && r.score > -1 && date(r.lookback_date) && r.lookback_date < String(v.as_of)
    && r.target_weight === (i < 3 ? 1/3 : 0))) return false;
  if (new Set(rows.map(r => r.ticker)).size !== rows.length) return false;
  return rows.every((r,i) => i === 0 || rows[i-1].score > r.score
    || (rows[i-1].score === r.score && rows[i-1].ticker < r.ticker));
}
export function currentMomentumForDate(v: CurrentMomentum | undefined, now = new Date()): CurrentMomentum {
  if (!v) return {status: "unavailable", reason: "No approved current price snapshot is connected."};
  if (v.status === "unavailable") return v;
  const age = (Date.parse(now.toISOString().slice(0,10)) - Date.parse(v.as_of)) / 86_400_000;
  if (!Number.isFinite(age) || age < 1 || age > 4 || Date.parse(v.captured_at_utc) > now.getTime()) return {
    status: "unavailable", reason: "Current ranking expired. Refresh the complete price panel before using it.",
  };
  return v;
}
export function isStrategyComparison(v: unknown): v is StrategyComparison {
  if (!record(v) || typeof v.id !== "string" || !/^[a-z0-9-]+$/.test(v.id) || typeof v.label !== "string"
    || !date(v.start) || !date(v.end) || !finite(v.periods) || !finite(v.effective_n) || !finite(v.cost_bps)
    || !finite(v.top_n) || !finite(v.n_strategies_tested) || typeof v.benchmark_id !== "string"
    || typeof v.drawdown_basis !== "string" || typeof v.price_basis !== "string" || !strings(v.notes)
    || typeof v.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(v.source_sha256)
    || !strings(v.universe) || !Array.isArray(v.curve_dates) || !v.curve_dates.every(date)
    || !record(v.curves) || !Array.isArray(v.rows) || v.rows.length < 2) return false;
  const length = v.curve_dates.length;
  const ids = new Set<string>();
  const rowsOk = v.rows.every(r => {
    if (!record(r) || typeof r.id !== "string" || ids.has(r.id)) return false;
    ids.add(r.id);
    const curve = (v.curves as Record<string, unknown>)[r.id];
    return ["label", "family", "rule", "source"].every(k => typeof r[k] === "string")
      && [r.net_compound_return, r.max_drawdown, r.mean_exposure, r.mean_monthly_turnover, r.excess_vs_hold].every(finite)
      && nullable(r.annualized_sharpe) && nullable(r.excess_p_value) && nullable(r.deflated_sharpe)
      && (r.log_excess_ci_95 === null || (Array.isArray(r.log_excess_ci_95) && r.log_excess_ci_95.length === 2 && r.log_excess_ci_95.every(finite)))
      && strings(r.last_selection)
      && Array.isArray(r.holdings) && r.holdings.every(h => record(h) && typeof h.ticker === "string" && date(h.entry_date) && date(h.exit_date)
        && String(h.entry_date) < String(h.exit_date) && finite(h.entry_price) && h.entry_price > 0 && finite(h.exit_price) && h.exit_price > 0
        && finite(h.days_held) && h.days_held > 0 && finite(h.price_return) && Math.abs(h.price_return - ((h.exit_price as number) / (h.entry_price as number) - 1)) < 1e-6
        && ["dropped_from_selection", "backtest_end"].includes(String(h.exit_reason)))
      && Array.isArray(curve) && curve.length === length && curve.every(x => finite(x) && x > 0);
  });
  return rowsOk && ids.has(v.benchmark_id as string);
}
export function isCurrentRanking(v: unknown): v is CurrentRanking {
  if (!record(v)) return false;
  if (v.status === "unavailable") return typeof v.reason === "string" && v.reason.length > 0;
  if (v.status !== "available" || v.scope !== "indicative_price_only" || !date(v.as_of) || !finite(v.top_n)
    || typeof v.captured_at_utc !== "string" || !/(Z|[+-]\d{2}:\d{2})$/.test(v.captured_at_utc)
    || !Number.isFinite(Date.parse(v.captured_at_utc)) || Date.parse(v.captured_at_utc) < Date.parse(v.as_of)
    || typeof v.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(v.source_sha256)
    || !record(v.experiments) || !record(v.series)) return false;
  const series = v.series as Record<string, unknown>;
  const seriesOk = Object.values(series).every(s => record(s) && Array.isArray(s.dates) && s.dates.length >= 2
    && s.dates.every(date) && ["close", "sma21", "sma200"].every(k => Array.isArray(s[k]) && (s[k] as unknown[]).length === (s.dates as unknown[]).length
      && (s[k] as unknown[]).every(x => k === "close" ? finite(x) && x > 0 : nullable(x))));
  if (!seriesOk) return false;
  return Object.values(v.experiments).every(e => {
    if (!record(e) || !strings(e.universe) || !Array.isArray(e.rules) || !e.rules.length) return false;
    const universe = e.universe as string[];
    return (e.rules as unknown[]).every(r => {
      if (!record(r) || !["id", "label", "family", "rule", "metric"].every(k => typeof r[k] === "string")
        || !["pct", "score"].includes(String(r.unit)) || typeof r.higher_is_better !== "boolean"
        || !finite(r.cash_weight) || r.cash_weight < 0 || r.cash_weight > 1 || !Array.isArray(r.ranking)) return false;
      const rows = r.ranking as unknown[];
      if (rows.length !== universe.length) return false;
      const hist = r.history;
      if (!Array.isArray(hist) || !hist.every((h, i) => record(h) && date(h.as_of) && strings(h.selected)
        && (h.selected as string[]).every(t => universe.includes(t)) && (i === 0 || String((hist[i - 1] as Record<string, unknown>).as_of) < String(h.as_of)))) return false;
      if (hist.length) {
        const last = hist[hist.length - 1] as Record<string, unknown>;
        const now = (rows as Record<string, unknown>[]).filter(row => (row.weight as number) > 0).map(row => row.ticker as string).sort();
        if (last.as_of !== v.as_of || JSON.stringify([...(last.selected as string[])].sort()) !== JSON.stringify(now)) return false;
      }
      let held = r.cash_weight as number;
      const ok = rows.every((row, i) => {
        if (!record(row) || typeof row.ticker !== "string" || !universe.includes(row.ticker) || row.rank !== i + 1
          || !nullable(row.value) || !finite(row.weight) || row.weight < 0 || !(row.ticker in series)) return false;
        held += row.weight as number;
        return true;
      });
      return ok && Math.abs(held - 1) < 1e-6 && new Set(rows.map(row => (row as Record<string, unknown>).ticker)).size === rows.length;
    });
  });
}
export function currentRankingForDate(v: CurrentRanking | undefined, now = new Date()): CurrentRanking {
  if (!v) return {status: "unavailable", reason: "No approved current ranking is connected."};
  if (v.status === "unavailable") return v;
  const age = (Date.parse(now.toISOString().slice(0, 10)) - Date.parse(v.as_of)) / 86_400_000;
  if (!Number.isFinite(age) || age < 1 || age > 4 || Date.parse(v.captured_at_utc) > now.getTime()) return {
    status: "unavailable", reason: "Current ranking expired. Refresh the complete price panel before using it.",
  };
  return v;
}
export function isAllocationResearch(v: unknown): v is AllocationResearch {
  if (!record(v) || v.version !== 1 || v.promotion_ready !== false || typeof v.generated_at_utc !== "string" || !Number.isFinite(Date.parse(v.generated_at_utc)) || typeof v.default_id !== "string" || typeof v.reliability_status !== "string" || !strings(v.limitations) || !record(v.current_plan) || v.current_plan.status !== "unavailable" || typeof v.current_plan.reason !== "string" || !Array.isArray(v.experiments) || !v.experiments.length) return false;
  const robustness = v.robustness;
  if (v.current_momentum !== undefined && !isCurrentMomentum(v.current_momentum)) return false;
  if (v.current_ranking !== undefined && !isCurrentRanking(v.current_ranking)) return false;
  if (v.strategy_comparisons !== undefined && (!Array.isArray(v.strategy_comparisons) || !v.strategy_comparisons.every(isStrategyComparison))) return false;
  if (!record(robustness) || !["rolling_wins","rolling_windows","rolling_min","omitted_months","omitted_allocator","omitted_hold"].every(k => finite(robustness[k]))) return false;
  const valid = v.experiments.every(e => {
    if (!record(e) || typeof e.id !== "string" || !/^[a-z0-9-]+$/.test(e.id)) return false;
    if (!record(e) || !["monthly", "episodes"].includes(String(e.kind)) || !["id", "label", "drawdown_basis", "price_basis", "fee_basis", "reference_label", "ci_reference"].every(k => typeof e[k] === "string") || typeof e.source_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(e.source_sha256) || !finite(e.excess_vs_hold) || !finite(e.cost_bps) || e.cost_bps < 0 || !finite(e.periods) || !Number.isInteger(e.periods) || e.periods < 1 || !finite(e.effective_n) || e.effective_n < 0 || !date(e.start) || !date(e.end) || !strings(e.universe) || e.universe.length < 3 || !strings(e.notes)) return false;
    if (!(e.ci === null || (Array.isArray(e.ci) && e.ci.length === 2 && e.ci.every(finite) && e.ci[0] <= e.ci[1]))) return false;
    if (!record(e.last_selection) || !date(e.last_selection.as_of) || !strings(e.last_selection.tickers) || !e.last_selection.tickers.every(t => (e.universe as string[]).includes(t))) return false;
    if (!Array.isArray(e.curve) || e.curve.length !== e.periods + 1 || !e.curve.every(p => record(p) && date(p.date) && finite(p.allocator) && p.allocator > 0 && finite(p.reference) && p.reference > 0 && nullable(p.log_excess))) return false;
    if (!Array.isArray(e.arms) || !e.arms.length || !e.arms.every(a => record(a) && typeof a.id === "string" && typeof a.label === "string" && ["available", "not_tested"].includes(String(a.status)) && nullable(a.net_return) && nullable(a.drawdown) && nullable(a.mean_exposure) && (a.status !== "not_tested" || [a.net_return,a.drawdown,a.mean_exposure].every(x => x === null)))) return false;
    const arms = e.arms as Record<string, unknown>[];
    return new Set(arms.map(a => a.id)).size === arms.length && ["allocator_only", "continuous_strict_hold", "ai_only", "allocator_plus_ai"].every(id => arms.some(a => a.id === id)) && arms.every(a => (a.status !== "available" || finite(a.net_return)) && (a.mean_exposure === null || (finite(a.mean_exposure) && a.mean_exposure >= 0 && a.mean_exposure <= 1)));
  });
  const snapshot = v.current_momentum as CurrentMomentum | undefined;
  const defaultExperiment = v.experiments.find(e => e.id === v.default_id);
  return valid && new Set(v.experiments.map(e => e.id)).size === v.experiments.length && !!defaultExperiment
    && (snapshot?.status !== "available" || JSON.stringify([...snapshot.universe].sort()) === JSON.stringify([...defaultExperiment.universe].sort()));
}
