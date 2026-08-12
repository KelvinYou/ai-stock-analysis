from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.models.agent_reports import TechnicalReport
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


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
    }


class TechnicalAgent(BaseAnalystAgent):
    name = "technical"
    description = "Analyzes price action, momentum indicators, volume patterns, and support/resistance"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

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
            "- Identify key support/resistance from recent highs/lows\n"
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
