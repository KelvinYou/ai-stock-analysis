from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import FundamentalsReport
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


class FundamentalsAgent(BaseAnalystAgent):
    name = "fundamentals"
    description = "Analyzes financial statements, valuation metrics, and balance sheet health"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    def system_prompt(self) -> str:
        return (
            "You are a senior equity research analyst specializing in fundamental analysis. "
            "You evaluate companies based on financial statements, valuation metrics, "
            "balance sheet health, and growth trajectory.\n\n"
            "Guidelines:\n"
            "- Be precise with numbers — cite specific metrics (e.g., 'P/E of 28.3x vs sector avg 22x')\n"
            "- Assess margin trends and debt levels relative to the company's size and sector\n"
            "- Identify key risks and strengths based on the financial data\n"
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
