from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from pydantic import BaseModel, Field

from stock_analysis.config import Settings
from stock_analysis.data.cloud import build_store
from stock_analysis.data.my_market import BURSA_ALIASES
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import MacroSnapshot, PriceBar
from stock_analysis.models.synthesis import Briefing
from stock_analysis.orchestrator import AnalysisPipeline

from .fetcher import BacktestFetcher

logger = logging.getLogger(__name__)


_SIGNAL_NAMES = {signal.value for signal in Signal}


def _normalise_agent_signals(signals: dict[str, str]) -> dict[str, str]:
    """Make agent attribution compatible with portfolio strategy names."""
    normalised: dict[str, str] = {}
    for name, raw_signal in signals.items():
        strategy = "macro" if name == "macro_fx" else name
        signal = str(raw_signal).strip().split(maxsplit=1)[0].lower()
        if signal in _SIGNAL_NAMES:
            normalised[strategy] = signal
    return normalised


def execution_signal(briefing: Briefing) -> Signal:
    """Return the signal that has a valid deterministic execution plan."""
    if briefing.action_plan is not None and briefing.action_plan.note:
        return Signal.NEUTRAL
    return briefing.overall_signal


def execution_signal_gate_reasons(briefing: Briefing) -> list[str]:
    """Return stable reason codes for gates applied before execution."""
    reasons = list(briefing.signal_gate_reasons)
    if briefing.action_plan is not None and briefing.action_plan.note:
        reasons.append("execution_action_plan_note_present")
    return list(dict.fromkeys(reasons))


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
    # Input analyst calls before strategy-name normalization or evidence guards.
    # Session scoring may neutralize unavailable evidence in agent_signals while
    # preserving the source labels here.
    raw_agent_signals: dict[str, str] = Field(default_factory=dict)
    # Synthesizer choice before deterministic gates; None means the source
    # briefing predates signal tracing.
    synthesized_signal: Signal | None = None
    # Stable gate reason codes; overall_signal remains the final executable
    # direction consumed by scoring and portfolio simulation.
    signal_gate_reasons: list[str] = Field(default_factory=list)
    error: str | None = None
    # Actual fill date. Older sealed bundles omit this and fall back to
    # ``as_of_date`` for compatibility; newly generated runs use next-session
    # open fills.
    entry_date: date | None = None


class BacktestResult(BaseModel):
    """Collected output of a backtest run."""

    trials: list[BacktestTrial]
    settings: dict
    started_at: date
    finished_at: date
    # Shared daily marks from the same provider response used to compute trial
    # outcomes. Optional so previously written artifacts remain readable.
    price_paths: dict[str, list[PriceBar]] = Field(default_factory=dict)
    # Optional dated FRED DFF observations. Kept in the scored artifact so a
    # later rescore reproduces the cash-yield diagnostic without refetching.
    cash_rate_path: list[MacroSnapshot] = Field(default_factory=list)


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
        self.settings = settings or Settings.from_env()
        self.store = build_store(self.settings)
        self.market = market.upper()
        self.horizon_days = horizon_days
        self.lookback_days = lookback_days

    def close(self) -> None:
        close = getattr(self.store, "close", None)
        if close:
            close()

    async def run(
        self,
        tickers: Iterable[str],
        as_of_dates: Iterable[date],
        resume: bool = False,
    ) -> BacktestResult:
        """Run the pipeline for every (ticker × as_of_date) pair.

        Unversioned cached briefings cannot prove which model, prompt, or
        evidence produced them, so confirmatory API runs always regenerate.
        """
        if resume:
            raise ValueError(
                "API backtest resume is unsafe without cache provenance; "
                "rerun with resume=False."
            )
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
                    trial = await self._run_one(ticker, as_of, forward_series[ticker])
                except Exception as exc:
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
                "entry_execution": "next_session_open",
                "price_path_source": "yfinance_auto_adjusted_ohlc",
                "signal_trace_schema": 1,
                "quick_think_model": self.settings.quick_think_model,
                "deep_think_model": self.settings.deep_think_model,
                "synthesis_model": self.settings.synthesis_model,
                "debate_rounds": self.settings.debate_rounds,
            },
            started_at=started_at,
            finished_at=date.today(),
            price_paths={
                ticker.upper(): self._price_bars(forward_series[ticker])
                for ticker in tickers
                if not forward_series[ticker].empty
            },
        )

    # ------------------------------------------------------------------
    async def _run_one(
        self,
        ticker: str,
        as_of: date,
        forward_series: pd.DataFrame,
    ) -> BacktestTrial:
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
        try:
            briefing = await pipeline.run(ticker)
        finally:
            pipeline.close()

        raw_agent_signals = dict(briefing.agent_signal_breakdown)
        agent_signals = _normalise_agent_signals(raw_agent_signals)
        entry_price, entry_date = self._price_on_or_after(
            forward_series,
            as_of + timedelta(days=1),
            price_column="Open",
        )
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
            overall_signal=execution_signal(briefing),
            conviction_score=briefing.conviction.score,
            signal_convergence=briefing.conviction.signal_convergence,
            agent_signals=agent_signals,
            raw_agent_signals=raw_agent_signals,
            synthesized_signal=briefing.synthesized_signal,
            signal_gate_reasons=execution_signal_gate_reasons(briefing),
            entry_date=entry_date,
        )

    # ------------------------------------------------------------------
    def _fetch_price_series(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        yf_ticker = self._resolve_yf(ticker)
        hist = yf.Ticker(yf_ticker).history(
            start=start.isoformat(), end=end.isoformat(), auto_adjust=True
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
    def _price_on_or_after(
        hist: pd.DataFrame,
        target: date,
        *,
        price_column: str = "Close",
    ):
        if hist.empty:
            return None, None
        dates = hist.index.date
        mask = dates >= target
        if not mask.any():
            return None, None
        idx = mask.argmax()
        row = hist.iloc[idx]
        if price_column not in row or pd.isna(row[price_column]):
            return None, None
        price = float(row[price_column])
        if not math.isfinite(price) or price <= 0:
            return None, None
        return price, hist.index[idx].date()

    @staticmethod
    def _price_bars(hist: pd.DataFrame) -> list[PriceBar]:
        bars: list[PriceBar] = []
        required = ("Open", "High", "Low", "Close", "Volume")
        for column in required:
            if column not in hist.columns:
                return []
        for timestamp, row in hist.iterrows():
            values = [row[column] for column in required]
            if any(pd.isna(value) for value in values):
                continue
            open_, high, low, close = (float(value) for value in values[:4])
            raw_volume = float(row["Volume"])
            if (
                not all(math.isfinite(value) for value in (open_, high, low, close))
                or not math.isfinite(raw_volume)
                or min(open_, high, low, close) <= 0
                or raw_volume < 0
            ):
                continue
            volume = int(raw_volume)
            bars.append(
                PriceBar(
                    date=timestamp.date(),
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        return bars
