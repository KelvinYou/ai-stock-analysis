import { isCurrentMomentum, type CurrentMomentum } from "./allocation-types";

type PriceSource = {name: string; url: string | null};
type PriceSession = {date: string; tickers: string[]};
export type PriceEvidence = {
  primary_source: PriceSource; supplemental_source: PriceSource | null;
  missing_sessions: PriceSession[]; supplemented_sessions: PriceSession[];
};
export type MomentumDashboard = {
  version: 1; generated_at_utc: string; cycle_month: string;
  ai_required: false; promotion_ready: false;
  strategy: {id: string; lookback_months: 12; top_n: 3; universe: string[]};
  preview: CurrentMomentum; monthly: CurrentMomentum;
  price_evidence?: PriceEvidence;
  reference_evidence?: PriceEvidence;
  context?: MomentumContext;
  comparison_evidence?: Record<string, PriceEvidence>;
  session_calendar?: {exchange: "XNYS"; library: string; source_url: string; valid_from_utc: string; valid_until_utc: string; sessions: {date: string; close_utc: string}[]};
  data_sessions?: {stocks_date: string | null; stocks_count: number; references: {ticker: string; date: string | null; complete: boolean}[]};
  freshness?: MomentumFreshness;
};
export type PeriodKey = "d1" | "m1" | "m3" | "m12";
type Returns = Record<PeriodKey, number | null>;
export type StockContext = {
  ticker: string; close: number; lookback_date: string; lookback_close: number;
  returns: Returns; drawdown_63: number | null; return_since_monthly_close: number | null;
  gap_pp: number; monthly_rank: number | null; previous_rank: number | null;
  rank_change_monthly: number | null; rank_change_previous: number | null;
};
type Unavailable = {status: "unavailable"; reason: string};
export type ComparisonReference = {ticker: string; label: string} & (Unavailable | {
  status: "available"; as_of: string; returns: Returns; curve: {date: string; value: number}[];
  cycle: Unavailable | {status: "available"; gross: number; net_scenario: number};
});
export type MomentumFreshness = {status: "latest" | "partial" | "lagging" | "unverified";
  expected_session: string | null; stocks_session: string | null; message: string};
export type MomentumPath = Unavailable | {status:"available"; start:string; end:string; basis:"gross"; cost_bps_per_side:0;
  curve:{date:string;value:number}[]; rebalances:{decision_date:string;execution_date:string;tickers:string[]}[]};
export type MomentumContext = Unavailable | {
  status: "available"; version: 1; as_of: string;
  periods: Record<PeriodKey, {start: string | null; end: string}>;
  momentum_curve?: MomentumPath;
  stocks: StockContext[]; previous_rank_date: string | null; monthly_rank_date: string | null;
  ranking_history: {as_of: string; ranking: {ticker: string; score: number; rank: number}[]}[];
  transition: {from: string; to: string; entries: string[]; exits: string[]} | null;
  decision_month_end: string; reference_ticker: string; comparisons?: ComparisonReference[];
  market: Unavailable | {status: "available"; ticker: string; label: string; as_of: string;
    returns: Returns; equal_weight_returns: Returns; curve: {date: string; market: number; equal_weight: number}[]};
  cycle: Unavailable | {status: "available"; decision_date: string; start: string; end: string;
    cost_bps_per_side: number; rows: {id: "monthly_basket" | "equal_weight" | "market"; gross: number; net_scenario: number}[]};
};
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
function isPriceEvidence(value: unknown, universe: string[], captured: string): value is PriceEvidence {
  if (!record(value) || Object.keys(value).sort().join() !== "missing_sessions,primary_source,supplemental_source,supplemented_sessions") return false;
  const source = (v: unknown): boolean => {
    if (!record(v) || Object.keys(v).sort().join() !== "name,url" || typeof v.name !== "string" || !v.name.trim() || v.name.length > 160) return false;
    if (v.url === null) return true;
    if (typeof v.url !== "string") return false;
    try { const url = new URL(v.url); return url.protocol === "https:" && !!url.hostname && !url.username && !url.password; } catch { return false; }
  };
  if (!source(value.primary_source) || (value.supplemental_source !== null && !source(value.supplemental_source))) return false;
  const sessions = (v: unknown): v is PriceSession[] => Array.isArray(v) && v.every(row =>
    record(row) && Object.keys(row).sort().join() === "date,tickers" && typeof row.date === "string"
    && /^\d{4}-\d{2}-\d{2}$/.test(row.date) && Number.isFinite(Date.parse(row.date))
    && new Date(row.date).toISOString().slice(0,10) === row.date && row.date < captured.slice(0,10)
    && Array.isArray(row.tickers) && row.tickers.length > 0
    && row.tickers.every(t => typeof t === "string" && universe.includes(t))
    && new Set(row.tickers).size === row.tickers.length)
    && new Set(v.map(row => row.date)).size === v.length;
  if (!sessions(value.missing_sessions) || !sessions(value.supplemented_sessions)) return false;
  if (value.supplemented_sessions.length && value.supplemental_source === null) return false;
  return value.supplemented_sessions.every(row => row.tickers.every(ticker =>
    (value.missing_sessions as PriceSession[]).some(gap => gap.date === row.date && gap.tickers.includes(ticker))));
}
const periodKeys: PeriodKey[] = ["d1", "m1", "m3", "m12"];
const finite = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const validDate = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)
  && Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0,10) === v;
