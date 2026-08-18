import { promises as fs } from "node:fs";
import path from "node:path";
import { cache } from "react";
import {
  ANALYSIS_API_CONFIGURED,
  assertAnalysisApiConfiguration,
  listTickerSummariesFromApi,
  loadTickerFromApi,
} from "./api";
import { loadWatchlistMap } from "./watchlist";
import type {
  AnalystReports,
  Briefing,
  DebateResult,
  Fundamentals,
  PricePoint,
  Technicals,
  TickerBundle,
  TickerSummary,
  WatchGroup,
  WatchlistEntry,
} from "./types";
import { parseRatio } from "./format";

const DATA_DIR = process.env.STOCK_DATA_DIR
  ? path.resolve(process.env.STOCK_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");

const SUPABASE_URL =
  process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_KEY =
  process.env.SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
  "";
const CLOUD_CONFIGURED = Boolean(SUPABASE_URL && SUPABASE_KEY);

const SUMMARY_CONCURRENCY = 16;

type CloudSummaryRow = {
  symbol: string;
  market: string;
  name: string | null;
  info_name: string | null;
  sector: string | null;
  industry: string | null;
  currency: string | null;
  watch_group: WatchGroup | null;
  theme: string | null;
  market_as_of_date: string | null;
  latest_price_date: string | null;
  previous_price: number | null;
  price: number | null;
  pe_ratio: number | null;
  rsi_14: number | null;
  pct_from_52w_high: number | null;
  latest_run_id: string | null;
  briefing_date: string | null;
  signal: TickerSummary["signal"];
  conviction: number | null;
  convergence: number | null;
  entry_limit: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  risk_reward: string | null;
};

async function cloudRows<T>(
  resource: string,
  params: Record<string, string> = {},
): Promise<T[]> {
  if (!CLOUD_CONFIGURED) {
    throw new Error("Supabase web configuration is missing");
  }
  const query = new URLSearchParams(params);
  const response = await fetch(
    `${SUPABASE_URL.replace(/\/$/, "")}/rest/v1/${resource}?${query.toString()}`,
    {
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
      },
      next: { revalidate: 60 },
    },
  );
  if (!response.ok) {
    throw new Error(`Supabase ${resource} failed (${response.status})`);
  }
  return (await response.json()) as T[];
}

async function cloudRowsAll<T>(
  resource: string,
  params: Record<string, string> = {},
): Promise<T[]> {
  const rows: T[] = [];
  const pageSize = 1000;
  for (let offset = 0; ; offset += pageSize) {
    const page = await cloudRows<T>(resource, {
      ...params,
      offset: String(offset),
      limit: String(pageSize),
    });
    rows.push(...page);
    if (page.length < pageSize) return rows;
  }
}

function summaryFromCloud(
  row: CloudSummaryRow,
  watch: WatchlistEntry | undefined,
): TickerSummary {
  const price = row.price;
  const previous = row.previous_price;
  const priceChangePct =
    price != null && previous != null && previous !== 0
      ? ((price - previous) / previous) * 100
      : null;
  const toEntryPct =
    row.entry_limit != null && price != null && price !== 0
      ? ((row.entry_limit - price) / price) * 100
      : null;

  return {
    symbol: row.symbol,
    name: row.info_name ?? row.name ?? row.symbol,
    sector: row.sector,
    market: row.market ?? watch?.market ?? "—",
    currency: row.currency ?? "USD",
    price,
    priceChangePct,
    signal: row.signal ?? null,
    conviction: row.conviction,
    convergence: row.convergence,
    briefingDate: row.briefing_date,
    briefingAgeDays: ageInDays(row.briefing_date),
    entryLimit: row.entry_limit,
    stopLoss: row.stop_loss,
    takeProfit1: row.take_profit_1,
    toEntryPct,
    riskReward: parseRatio(row.risk_reward),
    peRatio: row.pe_ratio,
    rsi14: row.rsi_14,
    pctFrom52wHigh: row.pct_from_52w_high,
    asOfDate: row.market_as_of_date ?? row.latest_price_date,
    group: row.watch_group ?? watch?.group ?? null,
    theme: row.theme ?? watch?.theme ?? null,
  };
}

