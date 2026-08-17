from __future__ import annotations

import asyncio
import logging
from datetime import date

from stock_analysis.agents.fundamentals import FundamentalsAgent
from stock_analysis.agents.macro import MacroFXAgent
from stock_analysis.agents.sentiment import SentimentAgent
from stock_analysis.agents.technical import TechnicalAgent
from stock_analysis.config import Settings
from stock_analysis.data.cloud import build_store
from stock_analysis.data.fetcher_base import BaseFetcher
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.data.us_market import USMarketFetcher
from stock_analysis.debate.engine import DebateEngine
from stock_analysis.debate.research_manager import ResearchManager
from stock_analysis.memory.cloud import build_outcome_store
from stock_analysis.memory.outcomes import build_memory_context
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import DebateResult, ResearchVerdict
from stock_analysis.models.market_data import TickerData
from stock_analysis.models.synthesis import Briefing
from stock_analysis.synthesis.risk_checker import RiskChecker
from stock_analysis.synthesis.synthesizer import SynthesizerAgent

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Orchestrates the public, research-only analysis pipeline.

    ``store`` and ``outcome_store`` are injected so cloud mode never falls
    through to a filesystem write. The local backend remains available for
    tests and offline research.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        market: str = "US",
        fetcher: BaseFetcher | None = None,
        as_of_date: date | None = None,
        store=None,
        outcome_store=None,
        run_id: str | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.store = store or build_store(self.settings, run_id=run_id)
        self.outcome_store = outcome_store or build_outcome_store(self.settings)
        self.run_id = run_id
        self.as_of_date = as_of_date
        self.market = market.upper()
        if fetcher is not None:
            self.fetcher = fetcher
        elif self.market == "MY":
            self.fetcher = MYMarketFetcher(period=self.settings.price_history_period)
        else:
            self.fetcher = USMarketFetcher(period=self.settings.price_history_period)

    def close(self) -> None:
        """Close backend clients owned by this pipeline, when applicable."""
        closed: set[int] = set()
        for backend in (self.store, self.outcome_store):
            if id(backend) in closed:
                continue
            closed.add(id(backend))
            close = getattr(backend, "close", None)
            if close:
                close()

    async def run(self, ticker: str) -> Briefing:
        # === Layer 1: Data Ingestion (deterministic) ===
        logger.info(f"[Layer 1] Fetching market data for {ticker}...")
        ticker_data = self.fetcher.fetch(ticker)
        logger.info(
            f"[Layer 1] Got {len(ticker_data.price_history)} price bars, "
            f"financials={'yes' if ticker_data.financials else 'no'}"
        )

        effective_as_of = self.as_of_date or (
            ticker_data.price_history[-1].date
            if ticker_data.price_history
            else ticker_data.fetched_at.date()
        )
        self.as_of_date = effective_as_of
        self.run_id = self.store.begin_run(
            ticker,
            effective_as_of,
            self.settings,
            market=ticker_data.info.market.value,
        )

        try:
            # API/worker runs have no separate ``stock-fetch`` prerequisite.
            # Persist the fetched market input in cloud mode so the dashboard
            # can render price/technical context next to the briefing. Local
            # mode keeps its historical pipeline behavior; ``stock-fetch`` is
            # still the explicit local market-data writer.
            if self.settings.storage_backend == "supabase":
                merged = self.store.merge_market_data(ticker, ticker_data)
                if merged:
                    self.store.save_technicals(
                        ticker,
                        compute_technicals(ticker_data.info.symbol, merged),
                    )
            briefing = await self._run_layers(ticker, ticker_data)
            self.store.complete_run(self.run_id)
            return briefing
        except Exception as exc:
            self.store.fail_run(self.run_id, str(exc))
            raise

    def _resume(self, stage: str, model_type):
        """Return a stage already persisted under this run, if the backend has one.

        A run whose lease expired mid-flight is reclaimed and re-entered here.
        Artifacts are keyed on ``(run_id, stage)`` and written as each layer
        finishes, so anything durable is a completed layer — re-running it would
        just spend Opus/Sonnet tokens to produce a second answer to a question
        already answered. Always ``None`` on the local backend and on a fresh run.
        """
        resume = getattr(self.store, "resume_artifact", None)
        if not resume:
            return None
        existing = resume(stage, model_type)
        if existing is not None:
            logger.info("[Resume] Reusing durable %s from run %s", stage, self.run_id)
        return existing

    async def _run_layers(self, ticker: str, ticker_data: TickerData) -> Briefing:
        """Run the LLM layers after the durable run has been claimed/created."""

        # === Layer 2: Analyst Agents (parallel) ===
        analyst_reports = self._resume("analyst_reports", AnalystReports)
        if analyst_reports is None:
            logger.info("[Layer 2] Running analyst agents in parallel...")
            agents = [
                FundamentalsAgent(self.settings),
                SentimentAgent(self.settings),
                TechnicalAgent(self.settings),
                MacroFXAgent(self.settings),
            ]

            results = await asyncio.gather(
                agents[0].analyze(ticker_data),
                agents[1].analyze(ticker_data),
                agents[2].analyze(ticker_data),
                agents[3].analyze(ticker_data),
            )

            analyst_reports = AnalystReports(
                fundamentals=results[0],
                sentiment=results[1],
                technical=results[2],
                macro=results[3],
            )
            self.store.save_analyst_reports(ticker, analyst_reports, self.as_of_date)
        logger.info(
            f"[Layer 2] Signals — "
            f"Fundamentals: {analyst_reports.fundamentals.signal.value}, "
            f"Sentiment: {analyst_reports.sentiment.signal.value}, "
            f"Technical: {analyst_reports.technical.signal.value}, "
            f"Macro: {analyst_reports.macro.signal.value}"
        )

        # === Layer 3: Adversarial Debate (sequential rounds) ===
        debate_result = self._resume("debate_result", DebateResult)
        if debate_result is None:
            logger.info(f"[Layer 3] Starting {self.settings.debate_rounds}-round debate...")
            debate_result = await DebateEngine(self.settings).run(ticker_data, analyst_reports)
            self.store.save_debate_result(ticker, debate_result, self.as_of_date)
            logger.info("[Layer 3] Debate complete.")

        # === Layer 3.5: Research Manager (adjudicates the debate) ===
        research_verdict: ResearchVerdict | None = None
        if self.settings.enable_research_manager:
            research_verdict = self._resume("research_verdict", ResearchVerdict)
            if research_verdict is None:
                logger.info("[Layer 3.5] Adjudicating debate...")
                research_verdict = await ResearchManager(self.settings).adjudicate(
                    ticker_data, analyst_reports, debate_result
                )
                self.store.save_research_verdict(ticker, research_verdict, self.as_of_date)
            logger.info(
                f"[Layer 3.5] Verdict: {research_verdict.judged_view.value} "
                f"(winning side: {research_verdict.winning_side})"
            )

        # A durable briefing means every layer finished and RiskChecker already
        # ran; only `complete_run` was missing. Return it rather than paying for
        # synthesis again — and skip the outcome-memory read it no longer needs.
        finished = self._resume("briefing", Briefing)
        if finished is not None:
            return finished

        # === Outcome memory read ===
        # Read before synthesis because it is an input to it. Gated on
        # `as_of_date` so a backtest never sees an outcome that had not resolved
        # yet — without that filter the "track record" becomes future knowledge.
        memory_context: str | None = None
        if self.settings.enable_outcome_memory:
            prior = self.outcome_store.load(ticker, before=self.as_of_date)
            if prior:
                memory_context = build_memory_context(
                    prior, self.outcome_store.calibration(ticker, before=self.as_of_date)
                )
                logger.info(f"[Outcome memory] Injected {len(prior)} prior outcome(s).")

        # === Layer 4: Synthesis + Risk ===
        logger.info("[Layer 4] Synthesizing final briefing...")
        briefing = await SynthesizerAgent(self.settings).synthesize(
            ticker_data,
            analyst_reports,
            debate_result,
            research_verdict=research_verdict,
            memory_context=memory_context,
        )

        risk_checker = RiskChecker()
        briefing.action_plan = risk_checker.plan_action(ticker_data, briefing)
        briefing.risk_assessment = risk_checker.assess(ticker_data, briefing)

        self.store.save_briefing(ticker, briefing, self.as_of_date)
        logger.info(
            f"[Layer 4] Research view: {briefing.overall_signal.value} "
            f"(conviction: {briefing.conviction.score:+.2f}, "
            f"convergence: {briefing.conviction.signal_convergence:.2f})"
        )
        return briefing
