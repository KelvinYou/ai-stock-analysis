"""Public read adapter shared by the FastAPI dashboard endpoints.

The web dashboard consumes this module's Pydantic models through HTTP rather
than reading Supabase directly.  The service deliberately returns only the
public, completed analysis surface; queue state and service credentials stay
behind the control-plane seam.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.data.cloud import SupabaseAnalysisStore
from stock_analysis.data.store import DataStore
from stock_analysis.data.watchlist import parse_watchlist
from stock_analysis.models.agent_reports import AnalystReports, Signal
from stock_analysis.models.debate import DebateResult
from stock_analysis.models.market_data import (
    FinancialStatements,
    PriceBar,
    TechnicalSnapshot,
    TickerData,
    TickerInfo,
)
from stock_analysis.models.synthesis import Briefing


class PublicFundamentals(BaseModel):
    info: TickerInfo
    financials: FinancialStatements | None = None
    analyst_recommendations: list[dict[str, Any]] | None = None
    news_headlines: list[dict[str, Any]] | None = None


class WatchlistEntryResponse(BaseModel):
    symbol: str
    market: Literal["US", "MY"]
    theme: str | None = None


class TickerSummaryResponse(BaseModel):
    symbol: str
    name: str
    sector: str | None = None
    market: str
    currency: str
    price: float | None = None
    price_change_pct: float | None = None
    signal: Signal | None = None
    conviction: float | None = None
    convergence: float | None = None
    briefing_date: str | None = None
    briefing_age_days: int | None = None
    entry_limit: float | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    to_entry_pct: float | None = None
    risk_reward: float | None = None
    pe_ratio: float | None = None
    rsi_14: float | None = None
    pct_from_52w_high: float | None = None
    as_of_date: str | None = None
    theme: str | None = None


class TickerBundleResponse(BaseModel):
    symbol: str
    fundamentals: PublicFundamentals | None = None
    technicals: TechnicalSnapshot | None = None
    price_history: list[PriceBar] = Field(default_factory=list)
    analyst_reports: AnalystReports | None = None
    debate: DebateResult | None = None
    briefing: Briefing | None = None


_RATIO_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)")
TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,14}$")


def normalize_ticker(symbol: str) -> str:
    """Normalize a route ticker and reject values unsafe for local paths."""
    normalized = symbol.strip().upper()
    if not TICKER_RE.fullmatch(normalized):
        raise ValueError("ticker must contain only letters, digits, dots, or hyphens")
    return normalized


def _age_in_days(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return max(0, (date.today() - date.fromisoformat(value[:10])).days)
    except ValueError:
        return None


def _parse_ratio(value: str | None) -> float | None:
    if not value:
        return None
    match = _RATIO_RE.match(value)
    if not match:
        return None
    denominator = float(match.group(2))
    return float(match.group(1)) / denominator if denominator else None


def _public_fundamentals(data: TickerData | None) -> PublicFundamentals | None:
    if data is None:
        return None
    return PublicFundamentals(
        info=data.info,
        financials=data.financials,
        analyst_recommendations=data.analyst_recommendations,
        news_headlines=data.news_headlines,
    )


def _summary_from_cloud(
    row: dict[str, Any],
) -> TickerSummaryResponse:
    price = row.get("price")
    previous = row.get("previous_price")
    price_change_pct = (
        (float(price) - float(previous)) / float(previous) * 100
        if price is not None and previous is not None and float(previous) != 0
        else None
    )
    entry = row.get("entry_limit")
    to_entry_pct = (
        (float(entry) - float(price)) / float(price) * 100
        if entry is not None and price is not None and float(price) != 0
        else None
    )
    return TickerSummaryResponse(
        symbol=row["symbol"],
        name=row.get("info_name") or row.get("name") or row["symbol"],
        sector=row.get("sector"),
        market=row.get("market") or "—",
        currency=row.get("currency") or "USD",
        price=price,
        price_change_pct=price_change_pct,
        signal=row.get("signal"),
        conviction=row.get("conviction"),
        convergence=row.get("convergence"),
        briefing_date=row.get("briefing_date"),
        briefing_age_days=_age_in_days(row.get("briefing_date")),
        entry_limit=entry,
        stop_loss=row.get("stop_loss"),
        take_profit_1=row.get("take_profit_1"),
        to_entry_pct=to_entry_pct,
        risk_reward=_parse_ratio(row.get("risk_reward")),
        pe_ratio=row.get("pe_ratio"),
        rsi_14=row.get("rsi_14"),
        pct_from_52w_high=row.get("pct_from_52w_high"),
        as_of_date=row.get("market_as_of_date") or row.get("latest_price_date"),
        theme=row.get("theme"),
    )


def _summary_from_local(
    symbol: str,
    data: TickerData | None,
    technicals: TechnicalSnapshot | None,
    briefing: Briefing | None,
) -> TickerSummaryResponse:
    bars = data.price_history if data else []
    price = bars[-1].close if bars else (technicals.close if technicals else None)
    previous = bars[-2].close if len(bars) >= 2 else None
    change = (
        (price - previous) / previous * 100
        if price is not None and previous not in (None, 0)
        else None
    )
    plan = briefing.action_plan if briefing else None
    entry = plan.entry_limit if plan else None
    to_entry = (
        (entry - price) / price * 100
        if entry is not None and price not in (None, 0)
        else None
    )
    return TickerSummaryResponse(
        symbol=symbol,
        name=data.info.name if data else symbol,
        sector=data.info.sector if data else None,
        market=data.info.market.value if data else "—",
        currency=data.info.currency if data else "USD",
        price=price,
        price_change_pct=change,
        signal=briefing.overall_signal if briefing else None,
        conviction=briefing.conviction.score if briefing else None,
        convergence=briefing.conviction.signal_convergence if briefing else None,
        briefing_date=briefing.date if briefing else None,
        briefing_age_days=_age_in_days(briefing.date) if briefing else None,
        entry_limit=entry,
        stop_loss=plan.stop_loss if plan else None,
        take_profit_1=plan.take_profit_1 if plan else None,
        to_entry_pct=to_entry,
        risk_reward=_parse_ratio(briefing.risk_assessment.risk_reward_ratio)
        if briefing
        else None,
        pe_ratio=data.info.pe_ratio if data else None,
        rsi_14=technicals.rsi_14 if technicals else None,
        pct_from_52w_high=technicals.pct_from_52w_high if technicals else None,
        as_of_date=(technicals.as_of_date.isoformat() if technicals else None)
        or (bars[-1].date.isoformat() if bars else None),
    )


class PublicReadService:
    """Load public dashboard data from Supabase or the offline data store."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _cloud(self) -> SupabaseAnalysisStore:
        return SupabaseAnalysisStore(self.settings)

    def list_summaries(self) -> list[TickerSummaryResponse]:
        if self.settings.storage_backend == "supabase":
            store = self._cloud()
            try:
                rows = store.client.select_all(
                    "latest_ticker_summary",
                    {"select": "*", "order": "symbol.asc"},
                )
                return [_summary_from_cloud(row) for row in rows]
            finally:
                store.close()

        base = Path(self.settings.data_dir)
        if not base.exists():
            return []
        data_store = DataStore(self.settings.data_dir)
        symbols = sorted(
            item.name for item in base.iterdir() if item.is_dir() and not item.name.startswith(".")
        )
        return [
            _summary_from_local(
                symbol,
                data_store.load_market_data(symbol),
                data_store.load_technicals(symbol),
                data_store.load_briefing(symbol),
            )
            for symbol in symbols
        ]

    def list_watchlist(self) -> list[WatchlistEntryResponse]:
        if self.settings.storage_backend == "supabase":
            store = self._cloud()
            try:
                rows = store.client.select_all(
                    "tickers",
                    {
                        "select": "symbol,market,theme",
                        "enabled": "eq.true",
                        "order": "symbol.asc",
                    },
                )
                return [
                    WatchlistEntryResponse(
                        symbol=row["symbol"],
                        market=row.get("market", "US"),
                        theme=row.get("theme"),
                    )
                    for row in rows
                ]
            finally:
                store.close()

        watchlist_path = Path("tickers.txt")
        if not watchlist_path.exists():
            return []
        return [
            WatchlistEntryResponse(
                symbol=entry.symbol,
                market=entry.market,
                theme=entry.theme,
            )
            for entry in parse_watchlist(watchlist_path.read_text())
        ]

    def load_ticker(self, symbol: str) -> TickerBundleResponse | None:
        normalized = normalize_ticker(symbol)
        if self.settings.storage_backend == "supabase":
            store = self._cloud()
            try:
                data = store.load_market_data(normalized)
                technicals = store.load_technicals(normalized)
                reports = store.load_public_artifact(normalized, "analyst_reports", AnalystReports)
                debate = store.load_public_artifact(normalized, "debate_result", DebateResult)
                briefing = store.load_public_artifact(normalized, "briefing", Briefing)
                if data is None and technicals is None and not any((reports, debate, briefing)):
                    return None
                return TickerBundleResponse(
                    symbol=normalized,
                    fundamentals=_public_fundamentals(data),
                    technicals=technicals,
                    price_history=data.price_history if data else [],
                    analyst_reports=reports,
                    debate=debate,
                    briefing=briefing,
                )
            finally:
                store.close()

        data_store = DataStore(self.settings.data_dir)
        data = data_store.load_market_data(normalized)
        technicals = data_store.load_technicals(normalized)
        reports = data_store.load_analyst_reports(normalized)
        debate = data_store.load_debate_result(normalized)
        briefing = data_store.load_briefing(normalized)
        if data is None and technicals is None and not any((reports, debate, briefing)):
            return None
        return TickerBundleResponse(
            symbol=normalized,
            fundamentals=_public_fundamentals(data),
            technicals=technicals,
            price_history=data.price_history if data else [],
            analyst_reports=reports,
            debate=debate,
            briefing=briefing,
        )
