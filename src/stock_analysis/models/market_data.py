from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class Market(str, Enum):
    US = "US"
    MY = "MY"


class PriceBar(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class FinancialStatements(BaseModel):
    revenue: float | None = None
    net_income: float | None = None
    total_debt: float | None = None
    total_equity: float | None = None
    free_cash_flow: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None


class TickerInfo(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    industry: str | None = None
    market: Market
    currency: str
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    dividend_yield: float | None = None
    beta: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None


class TechnicalSnapshot(BaseModel):
    """Latest technical indicator values computed from price history."""

    ticker: str
    as_of_date: date

    close: float

    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    ema_20: float | None = None

    rsi_14: float | None = None

    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None

    bb_upper: float | None = None
    bb_middle: float | None = None
    bb_lower: float | None = None
    bb_pct: float | None = None  # 0 = at lower band, 1 = at upper band

    atr_14: float | None = None

    volume: int
    volume_sma_20: float | None = None
    volume_ratio: float | None = None  # current / sma_20

    high_52w: float | None = None
    low_52w: float | None = None
    pct_from_52w_high: float | None = None  # negative = below high
    pct_from_52w_low: float | None = None   # positive = above low

    above_sma_20: bool | None = None
    above_sma_50: bool | None = None
    above_sma_200: bool | None = None


class TickerData(BaseModel):
    """Complete data package for one ticker on one date — input to all agents."""

    info: TickerInfo
    price_history: list[PriceBar]
    financials: FinancialStatements | None = None
    analyst_recommendations: list[dict] | None = None
    news_headlines: list[dict] | None = None
    fetched_at: datetime
