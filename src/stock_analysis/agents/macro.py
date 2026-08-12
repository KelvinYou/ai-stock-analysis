from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import Confidence, MacroFXReport, Signal
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent

def build_macro_snapshot(ticker_data: TickerData) -> dict:
    """Build a point-in-time macro envelope without inventing unavailable facts.

    The project does not currently ingest dated Fed/BNM/FX observations. An
    explicit unavailable snapshot is safer than feeding every historical trial
    a stale present-day paragraph, which would create both leakage and false
    confidence.
    """
    as_of = ticker_data.fetched_at.date().isoformat()
    return {
        "status": "unavailable",
        "as_of": as_of,
        "source": "not_configured",
        "freshness": "unknown",
        "fed": {
            "fed_funds_rate": None,
            "inflation": None,
        },
        "bnm": {"opr": None},
        "fx": {"usd_myr": None},
        "sector": ticker_data.info.sector,
        "notice": (
            "No dated macro snapshot is configured. Do not infer current or "
            "historical rates, FX, inflation, or geopolitical facts from memory."
        ),
    }


class MacroFXAgent(BaseAnalystAgent):
    name = "macro"
    description = "Analyzes macroeconomic factors, central bank policy, and FX impact"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    async def analyze(self, ticker_data: TickerData) -> MacroFXReport:
        """Return an explicit neutral report until dated macro data is available."""
        snapshot = build_macro_snapshot(ticker_data)
        if snapshot["status"] != "available":
            return MacroFXReport(
                signal=Signal.NEUTRAL,
                confidence=Confidence.LOW,
                fed_impact="Unavailable: no dated Fed snapshot is configured.",
                interest_rate_outlook="Unavailable: no dated rate snapshot is configured.",
                fx_impact="Unavailable: no dated FX snapshot is configured.",
                sector_macro_factors=[],
                geopolitical_risks=[],
                summary="Macro/FX data is unavailable; no directional view is assigned.",
            )
        return await super().analyze(ticker_data)

    def system_prompt(self) -> str:
        return (
            "You are a macroeconomic and FX analyst. You evaluate how central bank policy "
            "(Fed, BNM), interest rate trajectories, currency movements, and geopolitical "
            "factors affect the stock under analysis.\n\n"
            "Guidelines:\n"
            "- Consider the stock's sector sensitivity to macro factors\n"
            "- Assess how current rate environment affects the company's cost of capital\n"
            "- Identify geopolitical risks relevant to the company's operations/supply chain\n"
            "- For Malaysian stocks, specifically consider MYR/USD impact and BNM policy\n"
            "- If the macro tool reports an unavailable snapshot, do not invent facts; "
            "use neutral/low confidence unless dated macro evidence is present\n"
            "- Provide a clear signal with confidence level\n"
            "- Keep your summary concise (2-3 sentences)"
        )

    def output_model(self) -> type[BaseModel]:
        return MacroFXReport

    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]:
        @tool(
            "get_ticker_sector",
            "Get the stock's sector and industry for macro sensitivity mapping",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_ticker_sector(args: dict) -> dict:
            info = {
                "symbol": ticker_data.info.symbol,
                "sector": ticker_data.info.sector,
                "industry": ticker_data.info.industry,
                "market": ticker_data.info.market.value,
                "currency": ticker_data.info.currency,
                "beta": ticker_data.info.beta,
            }
            return {"content": [{"type": "text", "text": json.dumps(info, default=str)}]}

        @tool(
            "get_macro_context",
            "Get the point-in-time macro snapshot; it may explicitly report unavailable data",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_macro_context(args: dict) -> dict:
            snapshot = build_macro_snapshot(ticker_data)
            return {
                "content": [
                    {"type": "text", "text": json.dumps(snapshot, ensure_ascii=False)}
                ]
            }

        return [get_ticker_sector, get_macro_context]
