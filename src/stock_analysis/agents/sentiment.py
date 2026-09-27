from __future__ import annotations

import json

from claude_agent_sdk import SdkMcpTool, tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.evidence import (
    current_recommendations_are_usable,
    filter_point_in_time_news,
)
from stock_analysis.models.agent_reports import Confidence, SentimentReport, Signal
from stock_analysis.models.market_data import TickerData

from .base import BaseAnalystAgent


class SentimentAgent(BaseAnalystAgent):
    name = "sentiment"
    description = "Analyzes news headlines, social tone, and market narratives"

    def __init__(self, settings: Settings | None = None):
        s = settings or Settings()
        self.model = s.quick_think_model

    @staticmethod
    def canonicalize_report(
        report: SentimentReport,
        ticker_data: TickerData | None = None,
    ) -> SentimentReport:
        """Keep source-shaped fields deterministic after the LLM explains them."""

        updates = {"social_sentiment": None}
        if ticker_data is not None:
            dated_news = filter_point_in_time_news(
                ticker_data.news_headlines,
                as_of=ticker_data.fetched_at.date(),
            )
            updates["notable_headlines"] = [item["title"] for item in dated_news]
        return report.model_copy(update=updates)

    async def analyze(self, ticker_data: TickerData) -> SentimentReport:
        """Do not ask an LLM to invent sentiment when no dated evidence exists."""
        dated_news = filter_point_in_time_news(
            ticker_data.news_headlines,
            as_of=ticker_data.fetched_at.date(),
        )
        recommendations = (
            ticker_data.analyst_recommendations
            if current_recommendations_are_usable(
                ticker_data.analyst_recommendations,
                ticker_data.fetched_at.date(),
            )
            else []
        )
        if dated_news != (ticker_data.news_headlines or []):
            ticker_data = ticker_data.model_copy(
                update={
                    "news_headlines": dated_news,
                    "analyst_recommendations": recommendations,
                }
            )
        elif recommendations != (ticker_data.analyst_recommendations or []):
            ticker_data = ticker_data.model_copy(
                update={"analyst_recommendations": recommendations}
            )
        if not dated_news and not recommendations:
            return SentimentReport(
                signal=Signal.NEUTRAL,
                confidence=Confidence.LOW,
                news_tone="unavailable",
                news_summary="No point-in-time news or analyst recommendations available.",
                key_themes=[],
                notable_headlines=[],
                social_sentiment=None,
                summary="Sentiment is unavailable; no directional view is assigned.",
            )
        return self.canonicalize_report(await super().analyze(ticker_data), ticker_data)

    def system_prompt(self) -> str:
        return (
            "You are a market sentiment analyst. You evaluate investor sentiment by analyzing "
            "news headlines, analyst recommendations, and market narratives.\n\n"
            "Guidelines:\n"
            "- Use only headlines and recommendations returned by the tools; cite dates, publishers, or rating periods when available\n"
            "- Classify the overall news tone as positive, negative, mixed, or neutral\n"
            "- Identify recurring themes across headlines (e.g., 'AI expansion', 'margin pressure')\n"
            "- Separate the observed event from your inference about price impact; do not treat a single headline as a confirmed trend\n"
            "- There is no social-media tool in this pipeline; set social_sentiment to null rather than inferring it\n"
            "- Highlight any contrarian signals (e.g., extreme bullishness as a warning)\n"
            "- If no dated news or recommendations are available, use neutral/low confidence\n"
            "- Do not use general market knowledge to fill missing or undated news\n"
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
