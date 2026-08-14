from __future__ import annotations

import asyncio
import logging
from datetime import date

from stock_analysis.agents.fundamentals import FundamentalsAgent
from stock_analysis.agents.macro import MacroFXAgent
from stock_analysis.agents.sentiment import SentimentAgent
from stock_analysis.agents.technical import TechnicalAgent
from stock_analysis.config import Settings
from stock_analysis.data.fetcher_base import BaseFetcher
from stock_analysis.data.my_market import MYMarketFetcher
from stock_analysis.data.store import DataStore
from stock_analysis.data.us_market import USMarketFetcher
from stock_analysis.debate.engine import DebateEngine
from stock_analysis.debate.research_manager import ResearchManager
from stock_analysis.memory.outcomes import OutcomeStore, build_memory_context
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.debate import ResearchVerdict
from stock_analysis.models.synthesis import Briefing
from stock_analysis.synthesis.risk_checker import RiskChecker
from stock_analysis.synthesis.synthesizer import SynthesizerAgent

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Orchestrates the public, research-only analysis pipeline."""

    def __init__(
        self,
        settings: Settings | None = None,
        market: str = "US",
        fetcher: BaseFetcher | None = None,
        as_of_date: date | None = None,
    ):
        self.settings = settings or Settings()
        self.store = DataStore(self.settings.data_dir)
        self.as_of_date = as_of_date
        if fetcher is not None:
            self.fetcher = fetcher
        elif market.upper() == "MY":
            self.fetcher = MYMarketFetcher(period=self.settings.price_history_period)
        else:
            self.fetcher = USMarketFetcher(period=self.settings.price_history_period)

    async def run(self, ticker: str) -> Briefing:
        # === Layer 1: Data Ingestion (deterministic) ===
        logger.info(f"[Layer 1] Fetching market data for {ticker}...")
        ticker_data = self.fetcher.fetch(ticker)
        logger.info(
            f"[Layer 1] Got {len(ticker_data.price_history)} price bars, "
            f"financials={'yes' if ticker_data.financials else 'no'}"
        )

        # === Layer 2: Analyst Agents (parallel) ===
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
        logger.info(f"[Layer 3] Starting {self.settings.debate_rounds}-round debate...")
        debate_engine = DebateEngine(self.settings)
        debate_result = await debate_engine.run(ticker_data, analyst_reports)
        self.store.save_debate_result(ticker, debate_result, self.as_of_date)
        logger.info("[Layer 3] Debate complete.")

        # === Layer 3.5: Research Manager (adjudicates the debate) ===
        research_verdict: ResearchVerdict | None = None
        if self.settings.enable_research_manager:
            logger.info("[Layer 3.5] Adjudicating debate...")
            research_verdict = await ResearchManager(self.settings).adjudicate(
                ticker_data, analyst_reports, debate_result
            )
            self.store.save_research_verdict(ticker, research_verdict, self.as_of_date)
            logger.info(
                f"[Layer 3.5] Verdict: {research_verdict.judged_view.value} "
                f"(winning side: {research_verdict.winning_side})"
            )

        # === Outcome memory read ===
        # Read before synthesis because it is an input to it. Gated on
        # `as_of_date` so a backtest never sees an outcome that had not resolved
        # yet — without that filter the "track record" is future knowledge.
        memory_context: str | None = None
        if self.settings.enable_outcome_memory:
            outcome_store = OutcomeStore(self.settings.data_dir)
            prior = outcome_store.load(ticker, before=self.as_of_date)
            if prior:
                memory_context = build_memory_context(
                    prior, outcome_store.calibration(ticker, before=self.as_of_date)
                )
                logger.info(f"[Outcome memory] Injected {len(prior)} prior outcome(s).")

        # === Layer 4: Synthesis + Risk ===
        logger.info("[Layer 4] Synthesizing final briefing...")
        synthesizer = SynthesizerAgent(self.settings)
        briefing = await synthesizer.synthesize(
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
