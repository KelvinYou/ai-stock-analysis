from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import TechnicalReport
from stock_analysis.models.market_data import PriceBar, TickerData

from .base import BaseAnalystAgent


def compute_sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def compute_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-period:]
    gains = [d for d in recent if d > 0]
    losses = [-d for d in recent if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd(closes: list[float]) -> dict:
    """Compute MACD (12, 26, 9) using simple moving averages as approximation."""
    if len(closes) < 26:
        return {"macd_line": None, "signal_line": None, "histogram": None}
    ema12 = sum(closes[-12:]) / 12
    ema26 = sum(closes[-26:]) / 26
    macd_line = round(ema12 - ema26, 4)
    # Signal line approximated from last 9 MACD values
    if len(closes) >= 35:
        macd_values = []
        for i in range(9):
            offset = 8 - i
            sl = closes[: len(closes) - offset] if offset > 0 else closes
            e12 = sum(sl[-12:]) / 12
            e26 = sum(sl[-26:]) / 26
            macd_values.append(e12 - e26)
        signal_line = round(sum(macd_values) / 9, 4)
    else:
        signal_line = macd_line
    histogram = round(macd_line - signal_line, 4)
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
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
            "- Identify key support/resistance from recent highs/lows\n"
            "- Provide a clear signal with confidence level\n"
            "- Keep your summary concise (2-3 sentences)"
        )

    def output_model(self) -> type[BaseModel]:
        return TechnicalReport

    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]:
        closes = [bar.close for bar in ticker_data.price_history]
        volumes = [bar.volume for bar in ticker_data.price_history]

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
            indicators = {
                "rsi_14": compute_rsi(closes),
                "macd": compute_macd(closes),
                "sma_50": round(compute_sma(closes, 50), 4) if compute_sma(closes, 50) else None,
                "sma_200": round(compute_sma(closes, 200), 4) if compute_sma(closes, 200) else None,
                "current_price": closes[-1] if closes else None,
                "price_vs_sma50": (
                    f"{'above' if closes[-1] > sma50 else 'below'} by {abs(round((closes[-1] / sma50 - 1) * 100, 2))}%"
                    if (sma50 := compute_sma(closes, 50)) and closes
                    else None
                ),
                "price_vs_sma200": (
                    f"{'above' if closes[-1] > sma200 else 'below'} by {abs(round((closes[-1] / sma200 - 1) * 100, 2))}%"
                    if (sma200 := compute_sma(closes, 200)) and closes
                    else None
                ),
            }
            return {"content": [{"type": "text", "text": json.dumps(indicators, default=str)}]}

        return [get_price_summary, get_computed_indicators]
