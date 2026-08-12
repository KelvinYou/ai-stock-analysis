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

/** Whether to act on the research view — a separate axis from what the view is. */
export type TradeDecision = "approve" | "watch" | "reduce" | "reject";

export interface PositionSizing {
  risk_budget_pct: number | null;
  risk_budget_source: string;
  stop_distance_pct: number | null;
  suggested_position_pct: number | null;
  capped_by: string | null;
  notes: string[];
}

/**
 * `cap_unconfigured` is NOT a pass — it means policy.yaml has no cap to compare
 * against, so the check could not be performed. Render it distinctly from
 * `within_cap` or the UI will imply an approval the backend refused to give.
 */
export type ExposureStatus =
  | "within_cap"
  | "breach"
  | "cap_unconfigured"
  | "holdings_unavailable";

export interface ExposureCheck {
  label: string;
  current_pct: number | null;
  projected_pct: number | null;
  cap_pct: number | null;
  status: ExposureStatus;
  detail: string;
}

export interface PortfolioGateResult {
  decision: TradeDecision;
  reasons: string[];
  sizing: PositionSizing;
  exposures: ExposureCheck[];
  holdings_source: string;
  policy_source: string;
  equity_sleeve_value: number | null;
  valuation_currency: string | null;
  already_held: boolean;
  held_shares: number | null;
}

export interface ResearchVerdict {
  ticker: string;
  judged_view: Signal;
  confidence: "high" | "medium" | "low";
  thesis: string;
  winning_side: "bull" | "bear" | "neither";
  strongest_counterexample: string;
  invalidation_conditions: string[];
  evidence_gaps: string[];
  decisive_factors: string[];
}

export interface Briefing {
  ticker: string;
  date: string;
  overall_signal: Signal;
  /** The research layer's honest view; equals `overall_signal`. Null on briefings written before Layer 5 existed. */
  research_view?: Signal | null;
  /** Layer 5's ruling on whether to act. Null when the gate did not run. */
  trade_decision?: TradeDecision | null;
  conviction: ConvictionScore;
  executive_summary: string;
  bull_case: string;
  bear_case: string;
  key_uncertainties: string[];
  catalysts_upcoming: string[];
  risk_assessment: RiskAssessment;
  action_plan: ActionPlan | null;
  research_verdict?: ResearchVerdict | null;
  portfolio_gate?: PortfolioGateResult | null;
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
