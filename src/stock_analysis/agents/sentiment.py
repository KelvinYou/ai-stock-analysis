from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import SentimentReport
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


class SentimentAgent(BaseAnalystAgent):
    name = "sentiment"
    description = "Analyzes news headlines, social tone, and market narratives"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    def system_prompt(self) -> str:
        return (
            "You are a market sentiment analyst. You evaluate investor sentiment by analyzing "
            "news headlines, analyst recommendations, and market narratives.\n\n"
            "Guidelines:\n"
            "- Classify the overall news tone as positive, negative, mixed, or neutral\n"
            "- Identify recurring themes across headlines (e.g., 'AI expansion', 'margin pressure')\n"
            "- Note whether sentiment appears ahead of or behind the fundamentals\n"
            "- Highlight any contrarian signals (e.g., extreme bullishness as a warning)\n"
            "- Provide a clear signal with confidence level\n"
            "- Keep your summary concise (2-3 sentences)"
        )

    def output_model(self) -> type[BaseModel]:
        return SentimentReport

    def build_tools(self, ticker_data: TickerData) -> list[SdkMcpTool]:
        @tool(
            "get_news_headlines",
            "Get recent news headlines for the stock",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_news_headlines(args: dict) -> dict:
            news = ticker_data.news_headlines or []
            if not news:
                text = "No recent news headlines available."
            else:
                text = json.dumps(news, default=str)
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "get_analyst_recommendations",
            "Get recent analyst upgrades, downgrades, and rating changes",
            {"ticker": str},
            annotations=ToolAnnotations(readOnlyHint=True),
        )
        async def get_analyst_recommendations(args: dict) -> dict:
            recs = ticker_data.analyst_recommendations or []
            if not recs:
                text = "No analyst recommendations available."
            else:
                text = json.dumps(recs, default=str)
            return {"content": [{"type": "text", "text": text}]}

        return [get_news_headlines, get_analyst_recommendations]
