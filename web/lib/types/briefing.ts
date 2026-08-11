import type { Signal } from "./signals";
import type { Fundamentals, PricePoint, Technicals } from "./market";
import type { AnalystReports } from "./analysts";
import type { DebateResult } from "./debate";
import type { WatchGroup } from "./watchlist";

export interface ConvictionScore {
  score: number;
  signal_convergence: number;
  explanation: string;
}

export interface RiskAssessment {
  position_size_suggestion: string;
  correlation_notes: string[];
  max_drawdown_scenario: string;
  risk_reward_ratio: string | null;
}

export interface ActionPlan {
  entry_limit: number | null;
  entry_rationale: string | null;
  stop_loss: number | null;
  stop_rationale: string | null;
  take_profit_1: number | null;
  take_profit_2: number | null;
  target_rationale: string | null;
  horizon: string;
  note: string | null;
}

export interface Briefing {
  ticker: string;
  date: string;
  overall_signal: Signal;
  conviction: ConvictionScore;
  executive_summary: string;
  bull_case: string;
  bear_case: string;
  key_uncertainties: string[];
  catalysts_upcoming: string[];
  risk_assessment: RiskAssessment;
  action_plan: ActionPlan | null;
  agent_signal_breakdown: Record<string, string>;
}

export interface TickerBundle {
  symbol: string;
  fundamentals: Fundamentals | null;
  technicals: Technicals | null;
  priceHistory: PricePoint[];
  analystReports: AnalystReports | null;
  debate: DebateResult | null;
  briefing: Briefing | null;
}

/**
 * One row of the screener. Every field here is cheap — it comes from the three
 * JSON files `loadTickerSummary` already reads, so adding a column costs no
 * extra IO. Everything is nullable: 14 of 24 tickers currently have Layer-1
 * data but no briefing, and bearish briefings carry no entry level.
 */
export interface TickerSummary {
  symbol: string;
  name: string;
  sector: string | null;
  market: string;
  currency: string;
  price: number | null;
  priceChangePct: number | null;

  // Briefing (null until the AI pipeline has run for this ticker)
  signal: Signal | null;
  conviction: number | null;
  convergence: number | null;
  briefingDate: string | null;
  /** Days between the briefing date and today — analysis staleness. */
  briefingAgeDays: number | null;

  // Action plan
  entryLimit: number | null;
  stopLoss: number | null;
  takeProfit1: number | null;
  /** (entry − price) / price × 100. Negative = price must still fall to reach entry. */
  toEntryPct: number | null;
  riskReward: number | null;
  positionSize: string | null;

  // Layer-1 screening metrics (present for every fetched ticker)
  peRatio: number | null;
  rsi14: number | null;
  pctFrom52wHigh: number | null;
  /** Latest date the price/technicals snapshot covers — data staleness. */
  asOfDate: string | null;

  // Watchlist metadata from tickers.txt
  group: WatchGroup | null;
  theme: string | null;
}
