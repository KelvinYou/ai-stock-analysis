import type { Confidence, Signal } from "./signals";

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