async function loadCloudTicker(symbol: string): Promise<TickerBundle | null> {
  const normalized = symbol.toUpperCase();
  const [summaryRows, snapshotRows] = await Promise.all([
    cloudRows<CloudSummaryRow>("latest_ticker_summary", {
      symbol: `eq.${normalized}`,
      select: "*",
      limit: "1",
    }),
    cloudRows<Record<string, unknown>>("market_snapshots", {
      symbol: `eq.${normalized}`,
      select: "*",
      order: "as_of_date.desc",
      limit: "1",
    }),
  ]);
  if (!summaryRows.length && !snapshotRows.length) return null;

  const summary = summaryRows[0];
  const snapshot = snapshotRows[0];
  const priceRows = await cloudRowsAll<{
    bar_date: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
  }>("price_bars", {
    symbol: `eq.${normalized}`,
    select: "bar_date,open,high,low,close,volume",
    order: "bar_date.asc",
  });

  const artifactRows = summary?.latest_run_id
    ? await cloudRows<{ stage: string; payload: unknown }>("analysis_artifacts", {
        run_id: `eq.${summary.latest_run_id}`,
        select: "stage,payload",
      })
    : [];
  const artifacts = Object.fromEntries(
    artifactRows.map((row) => [row.stage, row.payload]),
  );

  return {
    symbol: normalized,
    fundamentals: (snapshot?.fundamentals as Fundamentals | null) ?? null,
    technicals: (snapshot?.technicals as Technicals | null) ?? null,
    priceHistory: priceRows.map((row) => ({
      date: row.bar_date,
      open: Number(row.open),
      high: Number(row.high),
      low: Number(row.low),
      close: Number(row.close),
      volume: Number(row.volume),
    })),
    analystReports: (artifacts.analyst_reports as AnalystReports | null) ?? null,
    debate: (artifacts.debate_result as DebateResult | null) ?? null,
    briefing: (artifacts.briefing as Briefing | null) ?? null,
  };
}

