export type Signal = "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell";
export type Confidence = "high" | "medium" | "low";

export interface TickerInfo {
  symbol: string;
  name: string;
  sector: string | null;
  industry: string | null;
  market: string;
  currency: string;
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  dividend_yield: number | null;
  beta: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;
}

export interface Financials {
  revenue: number | null;
  net_income: number | null;
  total_debt: number | null;
  total_equity: number | null;
  free_cash_flow: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
}

export interface AnalystRec {
  index: number;
  period: string;
  strongBuy: number;
  buy: number;
  hold: number;
  sell: number;
  strongSell: number;
}

export interface NewsHeadline {
  title: string;
  link: string;
  publisher: string;
}

export interface Fundamentals {
  info: TickerInfo;
  financials: Financials;
  analyst_recommendations: AnalystRec[];
  news_headlines: NewsHeadline[];
}

export interface Technicals {
  ticker: string;
  as_of_date: string;
  close: number;
  sma_20: number;
  sma_50: number;
  sma_200: number;
  ema_20: number;
  rsi_14: number;
  macd_line: number;
  macd_signal: number;
  macd_histogram: number;
  bb_upper: number;
  bb_middle: number;
  bb_lower: number;
  bb_pct: number;
  atr_14: number;
  volume: number;
  volume_sma_20: number;
  volume_ratio: number;
  high_52w: number;
  low_52w: number;
  pct_from_52w_high: number;
  pct_from_52w_low: number;
  above_sma_20: boolean;
  above_sma_50: boolean;
  above_sma_200: boolean;
}

export interface PricePoint {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FundamentalsReport {
  signal: Signal;
  confidence: Confidence;
  pe_assessment: string;
  margin_analysis: string;
  debt_analysis: string;
  growth_outlook: string;
  key_risks: string[];
  key_strengths: string[];
  summary: string;
}

export interface SentimentReport {
  signal: Signal;
  confidence: Confidence;
  news_tone: string;
  news_summary: string;
  key_themes: string[];
  notable_headlines: string[];
  social_sentiment: string | null;
  summary: string;
}

export interface TechnicalReport {
  signal: Signal;
  confidence: Confidence;
  trend: string;
  rsi_14: number | null;
  rsi_assessment: string;
  macd_assessment: string;
  volume_assessment: string;
  support_levels: number[];
  resistance_levels: number[];
  summary: string;
}

export interface MacroReport {
  signal: Signal;
  confidence: Confidence;
  fed_impact: string;
  interest_rate_outlook: string;
  fx_impact: string | null;
  sector_macro_factors: string[];
  geopolitical_risks: string[];
  summary: string;
}

export interface AnalystReports {
  fundamentals: FundamentalsReport;
  sentiment: SentimentReport;
  technical: TechnicalReport;
  macro: MacroReport;
}

export interface DebateArgument {
  position: "bull" | "bear";
  round_number: number;
  argument: string;
  key_points: string[];
  rebuttal_to_previous: string | null;
}

export interface DebateRound {
  round_number: number;
  bull_argument: DebateArgument;
  bear_argument: DebateArgument;
}

export interface DebateResult {
  ticker: string;
  rounds: DebateRound[];
  bull_case_summary: string;
  bear_case_summary: string;
  key_points_of_agreement: string[];
  key_points_of_disagreement: string[];
  unresolved_uncertainties: string[];
}

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
