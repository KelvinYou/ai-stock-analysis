"""Layer 5 gate: sizing arithmetic, cap enforcement, and honest degradation."""

import unittest
from datetime import datetime

from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import Market, TickerData, TickerInfo
from stock_analysis.models.synthesis import (
    ActionPlan,
    Briefing,
    ConvictionScore,
    ExposureStatus,
    RiskAssessment,
    TradeDecision,
)
from stock_analysis.synthesis.holdings import (
    ConcentrationPolicy,
    Holding,
    HoldingsSnapshot,
)
from stock_analysis.synthesis.portfolio_gate import PortfolioGate
from stock_analysis.synthesis.risk_checker import RiskChecker


def _ticker(symbol: str = "NVDA", sector: str = "Technology", currency: str = "USD") -> TickerData:
    return TickerData(
        info=TickerInfo(
            symbol=symbol,
            name=symbol,
            sector=sector,
            market=Market.US if currency == "USD" else Market.MY,
            currency=currency,
            beta=1.5,
        ),
        price_history=[],
        fetched_at=datetime(2026, 8, 13, 12, 0),
    )


def _briefing(
    score: float = 0.7,
    convergence: float = 0.8,
    entry: float | None = 200.0,
    stop: float | None = 180.0,
) -> Briefing:
    signal = Signal.BUY if score > 0 else Signal.SELL if score < 0 else Signal.NEUTRAL
    return Briefing(
        ticker="NVDA",
        date="2026-08-13",
        overall_signal=signal,
        research_view=signal,
        conviction=ConvictionScore(
            score=score, signal_convergence=convergence, explanation="test"
        ),
        executive_summary="s",
        bull_case="b",
        bear_case="b",
        key_uncertainties=[],
        catalysts_upcoming=[],
        risk_assessment=RiskAssessment(
            position_size_suggestion="pending",
            correlation_notes=[],
            max_drawdown_scenario="pending",
        ),
        action_plan=ActionPlan(
            entry_limit=entry,
            stop_loss=stop,
            take_profit_1=entry * 1.2 if entry else None,
        ),
        agent_signal_breakdown={},
    )


def _snapshot(*holdings: Holding) -> HoldingsSnapshot:
    return HoldingsSnapshot(holdings=list(holdings), source="test://portfolio.yaml")


def _holding(
    symbol: str,
    value_myr: float | None,
    sector: str = "Technology",
    currency: str = "USD",
    shares: float = 1.0,
    code: str | None = None,
) -> Holding:
    return Holding(
        symbol=symbol,
        code=code,
        market="US" if currency == "USD" else "MY",
        currency=currency,
        shares=shares,
        price=100.0 if value_myr is not None else None,
        sector=sector,
        value_myr=value_myr,
    )


def _gate(snapshot: HoldingsSnapshot, policy: ConcentrationPolicy) -> PortfolioGate:
    return PortfolioGate(data_dir="unused", holdings=snapshot, policy=policy)


def _policy(single=None, sector=None, usd=None) -> ConcentrationPolicy:
    return ConcentrationPolicy(
        max_single_position_pct_of_equity=single,
        max_sector_pct_of_equity=sector,
        max_usd_pct_of_tracked_investable_assets=usd,
        source="test://policy.yaml",
    )


