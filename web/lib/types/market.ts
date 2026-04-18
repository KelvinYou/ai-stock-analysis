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
