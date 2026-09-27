from __future__ import annotations

import json
import math
import statistics
from itertools import pairwise

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.models.agent_reports import TechnicalReport
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


def _bar_return(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    base = closes[-1 - lookback]
    if not math.isfinite(base) or base == 0:
        return None
    return round(closes[-1] / base - 1, 4)


def _bar_high(closes: list[float], lookback: int) -> float | None:
    window = closes[-lookback:] if len(closes) >= lookback else closes
    return round(max(window), 4) if window else None


def _bar_low(closes: list[float], lookback: int) -> float | None:
    window = closes[-lookback:] if len(closes) >= lookback else closes
    return round(min(window), 4) if window else None


def _daily_volatility(closes: list[float], lookback: int) -> float | None:
    window = closes[-lookback - 1 :]
    returns = [
        current / previous - 1
        for previous, current in pairwise(window)
        if previous and math.isfinite(previous) and math.isfinite(current)
    ]
    if len(returns) < 2:
        return None
    return round(statistics.pstdev(returns), 4)


def build_indicator_payload(ticker_data: TickerData) -> dict:
    """Return the exact deterministic indicator snapshot used downstream.

    Keeping this adapter next to the analyst tool makes it impossible for the
    LLM-facing layer and the deterministic risk layer to silently use two
    different MACD/RSI implementations.
    """
    snapshot = compute_technicals(
        ticker_data.info.symbol,
        ticker_data.price_history,
    )
    closes = [bar.close for bar in ticker_data.price_history]
    highs = [bar.high for bar in ticker_data.price_history]
    lows = [bar.low for bar in ticker_data.price_history]
    return {
        "as_of_date": snapshot.as_of_date.isoformat(),
        "rsi_14": snapshot.rsi_14,
        "macd": {
            "macd_line": snapshot.macd_line,
            "signal_line": snapshot.macd_signal,
            "histogram": snapshot.macd_histogram,
        },
        "sma_20": snapshot.sma_20,
        "sma_50": snapshot.sma_50,
        "sma_200": snapshot.sma_200,
        "ema_20": snapshot.ema_20,
        "current_price": snapshot.close,
        "price_vs_sma50": (
            f"{'above' if snapshot.above_sma_50 else 'below'} by "
            f"{abs(round((snapshot.close / snapshot.sma_50 - 1) * 100, 2))}%"
            if snapshot.sma_50 is not None
            else None
        ),
        "price_vs_sma200": (
            f"{'above' if snapshot.above_sma_200 else 'below'} by "
            f"{abs(round((snapshot.close / snapshot.sma_200 - 1) * 100, 2))}%"
            if snapshot.sma_200 is not None
            else None
        ),
        "atr_14": snapshot.atr_14,
        "bollinger": {
            "upper": snapshot.bb_upper,
            "middle": snapshot.bb_middle,
            "lower": snapshot.bb_lower,
            "pct": snapshot.bb_pct,
        },
        "volume": {
            "current": snapshot.volume,
            "sma_20": snapshot.volume_sma_20,
            "ratio": snapshot.volume_ratio,
        },
        "52_week": {
            "high": snapshot.high_52w,
            "low": snapshot.low_52w,
            "pct_from_high": snapshot.pct_from_52w_high,
            "pct_from_low": snapshot.pct_from_52w_low,
        },
        "price_momentum": {
            "return_5_bars": _bar_return(closes, 5),
            "return_20_bars": _bar_return(closes, 20),
            "return_60_bars": _bar_return(closes, 60),
            "return_252_bars": _bar_return(closes, 252),
        },
        "observed_levels": {
            "20_bar_high": _bar_high(highs, 20),
            "20_bar_low": _bar_low(lows, 20),
            "60_bar_high": _bar_high(highs, 60),
            "60_bar_low": _bar_low(lows, 60),
        },
        "risk_context": {
            "daily_volatility_20_bars": _daily_volatility(closes, 20),
        },
    }


def _normalise_levels(
    levels: list[float],
    *,
    lower_bound: float,
    upper_bound: float,
) -> list[float]:
    """Keep model-proposed levels inside the observed OHLC range."""

    clean = {
        round(level, 4)
        for level in levels
        if math.isfinite(level) and lower_bound <= level <= upper_bound
    }
    return sorted(clean)


def canonicalize_technical_report(
    report: TechnicalReport,
    ticker_data: TickerData,
) -> TechnicalReport:
    """Make factual technical fields deterministic after the LLM explains them.

    RSI is a canonical indicator, not a writing choice. Support/resistance are
    still model-selected, but values outside every observed bar are discarded
    rather than exposed as precise-looking invented levels.
    """

    snapshot = compute_technicals(ticker_data.info.symbol, ticker_data.price_history)
    lower_bound = min(bar.low for bar in ticker_data.price_history)
    upper_bound = max(bar.high for bar in ticker_data.price_history)
    return report.model_copy(
        update={
            "rsi_14": snapshot.rsi_14,
            "support_levels": _normalise_levels(
                report.support_levels,
                lower_bound=lower_bound,
                upper_bound=min(upper_bound, snapshot.close),
            ),
            "resistance_levels": _normalise_levels(
                report.resistance_levels,
                lower_bound=snapshot.close,
                upper_bound=upper_bound,
            ),
        }
    )


class TechnicalAgent(BaseAnalystAgent):
    name = "technical"
    description = "Analyzes price action, momentum indicators, volume patterns, and support/resistance"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    async def analyze(self, ticker_data: TickerData) -> TechnicalReport:
        report = await super().analyze(ticker_data)
        return canonicalize_technical_report(report, ticker_data)

    def system_prompt(self) -> str:
        return (
            "You are a quantitative technical analyst. You evaluate price action, momentum "
            "indicators, volume patterns, and support/resistance levels.\n\n"
            "Guidelines:\n"
            "- Base conclusions on the computed indicators provided, not opinions\n"
            "- Interpret RSI: >70 overbought, <30 oversold, context matters\n"
            "- Interpret MACD: positive histogram = bullish momentum, negative = bearish\n"
            "- Compare current price to SMA-50 and SMA-200 for trend direction\n"
            "- Use ATR-14 and Bollinger Bands to distinguish volatility from trend\n"
            "- Check volume ratio and 52-week distance for confirmation, not as standalone signals\n"
            "- Use the provided trading-bar returns and observed highs/lows as descriptive context, not as guaranteed forecasts\n"
            "- Identify key support/resistance from recent highs/lows; do not invent levels outside the observed range without saying so\n"
            "- If the history is too short for an indicator, treat it as unavailable rather than estimating it\n"
            "- Provide a clear signal with confidence level\n"
            "- Keep your summary concise (2-3 sentences)"
        )

    def output_model(self) -> type[BaseModel]:
        return TechnicalReport

    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]:
        closes = [bar.close for bar in ticker_data.price_history]
        volumes = [bar.volume for bar in ticker_data.price_history]
        indicators = build_indicator_payload(ticker_data)

        @tool(
            "get_price_summary",
            "Get price history summary: latest price, 52-week range, recent trend",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_price_summary(args: dict) -> dict:
            recent_20 = ticker_data.price_history[-20:] if len(ticker_data.price_history) >= 20 else ticker_data.price_history
            summary = {
                "latest_close": closes[-1] if closes else None,
                "latest_date": str(ticker_data.price_history[-1].date) if ticker_data.price_history else None,
                "total_bars": len(closes),
                "period_high": max(closes) if closes else None,
                "period_low": min(closes) if closes else None,
                "recent_20_days": [
                    {"date": str(b.date), "close": b.close, "volume": b.volume}
                    for b in recent_20
                ],
                "avg_volume_30d": (
                    round(sum(volumes[-30:]) / min(30, len(volumes)))
                    if volumes
                    else None
                ),
            }
            return {"content": [{"type": "text", "text": json.dumps(summary, default=str)}]}

        @tool(
            "get_computed_indicators",
            "Get pre-computed technical indicators: RSI-14, MACD(12,26,9), SMA-50, SMA-200",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_computed_indicators(args: dict) -> dict:
            return {"content": [{"type": "text", "text": json.dumps(indicators, default=str)}]}

        return [get_price_summary, get_computed_indicators]
