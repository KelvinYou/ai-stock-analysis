from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import MacroFXReport
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent

# Initial hardcoded macro context — will be replaced with live API data later
MACRO_CONTEXT = """
## Current Macro Environment (as of April 2026)

### US Federal Reserve
- Fed funds rate: 4.25-4.50% (holding steady)
- Inflation (CPI): trending toward 2% target
- Next FOMC meeting: upcoming — market expects hold
- Quantitative tightening: ongoing, pace reduced

### Global
- US GDP growth: moderate (~2%)
- US unemployment: low (~4%)
- China: mixed recovery signals
- Geopolitical: trade tensions remain elevated

### Malaysia (BNM)
- OPR: 3.00%
- MYR/USD: ~4.30-4.40 range
- BNM stance: accommodative, focused on growth
- Inflation: moderate

### Sector Sensitivity Notes
- Tech: sensitive to rate expectations, AI capex cycle
- Financials: benefit from higher-for-longer rates
- Energy: oil price volatility, geopolitical premium
- Consumer: inflation impact on spending
- Healthcare: defensive, less rate-sensitive
"""


class MacroFXAgent(BaseAnalystAgent):
    name = "macro"
    description = "Analyzes macroeconomic factors, central bank policy, and FX impact"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

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
            "Get current macroeconomic environment: Fed/BNM rates, inflation, GDP, FX, geopolitical factors",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_macro_context(args: dict) -> dict:
            return {"content": [{"type": "text", "text": MACRO_CONTEXT}]}

        return [get_ticker_sector, get_macro_context]
