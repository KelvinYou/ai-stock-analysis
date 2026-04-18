from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Signal(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FundamentalsReport(BaseModel):
    signal: Signal
    confidence: Confidence
    pe_assessment: str
    margin_analysis: str
    debt_analysis: str
    growth_outlook: str
    key_risks: list[str]
    key_strengths: list[str]
    summary: str


class SentimentReport(BaseModel):
    signal: Signal
    confidence: Confidence
    news_tone: str
    news_summary: str
    key_themes: list[str]
    notable_headlines: list[str]
    social_sentiment: str | None = None
    summary: str


class TechnicalReport(BaseModel):
    signal: Signal
    confidence: Confidence
    trend: str
    rsi_14: float | None = None
    rsi_assessment: str
    macd_assessment: str
    volume_assessment: str
    support_levels: list[float]
    resistance_levels: list[float]
    summary: str


class MacroFXReport(BaseModel):
    signal: Signal
    confidence: Confidence
    fed_impact: str
    interest_rate_outlook: str
    fx_impact: str | None = None
    sector_macro_factors: list[str]
    geopolitical_risks: list[str]
    summary: str


class AnalystReports(BaseModel):
    """Collected output from all Layer 2 agents."""

    fundamentals: FundamentalsReport
    sentiment: SentimentReport
    technical: TechnicalReport
    macro: MacroFXReport
