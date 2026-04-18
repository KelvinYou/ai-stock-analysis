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


class TickerData(BaseModel):
    """Complete data package for one ticker on one date — input to all agents."""

    info: TickerInfo
    price_history: list[PriceBar]
    financials: FinancialStatements | None = None
    analyst_recommendations: list[dict] | None = None
    news_headlines: list[dict] | None = None
    fetched_at: datetime