async function mapWithConcurrency<T, U>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<U>,
): Promise<U[]> {
  const results: U[] = new Array(items.length);
  let cursor = 0;
  const workerCount = Math.min(limit, items.length);
  const workers = Array.from({ length: workerCount }, async () => {
    while (true) {
      const idx = cursor++;
      if (idx >= items.length) return;
      results[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return results;
}

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(filePath, "utf8");
    return JSON.parse(raw) as T;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw err;
  }
}

async function readCsv(filePath: string): Promise<PricePoint[]> {
  let raw: string;
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw err;
  }
  const lines = raw.trim().split(/\r?\n/);
  if (lines.length <= 1) return [];
  const header = lines[0].split(",").map((s) => s.trim().toLowerCase());
  const idx = (name: string) => header.indexOf(name);
  const di = idx("date");
  const oi = idx("open");
  const hi = idx("high");
  const li = idx("low");
  const ci = idx("close");
  const vi = idx("volume");
  const out: PricePoint[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    if (cols.length < 6) continue;
    const num = (k: number) => Number(cols[k]);
    out.push({
      date: cols[di],
      open: num(oi),
      high: num(hi),
      low: num(li),
      close: num(ci),
      volume: num(vi),
    });
  }
  return out;
}

export const listTickers = cache(async (): Promise<string[]> => {
  assertAnalysisApiConfiguration();
  if (ANALYSIS_API_CONFIGURED) {
    return (await listTickerSummariesFromApi()).map((summary) => summary.symbol);
  }
  if (CLOUD_CONFIGURED) {
    const rows = await cloudRows<{ symbol: string }>("tickers", {
      select: "symbol",
      enabled: "eq.true",
      order: "symbol.asc",
    });
    return rows.map((row) => row.symbol);
  }
  try {
    const entries = await fs.readdir(DATA_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && !e.name.startsWith("."))
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
});

export async function loadTicker(symbol: string): Promise<TickerBundle | null> {
  assertAnalysisApiConfiguration();
  if (ANALYSIS_API_CONFIGURED) return loadTickerFromApi(symbol);
  if (CLOUD_CONFIGURED) return loadCloudTicker(symbol);
  const dir = path.join(DATA_DIR, symbol);
  try {
    const stat = await fs.stat(dir);
    if (!stat.isDirectory()) return null;
  } catch {
    return null;
  }
  const [fundamentals, technicals, priceHistory, analystReports, debate, briefing] =
    await Promise.all([
      readJson<Fundamentals>(path.join(dir, "fundamentals.json")),
      readJson<Technicals>(path.join(dir, "technicals.json")),
      readCsv(path.join(dir, "price_history.csv")),
      readJson<AnalystReports>(path.join(dir, "analyst_reports.json")),
      readJson<DebateResult>(path.join(dir, "debate_result.json")),
      readJson<Briefing>(path.join(dir, "briefing.json")),
    ]);
  return {
    symbol,
    fundamentals,
    technicals,
    priceHistory,
    analystReports,
    debate,
    briefing,
  };
}

interface LastCloses {
  latest: number | null;
  prev: number | null;
  latestDate: string | null;
}

const NO_CLOSES: LastCloses = { latest: null, prev: null, latestDate: null };

async function readLastTwoCloses(filePath: string): Promise<LastCloses> {
  let raw: string;
  try {
    raw = await fs.readFile(filePath, "utf8");
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return NO_CLOSES;
    throw err;
  }
  const lines = raw.trimEnd().split(/\r?\n/);
  if (lines.length <= 1) return NO_CLOSES;
  const header = lines[0].split(",").map((s) => s.trim().toLowerCase());
  const ci = header.indexOf("close");
  const di = header.indexOf("date");
  if (ci < 0) return NO_CLOSES;
  const parseClose = (line: string): number | null => {
    const cols = line.split(",");
    if (cols.length <= ci) return null;
    const n = Number(cols[ci]);
    return Number.isFinite(n) ? n : null;
  };
  const lastLine = lines[lines.length - 1];
  const latest = parseClose(lastLine);
  const prev = lines.length >= 3 ? parseClose(lines[lines.length - 2]) : null;
  const latestDate = di >= 0 ? (lastLine.split(",")[di]?.trim() ?? null) : null;
  return { latest, prev, latestDate: latestDate || null };
}

/** Whole days from `iso` (YYYY-MM-DD) to today, UTC. Null if unparseable. */
function ageInDays(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const then = Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);
  if (Number.isNaN(then)) return null;
  const today = new Date();
  const todayUtc = Date.UTC(
    today.getUTCFullYear(),
    today.getUTCMonth(),
    today.getUTCDate(),
  );
  return Math.max(0, Math.round((todayUtc - then) / 86_400_000));
}

async function loadTickerSummary(
  symbol: string,
  watch: WatchlistEntry | undefined,
): Promise<TickerSummary | null> {
  if (CLOUD_CONFIGURED) {
    const rows = await cloudRows<CloudSummaryRow>("latest_ticker_summary", {
      symbol: `eq.${symbol.toUpperCase()}`,
      select: "*",
      limit: "1",
    });
    return rows[0] ? summaryFromCloud(rows[0], watch) : null;
  }
  const dir = path.join(DATA_DIR, symbol);
  try {
    const stat = await fs.stat(dir);
    if (!stat.isDirectory()) return null;
  } catch {
    return null;
  }
  const [fundamentals, technicals, closes, briefing] = await Promise.all([
    readJson<Fundamentals>(path.join(dir, "fundamentals.json")),
    readJson<Technicals>(path.join(dir, "technicals.json")),
    readLastTwoCloses(path.join(dir, "price_history.csv")),
    readJson<Briefing>(path.join(dir, "briefing.json")),
  ]);
  const info = fundamentals?.info;
  const latest = closes.latest ?? technicals?.close ?? null;
  const prev = closes.prev;
  const changePct =
    latest != null && prev != null && prev !== 0 ? ((latest - prev) / prev) * 100 : null;

  const plan = briefing?.action_plan ?? null;
  const entry = plan?.entry_limit ?? null;
  const toEntryPct =
    entry != null && latest != null && latest !== 0
      ? ((entry - latest) / latest) * 100
      : null;

  return {
    symbol,
    name: info?.name ?? symbol,
    sector: info?.sector ?? null,
    market: info?.market ?? watch?.market ?? "—",
    currency: info?.currency ?? "USD",
    price: latest,
    priceChangePct: changePct,

    signal: briefing?.overall_signal ?? null,
    conviction: briefing?.conviction?.score ?? null,
    convergence: briefing?.conviction?.signal_convergence ?? null,
    briefingDate: briefing?.date ?? null,
    briefingAgeDays: ageInDays(briefing?.date),

    entryLimit: entry,
    stopLoss: plan?.stop_loss ?? null,
    takeProfit1: plan?.take_profit_1 ?? null,
    toEntryPct,
    riskReward: parseRatio(briefing?.risk_assessment?.risk_reward_ratio),

    peRatio: info?.pe_ratio ?? null,
    rsi14: technicals?.rsi_14 ?? null,
    pctFrom52wHigh: technicals?.pct_from_52w_high ?? null,
    asOfDate: technicals?.as_of_date ?? closes.latestDate ?? null,

    group: watch?.group ?? null,
    theme: watch?.theme ?? null,
  };
}

export const listTickerSummaries = cache(async (): Promise<TickerSummary[]> => {
  assertAnalysisApiConfiguration();
  if (ANALYSIS_API_CONFIGURED) return listTickerSummariesFromApi();
  if (CLOUD_CONFIGURED) {
    const [rows, watchMap] = await Promise.all([
      cloudRowsAll<CloudSummaryRow>("latest_ticker_summary", {
        select: "*",
        order: "symbol.asc",
      }),
      loadWatchlistMap(),
    ]);
    return rows.map((row) => summaryFromCloud(row, watchMap[row.symbol]));
  }
  const [tickers, watchMap] = await Promise.all([listTickers(), loadWatchlistMap()]);
  const results = await mapWithConcurrency(tickers, SUMMARY_CONCURRENCY, (symbol) =>
    loadTickerSummary(symbol, watchMap[symbol]),
  );
  return results.filter((s): s is TickerSummary => s !== null);
});