class SizingChainTests(unittest.TestCase):
    def test_position_size_is_risk_budget_over_stop_distance(self):
        # 0.5% risk budget on a 10% stop distance -> 5% position.
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing(entry=200.0, stop=180.0))
        self.assertEqual(result.sizing.stop_distance_pct, 10.0)
        self.assertEqual(result.sizing.suggested_position_pct, 5.0)

    def test_tighter_stop_allows_larger_position(self):
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        tight = gate.evaluate(_ticker(), _briefing(entry=200.0, stop=195.0))
        wide = gate.evaluate(_ticker(), _briefing(entry=200.0, stop=150.0))
        self.assertGreater(
            tight.sizing.suggested_position_pct, wide.sizing.suggested_position_pct
        )

    def test_size_is_capped_by_sanity_rail_and_says_so(self):
        # A 0.5% stop distance would imply a 100% position.
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing(entry=200.0, stop=199.0))
        self.assertEqual(result.sizing.suggested_position_pct, 25.0)
        self.assertIn("sanity rail", result.sizing.capped_by)

    def test_stop_above_entry_yields_no_size_and_watch(self):
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing(entry=200.0, stop=210.0))
        self.assertIsNone(result.sizing.suggested_position_pct)
        self.assertIs(result.decision, TradeDecision.WATCH)

    def test_missing_action_plan_levels_yield_no_size(self):
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing(entry=None, stop=None))
        self.assertIsNone(result.sizing.suggested_position_pct)
        self.assertIs(result.decision, TradeDecision.WATCH)

    def test_risk_budget_is_labelled_as_an_assumption(self):
        gate = _gate(_snapshot(_holding("MSFT", 1000.0)), _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIn("assumption", result.sizing.risk_budget_source)


class DecisionTests(unittest.TestCase):
    def test_approves_when_size_fits_every_cap(self):
        gate = _gate(
            _snapshot(
                _holding("MSFT", 3000.0, "Technology"),
                _holding("JNJ", 3000.0, "Healthcare"),
                _holding("MAYBANK", 4000.0, "Financial Services", "MYR"),
            ),
            _policy(single=20, sector=60, usd=95),
        )
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.APPROVE)
        self.assertTrue(
            all(c.status is ExposureStatus.WITHIN_CAP for c in result.exposures)
        )

    def test_reduces_when_adding_would_breach_a_cap(self):
        # NVDA at 8% of a 10k sleeve, +5% would be 13% against a 10% cap.
        # Other holdings sit outside Technology so the single-position cap is
        # the only one in play.
        gate = _gate(
            _snapshot(
                _holding("NVDA", 800.0, "Technology"),
                _holding("JNJ", 9200.0, "Healthcare"),
            ),
            _policy(single=10, sector=99, usd=100),
        )
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.REDUCE)
        self.assertTrue(any("Trim to at most" in r for r in result.reasons))

    def test_rejects_when_already_over_cap_before_adding(self):
        gate = _gate(
            _snapshot(_holding("NVDA", 5000.0), _holding("MSFT", 5000.0)),
            _policy(single=10, sector=99, usd=99),
        )
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.REJECT)

    def test_null_cap_is_not_a_pass(self):
        """policy.yaml's rule: a null target takes the cannot-compute path."""
        gate = _gate(_snapshot(_holding("MSFT", 10000.0)), _policy())
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.WATCH)
        self.assertTrue(
            all(c.status is ExposureStatus.CAP_UNCONFIGURED for c in result.exposures)
        )
        self.assertIsNone(result.exposures[0].cap_pct)

    def test_unactionable_signal_watches_without_sizing(self):
        gate = _gate(_snapshot(_holding("MSFT", 10000.0)), _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), _briefing(score=0.1, convergence=0.9))
        self.assertIs(result.decision, TradeDecision.WATCH)

    def test_low_convergence_watches_even_at_high_conviction(self):
        gate = _gate(_snapshot(_holding("MSFT", 10000.0)), _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), _briefing(score=0.9, convergence=0.2))
        self.assertIs(result.decision, TradeDecision.WATCH)

    def test_setup_below_the_reward_risk_floor_watches(self):
        """Guards a real defect: TP1 can land just above a pullback entry.

        `_plan_bullish` takes entry from SMA-20 and TP1 from the nearest
        resistance above the *current* price, so a bullish view can produce a
        setup risking $8.93 to make $0.38. Size alone cannot catch that.
        """
        briefing = _briefing(entry=200.0, stop=180.0)
        briefing.action_plan.take_profit_1 = 201.0  # 0.05:1
        gate = _gate(_snapshot(_holding("MSFT", 10000.0)), _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), briefing)
        self.assertIs(result.decision, TradeDecision.WATCH)
        self.assertTrue(any("below the 1:1 floor" in r for r in result.reasons))

    def test_setup_above_the_floor_is_unaffected(self):
        briefing = _briefing(entry=200.0, stop=180.0)
        briefing.action_plan.take_profit_1 = 240.0  # 2:1
        gate = _gate(
            _snapshot(
                _holding("MSFT", 3000.0, "Technology"),
                _holding("MAYBANK", 7000.0, "Financial Services", "MYR"),
            ),
            _policy(single=20, sector=60, usd=95),
        )
        self.assertIs(gate.evaluate(_ticker(), briefing).decision, TradeDecision.APPROVE)

    def test_bearish_on_held_position_reduces(self):
        gate = _gate(_snapshot(_holding("NVDA", 1000.0), _holding("MSFT", 9000.0)), _policy())
        result = gate.evaluate(_ticker(), _briefing(score=-0.7, entry=None, stop=None))
        self.assertIs(result.decision, TradeDecision.REDUCE)
        self.assertTrue(result.already_held)

    def test_bearish_on_unheld_position_rejects(self):
        gate = _gate(_snapshot(_holding("MSFT", 10000.0)), _policy())
        result = gate.evaluate(_ticker(), _briefing(score=-0.7, entry=None, stop=None))
        self.assertIs(result.decision, TradeDecision.REJECT)
        self.assertFalse(result.already_held)

    def test_missing_holdings_degrades_to_watch_not_approve(self):
        gate = _gate(HoldingsSnapshot(warnings=["no portfolio"]), _policy(single=20))
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.WATCH)
        self.assertTrue(any("portfolio-blind" in r for r in result.reasons))
        # Sizing still reported — it does not depend on holdings.
        self.assertEqual(result.sizing.suggested_position_pct, 5.0)

    def test_wholly_unpriced_portfolio_cannot_check_exposure(self):
        gate = _gate(_snapshot(_holding("MSFT", None)), _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.WATCH)
        self.assertTrue(any("no denominator" in r.lower() for r in result.reasons))


    def test_held_but_unpriced_candidate_cannot_be_approved(self):
        """The one case where a missing price would flip the verdict.

        An unpriced held position reads as 0% current exposure, so the cap check
        would pass on a false premise.
        """
        snapshot = HoldingsSnapshot(
            holdings=[_holding("NVDA", None), _holding("MSFT", 10000.0)],
            source="test://portfolio.yaml",
            unpriced=["NVDA"],
        )
        gate = _gate(snapshot, _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), _briefing())
        self.assertIs(result.decision, TradeDecision.WATCH)
        self.assertTrue(any("unverifiable for exactly this ticker" in r for r in result.reasons))


