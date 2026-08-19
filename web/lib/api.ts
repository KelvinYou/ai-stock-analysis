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
import { FETCH_REVALIDATE_SECONDS } from "./site";

/** Server-side FastAPI reader. Never expose these variables as NEXT_PUBLIC_*. */
const API_URL = (process.env.STOCK_ANALYSIS_API_URL ?? "").replace(/\/+$/, "");
const API_TOKEN = process.env.STOCK_ANALYSIS_API_TOKEN ?? "";

export const ANALYSIS_API_CONFIGURED = Boolean(API_URL && API_TOKEN);
export const ANALYSIS_API_MISCONFIGURED = Boolean(API_URL || API_TOKEN) && !ANALYSIS_API_CONFIGURED;

export function assertAnalysisApiConfiguration(): void {
  if (ANALYSIS_API_MISCONFIGURED) {
    throw new Error(
      "FastAPI web configuration must set both STOCK_ANALYSIS_API_URL and STOCK_ANALYSIS_API_TOKEN",
    );
  }
}

type ApiTickerSummary = {
  symbol: string;
  name: string;
  sector: string | null;
  market: string;
  currency: string;
  price: number | null;
  price_change_pct: number | null;
  signal: TickerSummary["signal"];
  conviction: number | null;
  convergence: number | null;
  briefing_date: string | null;
  briefing_age_days: number | null;
  entry_limit: number | null;
  stop_loss: number | null;
  take_profit_1: number | null;
  to_entry_pct: number | null;
  risk_reward: number | null;
  pe_ratio: number | null;
  rsi_14: number | null;
  pct_from_52w_high: number | null;
  as_of_date: string | null;
  theme: string | null;
};

type ApiWatchlistEntry = {
  symbol: string;
  market: WatchlistEntry["market"];
  theme: string | null;
};

type ApiTickerBundle = {
  symbol: string;
  fundamentals: Fundamentals | null;
  technicals: Technicals | null;
  price_history: PricePoint[];
  analyst_reports: AnalystReports | null;
  debate: DebateResult | null;
  briefing: Briefing | null;
};

function asRecord(value: unknown, context: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`FastAPI ${context} returned an invalid JSON object`);
  }
  return value as Record<string, unknown>;
}

function asArray(value: unknown, context: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`FastAPI ${context} returned an invalid JSON array`);
  }
  return value;
}

async function apiGet<T>(pathname: string, allowNotFound = false): Promise<T | null> {
  assertAnalysisApiConfiguration();
  if (!ANALYSIS_API_CONFIGURED) {
    throw new Error("FastAPI web configuration is missing");
  }
  const response = await fetch(`${API_URL}${pathname}`, {
    headers: { Authorization: `Bearer ${API_TOKEN}` },
    next: { revalidate: FETCH_REVALIDATE_SECONDS },
  });
  if (allowNotFound && response.status === 404) return null;
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const error = body && typeof body === "object" ? (body as { error?: { message?: string } }).error : null;
    throw new Error(error?.message ?? `FastAPI ${pathname} failed (${response.status})`);
  }
  return (await response.json()) as T;
}

function mapSummary(raw: ApiTickerSummary): TickerSummary {
  return {
    symbol: raw.symbol,
    name: raw.name,
    sector: raw.sector,
    market: raw.market,
    currency: raw.currency,
    price: raw.price,
    priceChangePct: raw.price_change_pct,
    signal: raw.signal,
    conviction: raw.conviction,
    convergence: raw.convergence,
    briefingDate: raw.briefing_date,
    briefingAgeDays: raw.briefing_age_days,
    entryLimit: raw.entry_limit,
    stopLoss: raw.stop_loss,
    takeProfit1: raw.take_profit_1,
    toEntryPct: raw.to_entry_pct,
    riskReward: raw.risk_reward,
    peRatio: raw.pe_ratio,
    rsi14: raw.rsi_14,
    pctFrom52wHigh: raw.pct_from_52w_high,
    asOfDate: raw.as_of_date,
    theme: raw.theme,
  };
}

function mapBundle(raw: ApiTickerBundle): TickerBundle {
  return {
    symbol: raw.symbol,
    fundamentals: raw.fundamentals,
    technicals: raw.technicals,
    priceHistory: raw.price_history,
    analystReports: raw.analyst_reports,
    debate: raw.debate,
    briefing: raw.briefing,
  };
}

export async function listTickerSummariesFromApi(): Promise<TickerSummary[]> {
  const payload = await apiGet<unknown>("/api/v1/tickers");
  return asArray(payload, "ticker summaries").map((row) => mapSummary(asRecord(row, "ticker summary") as unknown as ApiTickerSummary));
}

export async function loadWatchlistFromApi(): Promise<WatchlistEntry[]> {
  const payload = await apiGet<unknown>("/api/v1/watchlist");
  return asArray(payload, "watchlist").map((row) =>
    asRecord(row, "watchlist entry") as unknown as ApiWatchlistEntry,
  );
}

export async function loadTickerFromApi(symbol: string): Promise<TickerBundle | null> {
  const payload = await apiGet<unknown>(`/api/v1/tickers/${encodeURIComponent(symbol)}`, true);
  if (payload === null) return null;
  return mapBundle(asRecord(payload, "ticker bundle") as unknown as ApiTickerBundle);
}