const returns = (v: unknown): boolean => record(v) && periodKeys.every(k => v[k] === null || (finite(v[k]) && v[k] > -1));
const unavailable = (v: Record<string, unknown>): boolean => v.status === "unavailable" && typeof v.reason === "string" && !!v.reason;
function isContext(v: unknown, dashboard: MomentumDashboard): v is MomentumContext {
  if (!record(v)) return false;
  if (v.status === "unavailable") return unavailable(v);
  const names = dashboard.strategy.universe, preview = dashboard.preview;
  if (v.status !== "available" || v.version !== 1 || preview.status !== "available" || v.as_of !== preview.as_of
    || !validDate(v.decision_month_end) || v.decision_month_end.slice(0,7) !== dashboard.cycle_month
    || typeof v.reference_ticker !== "string" || !/^[A-Z][A-Z0-9.-]*$/.test(v.reference_ticker)
    || !record(v.periods) || !periodKeys.every(k => record((v.periods as Record<string, unknown>)[k])
      && ((v.periods as Record<string, Record<string, unknown>>)[k].start === null || (validDate((v.periods as Record<string, Record<string, unknown>>)[k].start)
      && String((v.periods as Record<string, Record<string, unknown>>)[k].start) < String(v.as_of)))
      && (v.periods as Record<string, Record<string, unknown>>)[k].end === v.as_of)
    || ![v.previous_rank_date, v.monthly_rank_date].every(d => d === null || (validDate(d) && d <= String(v.as_of)))
    || !Array.isArray(v.stocks) || v.stocks.length !== names.length) return false;
  const rank = (x: unknown) => x === null || (finite(x) && Number.isInteger(x) && x >= 1 && x <= names.length);
  const change = (x: unknown) => x === null || (finite(x) && Number.isInteger(x) && Math.abs(x) < names.length);
  if (!v.stocks.every((r,i) => record(r) && r.ticker === preview.ranking[i].ticker
    && finite(r.close) && r.close > 0 && finite(r.lookback_close) && r.lookback_close > 0
    && validDate(r.lookback_date) && r.lookback_date < String(v.as_of) && returns(r.returns)
    && (r.drawdown_63 === null || (finite(r.drawdown_63) && r.drawdown_63 > -1 && r.drawdown_63 <= 0))
    && (r.return_since_monthly_close === null || (finite(r.return_since_monthly_close) && r.return_since_monthly_close > -1))
    && finite(r.gap_pp) && rank(r.monthly_rank) && rank(r.previous_rank)
    && change(r.rank_change_monthly) && change(r.rank_change_previous))) return false;
  if (!Array.isArray(v.ranking_history) || v.ranking_history.length > 3 || !v.ranking_history.every((h,i,all) =>
    record(h) && validDate(h.as_of) && h.as_of < `${dashboard.cycle_month}-01` && h.as_of <= String(v.as_of)
    && (i === 0 || all[i-1].as_of < h.as_of) && Array.isArray(h.ranking) && h.ranking.length === names.length
    && new Set(h.ranking.map((r: Record<string, unknown>) => r.ticker)).size === names.length
    && h.ranking.every((r: unknown,j: number) => record(r) && names.includes(String(r.ticker)) && r.rank === j+1 && finite(r.score) && r.score > -1))) return false;
  if (v.transition !== null) {
    const t = v.transition;
    if (!record(t) || !validDate(t.from) || !validDate(t.to) || t.from >= t.to || t.to !== v.monthly_rank_date
      || ![t.entries,t.exits].every(a => Array.isArray(a) && new Set(a).size === a.length && a.every(n => names.includes(n)))
      || (t.entries as string[]).some(n => (t.exits as string[]).includes(n))) return false;
  }
  if (!record(v.market) || !record(v.cycle)) return false;
  const m = v.market, c = v.cycle;
  if (m.status === "unavailable") {if (!unavailable(m)) return false;}
  else if (m.status !== "available" || m.ticker !== v.reference_ticker || typeof m.label !== "string" || !m.label
    || m.as_of !== v.as_of || !returns(m.returns) || !returns(m.equal_weight_returns)
    || !Array.isArray(m.curve) || !m.curve.every((p,i,all) => record(p) && validDate(p.date) && p.date <= String(v.as_of)
      && (i === 0 || all[i-1].date < p.date) && finite(p.market) && p.market > 0 && finite(p.equal_weight) && p.equal_weight > 0)) return false;
  if (c.status === "unavailable") {if (!unavailable(c)) return false;}
  else if (c.status !== "available" || !validDate(c.decision_date) || c.decision_date !== v.monthly_rank_date
    || !validDate(c.start) || c.start <= c.decision_date || c.end !== v.as_of || c.start > String(c.end)
    || !finite(c.cost_bps_per_side) || c.cost_bps_per_side < 0 || c.cost_bps_per_side >= 10000
    || !Array.isArray(c.rows) || c.rows.length !== 3 || !c.rows.every((r,i) => record(r)
      && r.id === ["monthly_basket","equal_weight","market"][i] && finite(r.gross) && r.gross > -1
      && finite(r.net_scenario) && r.net_scenario > -1 && r.net_scenario <= r.gross + 1e-12)) return false;
  if (v.momentum_curve !== undefined) {
    const p=v.momentum_curve;
    if (!record(p)) return false;
    if (p.status === "unavailable") {if (!unavailable(p)) return false;}
    else if (p.status !== "available" || p.basis !== "gross" || p.cost_bps_per_side !== 0
      || !validDate(p.start) || p.end !== v.as_of || p.start >= String(p.end)
      || !Array.isArray(p.curve) || !p.curve.length || p.curve[0].date !== p.start || p.curve[0].value !== 100
      || p.curve.at(-1).date !== p.end || !p.curve.every((r,i,all)=>record(r) && validDate(r.date)
        && r.date >= String(p.start) && r.date <= String(p.end) && (i===0 || all[i-1].date < r.date) && finite(r.value) && r.value>0)
      || !Array.isArray(p.rebalances) || !p.rebalances.length || !p.rebalances.every((r,i,all)=>record(r)
        && validDate(r.decision_date) && validDate(r.execution_date) && r.decision_date<r.execution_date && r.execution_date<=String(p.end)
        && (i===0 ? r.execution_date <= String(p.start) : all[i-1].execution_date < r.execution_date)
        && Array.isArray(r.tickers) && r.tickers.length===3 && new Set(r.tickers).size===3 && r.tickers.every(t=>names.includes(t)))) return false;
  }
  if (v.comparisons !== undefined) {
    if (!Array.isArray(v.comparisons) || new Set(v.comparisons.map(r => record(r) ? r.ticker : null)).size !== v.comparisons.length
      || !v.comparisons.every(r => record(r) && typeof r.ticker === "string" && /^[A-Z][A-Z0-9.-]*$/.test(r.ticker)
        && r.ticker !== v.reference_ticker && typeof r.label === "string" && !!r.label
        && (r.status === "unavailable" ? unavailable(r) : r.status === "available" && r.as_of === v.as_of
          && returns(r.returns) && Array.isArray(r.curve) && r.curve.every((p,i,all) => record(p) && validDate(p.date)
            && p.date <= String(v.as_of) && (i===0 || all[i-1].date < p.date) && finite(p.value) && p.value > 0)
          && record(r.cycle) && (r.cycle.status === "unavailable" ? unavailable(r.cycle) : r.cycle.status === "available"
            && finite(r.cycle.gross) && r.cycle.gross > -1 && finite(r.cycle.net_scenario)
            && r.cycle.net_scenario > -1 && r.cycle.net_scenario <= r.cycle.gross + 1e-12)))) return false;
  }
  return true;
}
export function isMomentumDashboard(v: unknown): v is MomentumDashboard {
  if (!record(v) || v.version !== 1 || v.ai_required !== false || v.promotion_ready !== false
    || typeof v.generated_at_utc !== "string" || !/(Z|[+-]\d{2}:\d{2})$/.test(v.generated_at_utc)
    || !Number.isFinite(Date.parse(v.generated_at_utc)) || typeof v.cycle_month !== "string"
    || !/^\d{4}-(0[1-9]|1[0-2])$/.test(v.cycle_month) || !record(v.strategy)
    || typeof v.strategy.id !== "string" || !v.strategy.id || v.strategy.lookback_months !== 12
    || v.strategy.top_n !== 3 || !Array.isArray(v.strategy.universe) || v.strategy.universe.length < 3
    || !v.strategy.universe.every(n => typeof n === "string" && /^[A-Z][A-Z0-9.-]*$/.test(n))
    || new Set(v.strategy.universe).size !== v.strategy.universe.length
    || !isCurrentMomentum(v.preview) || !isCurrentMomentum(v.monthly)) return false;
  if (v.price_evidence !== undefined && !isPriceEvidence(v.price_evidence, v.strategy.universe as string[], v.generated_at_utc)) return false;
  if (v.context !== undefined && !isContext(v.context, v as MomentumDashboard)) return false;
  if (v.reference_evidence !== undefined) {
    const referenceTicker = v.context?.status === "available" ? v.context.reference_ticker : "SPY";
    if (!isPriceEvidence(v.reference_evidence, [referenceTicker], v.generated_at_utc)) return false;
  }
  if (v.comparison_evidence !== undefined) {
    if (!record(v.comparison_evidence) || !Object.entries(v.comparison_evidence).every(([ticker,e]) =>
      /^[A-Z][A-Z0-9.-]*$/.test(ticker) && isPriceEvidence(e,[ticker],v.generated_at_utc as string))) return false;
  }
  if (v.session_calendar !== undefined) {
    const cal=v.session_calendar;
    const timestamp=(x:unknown): x is string => typeof x === "string" && /(Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x));
    if (!record(cal) || cal.exchange !== "XNYS" || typeof cal.library !== "string" || !cal.library
      || cal.source_url !== "https://www.nyse.com/trade/hours-calendars" || !timestamp(cal.valid_from_utc) || !timestamp(cal.valid_until_utc)
      || Date.parse(cal.valid_from_utc) >= Date.parse(cal.valid_until_utc) || !Array.isArray(cal.sessions) || !cal.sessions.length
      || !cal.sessions.every((row,i,all) => record(row) && validDate(row.date) && timestamp(row.close_utc)
        && row.close_utc.slice(0,10) === row.date && Date.parse(row.close_utc) >= Date.parse(cal.valid_from_utc as string)
        && Date.parse(row.close_utc) < Date.parse(cal.valid_until_utc as string) && (i===0 || all[i-1].date < row.date))) return false;
  }
  if (v.data_sessions !== undefined) {
    const sessions=v.data_sessions;
    if (!record(sessions) || !(sessions.stocks_date === null || validDate(sessions.stocks_date))
      || !finite(sessions.stocks_count) || !Number.isInteger(sessions.stocks_count) || sessions.stocks_count < 0 || sessions.stocks_count > v.strategy.universe.length
      || !Array.isArray(sessions.references) || !sessions.references.length
      || !sessions.references.every(r => record(r) && typeof r.ticker === "string" && /^[A-Z][A-Z0-9.-]*$/.test(r.ticker)
        && (r.date === null || validDate(r.date)) && typeof r.complete === "boolean")
      || new Set(sessions.references.map(r=>r.ticker)).size !== sessions.references.length
      || (v.preview.status === "available" && (sessions.stocks_date !== v.preview.as_of || sessions.stocks_count !== v.preview.ranking.length))) return false;
  }
  const dataSessions = v.data_sessions as MomentumDashboard["data_sessions"];
  if (dataSessions && v.context?.status === "available") {
    const expected=[v.context.reference_ticker,...(v.context.comparisons || []).map(r=>r.ticker)].sort();
    if (JSON.stringify(dataSessions.references.map(r=>r.ticker).sort()) !== JSON.stringify(expected)) return false;
    for (const r of dataSessions.references) {
      const available=r.ticker===v.context.reference_ticker ? v.context.market.status === "available" : v.context.comparisons?.some(c=>c.ticker===r.ticker && c.status === "available") || false;
      if (r.complete !== available || (r.complete && r.date !== v.context.as_of)) return false;
    }
  }
  const universe = JSON.stringify([...v.strategy.universe].sort());
  for (const view of [v.preview, v.monthly]) {
    if (view.status === "available" && JSON.stringify([...view.universe].sort()) !== universe) return false;
  }
  if (v.monthly.status === "available") {
    const daysBeforeMonth = (Date.parse(`${v.cycle_month}-01`) - Date.parse(v.monthly.as_of)) / 86_400_000;
    if (daysBeforeMonth < 1 || daysBeforeMonth > 4) return false;
  }
  return true;
}
export function momentumFreshness(data: MomentumDashboard, now = new Date()): MomentumFreshness {
  const calendar=data.session_calendar, coverage=data.data_sessions;
  const stocks=coverage?.stocks_date ?? (data.preview.status === "available" ? data.preview.as_of : null);
  const unknown=(message:string): MomentumFreshness => ({status:"unverified",expected_session:null,stocks_session:stocks,message});
  if (!calendar || !coverage) return unknown("Latest-session coverage is unverified: regenerate with an exchange calendar.");
  if (now.getTime() < Date.parse(calendar.valid_from_utc) || now.getTime() >= Date.parse(calendar.valid_until_utc)) return unknown("Exchange calendar coverage expired; refresh before using current targets.");
  const completed=calendar.sessions.filter(row=>Date.parse(row.close_utc)<=now.getTime());
  const expected=completed.at(-1)?.date;
  if (!expected) return unknown("No completed exchange session can be verified for this clock.");
  const common={expected_session:expected,stocks_session:stocks};
  if (stocks !== expected || coverage.stocks_count !== data.strategy.universe.length) return {...common,status:"lagging",message:`Price data is delayed: expected ${expected}, received ${stocks || "none"}. Current targets are hidden.`};
  if (data.cycle_month !== now.toISOString().slice(0,7)) return {...common,status:"lagging",message:"Calendar-month rollover requires a new model snapshot. Current targets are hidden."};
  const missing=coverage.references.filter(r=>r.date!==expected || !r.complete).map(r=>r.ticker);
  if (missing.length) return {...common,status:"partial",message:`Stocks match the latest completed session; reference coverage is incomplete: ${missing.join(", ")}.`};
  return {...common,status:"latest",message:`Latest completed session verified: ${coverage.stocks_count}/${data.strategy.universe.length} stocks and ${coverage.references.map(r=>r.ticker).join(", ")} match ${expected}.`};
}
export function momentumDashboardForDate(data: MomentumDashboard, now = new Date()): MomentumDashboard {
  const freshness=momentumFreshness(data,now);
  if (freshness.status === "lagging" || freshness.status === "unverified" || Date.parse(data.generated_at_utc)>now.getTime()) {
    const unavailable: CurrentMomentum={status:"unavailable",reason:freshness.message};
    return {...data,freshness,preview:unavailable,monthly:unavailable,context:{status:"unavailable",reason:freshness.message}};
  }
  return {...data,freshness};
}

export function shouldReplaceMomentumSnapshot(current: MomentumDashboard, next: MomentumDashboard): boolean {
  if (Date.parse(next.generated_at_utc) < Date.parse(current.generated_at_utc)) return false;
  if (next.strategy.id === current.strategy.id && next.preview.status === "available" && current.preview.status === "available"
    && next.preview.as_of < current.preview.as_of) return false;
  return true;
}
