"""Shared, evidence-aware context renderers for the LLM layers.

The analyst reports are typed objects, but the debate and synthesis layers used
to receive hand-picked summaries rather than the complete reports. That made
quality depend on which fields happened to be copied into each prompt. This
module keeps the prompt contract in one place and adds a small deterministic
provenance envelope so later layers can distinguish unavailable evidence from a
neutral view.
"""

from __future__ import annotations

import json
from typing import Any

from stock_analysis.data.evidence import (
    current_recommendations_are_usable,
    filter_point_in_time_news,
    financials_are_usable,
    financials_have_evidence,
    macro_snapshot_is_usable,
)
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.market_data import TickerData


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str)


def build_evidence_envelope(ticker_data: TickerData) -> str:
    """Render deterministic data provenance without exposing future prices."""

    analysis_as_of = ticker_data.fetched_at.date()
    price_as_of = ticker_data.price_history[-1].date if ticker_data.price_history else None
    financials = ticker_data.financials
    dated_news = filter_point_in_time_news(
        ticker_data.news_headlines,
        as_of=analysis_as_of,
        max_age_days=ticker_data.news_max_age_days,
    )
    snapshot = ticker_data.macro_snapshot

    if financials is None or not financials_have_evidence(financials):
        fundamentals_status = "unavailable"
    elif not financials_are_usable(financials, analysis_as_of):
        fundamentals_status = "future_or_invalid"
    elif financials.available_as_of is None:
        fundamentals_status = "present_but_availability_unknown"
    else:
        fundamentals_status = "available"

    macro_available = macro_snapshot_is_usable(snapshot, analysis_as_of)

    envelope = {
        "analysis_as_of": analysis_as_of.isoformat(),
        "price_data_as_of": price_as_of.isoformat() if price_as_of else None,
        "price_bar_count": len(ticker_data.price_history),
        "fundamentals": {
            "status": fundamentals_status,
            "fiscal_period_end": (
                financials.fiscal_period_end.isoformat()
                if financials and financials.fiscal_period_end
                else None
            ),
            "available_as_of": (
                financials.available_as_of.isoformat()
                if financials and financials.available_as_of
                else None
            ),
            "source": financials.availability_source if financials else None,
        },
        "sentiment": {
            "dated_news_count": len(dated_news),
            "recommendation_count": (
                len(ticker_data.analyst_recommendations or [])
                if current_recommendations_are_usable(
                    ticker_data.analyst_recommendations,
                    analysis_as_of,
                    provider_capture=ticker_data.provider_capture,
                )
                else 0
            ),
            "note": (
                "Only dated news is evidence-backed. Undated recommendations are usable only "
                "for a current snapshot, never for historical replay."
            ),
        },
        "macro": {
            "status": "available" if macro_available else "unavailable",
            "as_of_date": snapshot.as_of_date.isoformat() if snapshot else None,
            "available_as_of": snapshot.available_as_of.isoformat() if snapshot else None,
            "source": snapshot.source if snapshot and macro_available else "not_configured",
        },
        "rules": [
            "Treat unavailable or unknown evidence as unavailable, not as a bearish or bullish fact.",
            "Do not use knowledge that is newer than analysis_as_of.",
            "Separate observed data from inference and label uncertainty explicitly.",
        ],
    }
    return _json(envelope)


def build_analyst_reports_context(analyst_reports: AnalystReports) -> str:
    """Render every typed analyst field for downstream adjudication.

    Keeping this as JSON makes omissions visible in review and prevents a new
    report field from silently disappearing from debate/synthesis prompts.
    """

    payload = analyst_reports.model_dump(mode="json")
    return _json(payload)
