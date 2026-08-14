import { promises as fs } from "node:fs";
import path from "node:path";
import { cache } from "react";
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
  WatchlistEntry,
} from "./types";
import { parseRatio } from "./format";

const DATA_DIR = process.env.STOCK_DATA_DIR
  ? path.resolve(process.env.STOCK_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");

const SUMMARY_CONCURRENCY = 16;

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
  const [tickers, watchMap] = await Promise.all([listTickers(), loadWatchlistMap()]);
  const results = await mapWithConcurrency(tickers, SUMMARY_CONCURRENCY, (symbol) =>
    loadTickerSummary(symbol, watchMap[symbol]),
  );
  return results.filter((s): s is TickerSummary => s !== null);
});
