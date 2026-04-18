import { promises as fs } from "node:fs";
import path from "node:path";
import type {
  AnalystReports,
  Briefing,
  DebateResult,
  Fundamentals,
  PricePoint,
  Technicals,
  TickerBundle,
  TickerSummary,
} from "./types";

const DATA_DIR = process.env.STOCK_DATA_DIR
  ? path.resolve(process.env.STOCK_DATA_DIR)
  : path.resolve(process.cwd(), "..", "data");

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

export async function listTickers(): Promise<string[]> {
  try {
    const entries = await fs.readdir(DATA_DIR, { withFileTypes: true });
    return entries
      .filter((e) => e.isDirectory() && !e.name.startsWith("."))
      .map((e) => e.name)
      .sort();
  } catch {
    return [];
  }
}

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

export async function listTickerSummaries(): Promise<TickerSummary[]> {
  const tickers = await listTickers();
  const bundles = await Promise.all(tickers.map(loadTicker));
  const summaries: TickerSummary[] = [];
  for (const b of bundles) {
    if (!b) continue;
    const info = b.fundamentals?.info;
    const latest = b.priceHistory.at(-1)?.close ?? b.technicals?.close ?? null;
    const prev = b.priceHistory.at(-2)?.close ?? null;
    const changePct = latest != null && prev != null && prev !== 0 ? ((latest - prev) / prev) * 100 : null;
    summaries.push({
      symbol: b.symbol,
      name: info?.name ?? b.symbol,
      sector: info?.sector ?? null,
      market: info?.market ?? "—",
      currency: info?.currency ?? "USD",
      price: latest,
      priceChangePct: changePct,
      signal: b.briefing?.overall_signal ?? null,
      conviction: b.briefing?.conviction?.score ?? null,
    });
  }
  return summaries;
}