class ExposureAccountingTests(unittest.TestCase):
    def test_sector_exposure_aggregates_across_holdings(self):
        gate = _gate(
            _snapshot(
                _holding("MSFT", 3000.0, "Technology"),
                _holding("AAPL", 2000.0, "Technology"),
                _holding("MAYBANK", 5000.0, "Financial Services", "MYR"),
            ),
            _policy(single=99, sector=60, usd=99),
        )
        result = gate.evaluate(_ticker(), _briefing())
        sector_check = next(c for c in result.exposures if c.label.startswith("sector"))
        self.assertEqual(sector_check.current_pct, 50.0)
        self.assertEqual(sector_check.projected_pct, 55.0)

    def test_myr_candidate_does_not_add_to_usd_exposure(self):
        gate = _gate(
            _snapshot(_holding("MSFT", 4000.0), _holding("MAYBANK", 6000.0, "Financial Services", "MYR")),
            _policy(single=99, sector=99, usd=99),
        )
        result = gate.evaluate(
            _ticker(symbol="1155", sector="Financial Services", currency="MYR"), _briefing()
        )
        usd_check = next(c for c in result.exposures if "USD" in c.label)
        self.assertEqual(usd_check.current_pct, 40.0)
        self.assertEqual(usd_check.projected_pct, 40.0)

    def test_partial_sector_coverage_is_disclosed(self):
        snapshot = HoldingsSnapshot(
            holdings=[_holding("MSFT", 10000.0, "Technology")],
            source="test://portfolio.yaml",
            missing_sector=["GAMUDA"],
        )
        gate = _gate(snapshot, _policy(single=99, sector=99, usd=99))
        result = gate.evaluate(_ticker(), _briefing())
        sector_check = next(c for c in result.exposures if c.label.startswith("sector"))
        self.assertIn("partial", sector_check.detail)

    def test_unpriced_holdings_warning_reaches_the_reasons(self):
        snapshot = HoldingsSnapshot(
            holdings=[_holding("MSFT", 10000.0), _holding("GAMUDA", None, "Industrials", "MYR")],
            source="test://portfolio.yaml",
            unpriced=["GAMUDA"],
            warnings=["1 holding(s) unpriced (GAMUDA) — exposure percentages understate."],
        )
        gate = _gate(snapshot, _policy(single=20, sector=60, usd=95))
        result = gate.evaluate(_ticker(), _briefing())
        self.assertTrue(any("unpriced" in r for r in result.reasons))


class HoldingsMatchingTests(unittest.TestCase):
    def test_bursa_code_and_alias_resolve_to_the_same_holding(self):
        snapshot = _snapshot(
            _holding("MAYBANK", 1000.0, "Financial Services", "MYR", code="1155")
        )
        for query in ("MAYBANK", "1155", "1155.KL", "maybank"):
            with self.subTest(query=query):
                self.assertIsNotNone(snapshot.find(query))

    def test_unrelated_ticker_does_not_match(self):
        snapshot = _snapshot(_holding("MSFT", 1000.0))
        self.assertIsNone(snapshot.find("NVDA"))

    def test_equity_value_ignores_unpriced_holdings(self):
        snapshot = _snapshot(_holding("MSFT", 1000.0), _holding("GAMUDA", None))
        self.assertEqual(snapshot.equity_value_myr, 1000.0)
        self.assertFalse(snapshot.fully_priced)


class RiskAssessmentIntegrationTests(unittest.TestCase):
    """`RiskChecker` must report the gate's size, never derive a second one."""

    def test_position_size_comes_from_the_gate(self):
        briefing = _briefing()
        gate = _gate(
            _snapshot(
                _holding("MSFT", 3000.0, "Technology"),
                _holding("MAYBANK", 7000.0, "Financial Services", "MYR"),
            ),
            _policy(single=20, sector=60, usd=95),
        )
        briefing.portfolio_gate = gate.evaluate(_ticker(), briefing)
        assessment = RiskChecker().assess(_ticker(), briefing)
        self.assertIn("5.0% of priced equity sleeve", assessment.position_size_suggestion)
        self.assertIn("APPROVE", assessment.position_size_suggestion)

    def test_says_not_sized_when_gate_did_not_run(self):
        assessment = RiskChecker().assess(_ticker(), _briefing())
        self.assertIn("Not sized", assessment.position_size_suggestion)

    def test_risk_reward_uses_real_level_distances(self):
        briefing = _briefing(entry=200.0, stop=180.0)
        briefing.action_plan.take_profit_1 = 260.0
        assessment = RiskChecker().assess(_ticker(), briefing)
        # (260-200) / (200-180) = 3.0
        self.assertEqual(assessment.risk_reward_ratio, "3.0:1")


if __name__ == "__main__":
    unittest.main()
