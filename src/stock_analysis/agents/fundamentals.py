from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.evidence import financials_are_usable
from stock_analysis.models.agent_reports import Confidence, FundamentalsReport, Signal
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


class FundamentalsAgent(BaseAnalystAgent):
    name = "fundamentals"
    description = "Analyzes financial statements, valuation metrics, and balance sheet health"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    async def analyze(self, ticker_data: TickerData) -> FundamentalsReport:
        """Fail closed when no dated financial statement evidence exists."""
        financials = ticker_data.financials
        if not financials_are_usable(financials, ticker_data.fetched_at.date()):
            return FundamentalsReport(
                signal=Signal.NEUTRAL,
                confidence=Confidence.LOW,
                pe_assessment="Unavailable: no financial statement evidence.",
                margin_analysis="Unavailable: no financial statement evidence.",
                debt_analysis="Unavailable: no balance-sheet evidence.",
                growth_outlook="Unavailable: no dated financial statement evidence.",
                key_risks=["Point-in-time fundamental data is unavailable."],
                key_strengths=[],
                summary="Fundamental evidence is unavailable; no directional view is assigned.",
            )
        report = await super().analyze(ticker_data)
        return self.canonicalize_report(report, ticker_data)

    @staticmethod
    def canonicalize_report(
        report: FundamentalsReport,
        ticker_data: TickerData,
    ) -> FundamentalsReport:
        """Cap confidence when fewer than two independent inputs are present."""

        financials = ticker_data.financials
        if not financials_are_usable(financials, ticker_data.fetched_at.date()):
            return report.model_copy(update={"signal": Signal.NEUTRAL, "confidence": Confidence.LOW})

        assert financials is not None
        independent_inputs = sum(
            (
                int(
                    ticker_data.info.pe_ratio is not None
                    or ticker_data.info.forward_pe is not None
                ),
                int(
                    any(
                        value is not None
                        for value in (
                            financials.gross_margin,
                            financials.operating_margin,
                            financials.net_margin,
                        )
                    )
                ),
                int(
                    financials.total_debt is not None
                    or financials.total_equity is not None
                ),
                int(financials.free_cash_flow is not None),
                int(
                    financials.revenue is not None
                    or financials.net_income is not None
                ),
            )
        )
        if independent_inputs < 2:
            return report.model_copy(update={"confidence": Confidence.LOW})
        return report

    def system_prompt(self) -> str:
        return (
            "You are a senior equity research analyst specializing in fundamental analysis. "
            "You evaluate companies based on financial statements, valuation metrics, "
            "balance sheet health, and growth trajectory.\n\n"
            "Guidelines:\n"
            "- Be precise with numbers — cite only metrics returned by the tools; never invent a sector average or missing value\n"
            "- The financials tool may contain only one statement period; never claim a trend or year-over-year change unless multiple periods are explicitly provided\n"
            "- Treat missing P/E, market cap, analyst targets, and valuation inputs as unavailable; do not estimate them\n"
            "- Assess margins, debt, cash flow, and growth only from observed values, and label any interpretation as inference\n"
            "- Identify key risks and strengths based on the financial data\n"
            "- If fewer than two independent fundamental signals are available, prefer neutral/low confidence\n"
            "- Provide a clear signal (strong_buy/buy/neutral/sell/strong_sell) with confidence level\n"
            "- Keep your summary concise (2-3 sentences)"
        )

    def output_model(self) -> type[BaseModel]:
        return FundamentalsReport

    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]:
        @tool(
            "get_ticker_info",
            "Get basic info: symbol, name, sector, market cap, P/E, beta, 52-week range, dividend yield",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_ticker_info(args: dict) -> dict:
            info = ticker_data.info
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(info.model_dump(), default=str),
                    }
                ]
            }

        @tool(
            "get_financials",
            "Get financial statements: revenue, net income, margins, debt, equity, free cash flow",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_financials(args: dict) -> dict:
            if ticker_data.financials is None:
                text = "Financial data not available for this ticker."
            else:
                text = json.dumps(ticker_data.financials.model_dump(), default=str)
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "get_analyst_targets",
            "Get recent analyst recommendations and price targets",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_analyst_targets(args: dict) -> dict:
            recs = ticker_data.analyst_recommendations or []
            if not recs:
                text = "No analyst recommendations available."
            else:
                text = json.dumps(recs, default=str)
            return {"content": [{"type": "text", "text": text}]}

        return [get_ticker_info, get_financials, get_analyst_targets]
