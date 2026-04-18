import type { Signal } from "./signals";
import type { Fundamentals, PricePoint, Technicals } from "./market";
import type { AnalystReports } from "./analysts";
import type { DebateResult } from "./debate";

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

export interface TickerSummary {
  symbol: string;
  name: string;
  sector: string | null;
  market: string;
  currency: string;
  price: number | null;
  priceChangePct: number | null;
  signal: Signal | null;
  conviction: number | null;
}
