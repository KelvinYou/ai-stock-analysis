from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf
from pydantic import BaseModel

from stock_analysis.config import Settings
from stock_analysis.data.my_market import BURSA_ALIASES
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.synthesis import Briefing
from stock_analysis.orchestrator import AnalysisPipeline

from .fetcher import BacktestFetcher

logger = logging.getLogger(__name__)


class BacktestTrial(BaseModel):
    """Result of a single (ticker, as_of_date) trial."""

    ticker: str
    as_of_date: date
    horizon_days: int
    entry_price: float
    exit_date: date | None
    exit_price: float | None
    realized_return: float | None  # (exit - entry) / entry
    overall_signal: Signal
    conviction_score: float
    signal_convergence: float
    agent_signals: dict[str, str]
    error: str | None = None


class BacktestResult(BaseModel):
    """Collected output of a backtest run."""

    trials: list[BacktestTrial]
    settings: dict
    started_at: date
    finished_at: date


class Backtester:
    """Runs the analysis pipeline across historical (ticker, as_of_date) pairs
    and captures realized forward returns for scoring."""

    def __init__(
        self,
        settings: Settings | None = None,
        market: str = "US",
        horizon_days: int = 30,
        lookback_days: int = 365,
    ):
        self.settings = settings or Settings()
        self.market = market.upper()
        self.horizon_days = horizon_days
        self.lookback_days = lookback_days

    async def run(
        self,
        tickers: Iterable[str],
        as_of_dates: Iterable[date],
        resume: bool = True,
    ) -> BacktestResult:
        """Run the pipeline for every (ticker × as_of_date) pair.

        If `resume` is True, trials whose briefing.json already exists on disk
        are reloaded instead of re-run — useful for expensive LLM calls.
        """
        tickers = list(tickers)
        as_of_dates = sorted(set(as_of_dates))
        started_at = date.today()

        # Fetch forward price series once per ticker, spanning the full trial range.
        max_exit = max(as_of_dates) + timedelta(days=self.horizon_days + 10)
        forward_series = {
            t: self._fetch_price_series(t, min(as_of_dates), max_exit) for t in tickers
        }

        trials: list[BacktestTrial] = []
        for ticker in tickers:
            for as_of in as_of_dates:
                try:
                    trial = await self._run_one(ticker, as_of, forward_series[ticker], resume)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Trial failed: %s @ %s", ticker, as_of)
                    trial = BacktestTrial(
                        ticker=ticker,
                        as_of_date=as_of,
                        horizon_days=self.horizon_days,
                        entry_price=float("nan"),
                        exit_date=None,
                        exit_price=None,
                        realized_return=None,
                        overall_signal=Signal.NEUTRAL,
                        conviction_score=0.0,
                        signal_convergence=0.0,
                        agent_signals={},
                        error=str(exc),
                    )
                trials.append(trial)

        return BacktestResult(
            trials=trials,
            settings={
                "market": self.market,
                "horizon_days": self.horizon_days,
                "lookback_days": self.lookback_days,
                "quick_think_model": self.settings.quick_think_model,
                "deep_think_model": self.settings.deep_think_model,
                "debate_rounds": self.settings.debate_rounds,
            },
            started_at=started_at,
            finished_at=date.today(),
        )

    # ------------------------------------------------------------------
    async def _run_one(
        self,
        ticker: str,
        as_of: date,
        forward_series: pd.DataFrame,
        resume: bool,
    ) -> BacktestTrial:
        # Check cache first
        store_path = (
            Path(self.settings.data_dir) / ticker.upper() / as_of.isoformat() / "briefing.json"
        )
        briefing: Briefing | None = None
        if resume and store_path.exists():
            logger.info("[%s @ %s] Resuming from cached briefing", ticker, as_of)
            briefing = Briefing.model_validate_json(store_path.read_text())

        if briefing is None:
            fetcher = BacktestFetcher(
                as_of_date=as_of,
                market=self.market,
                lookback_days=self.lookback_days,
            )
            pipeline = AnalysisPipeline(
                settings=self.settings,
                market=self.market,
                fetcher=fetcher,
                as_of_date=as_of,
            )
            logger.info("[%s @ %s] Running pipeline", ticker, as_of)
            briefing = await pipeline.run(ticker)

        entry_price, _entry_date = self._price_on_or_after(forward_series, as_of)
        exit_price, exit_date = self._price_on_or_after(
            forward_series, as_of + timedelta(days=self.horizon_days)
        )
        realized = (
            (exit_price - entry_price) / entry_price
            if entry_price and exit_price
            else None
        )

        return BacktestTrial(
            ticker=ticker.upper(),
            as_of_date=as_of,
            horizon_days=self.horizon_days,
            entry_price=entry_price if entry_price is not None else float("nan"),
            exit_date=exit_date,
            exit_price=exit_price,
            realized_return=realized,
            overall_signal=briefing.overall_signal,
            conviction_score=briefing.conviction.score,
            signal_convergence=briefing.conviction.signal_convergence,
            agent_signals=dict(briefing.agent_signal_breakdown),
        )

    # ------------------------------------------------------------------
    def _fetch_price_series(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        yf_ticker = self._resolve_yf(ticker)
        hist = yf.Ticker(yf_ticker).history(
            start=start.isoformat(), end=end.isoformat()
        )
        if hist.empty:
            logger.warning("No forward price data for %s", ticker)
        return hist

    def _resolve_yf(self, ticker: str) -> str:
        t = ticker.upper().strip()
        if self.market != "MY":
            return t
        if t.endswith(".KL"):
            return t
        if t in BURSA_ALIASES:
            return f"{BURSA_ALIASES[t]}.KL"
        return f"{t}.KL"

    @staticmethod
    def _price_on_or_after(hist: pd.DataFrame, target: date):
        if hist.empty:
            return None, None
        dates = hist.index.date
        mask = dates >= target
        if not mask.any():
            return None, None
        idx = mask.argmax()
        row = hist.iloc[idx]
        return float(row["Close"]), hist.index[idx].date()
