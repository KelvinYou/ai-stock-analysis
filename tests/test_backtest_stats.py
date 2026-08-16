"""Tests for backtest uncertainty quantification.

These pin the behaviour that stops a backtest from overstating itself: interval
estimates that admit when they span the null, sample sizes discounted for
overlapping holding periods, and Sharpe figures priced for selection bias.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from stock_analysis.backtest import portfolio as portfolio_mod
from stock_analysis.backtest import stats
from stock_analysis.backtest.portfolio import PortfolioConfig
from stock_analysis.backtest.runner import BacktestResult, BacktestTrial
from stock_analysis.backtest.scorer import Scorer
from stock_analysis.models.agent_reports import Signal


class StudentTTests(unittest.TestCase):
    """The t tail is hand-rolled, so it is checked against published criticals."""

    def test_matches_textbook_critical_values(self):
        cases = [
            (2.228, 10, 0.05),
            (2.086, 20, 0.05),
            (3.169, 10, 0.01),
            (2.845, 20, 0.01),
        ]
        for t, df, expected_p in cases:
            with self.subTest(t=t, df=df):
                self.assertAlmostEqual(stats.student_t_two_sided_p(t, df), expected_p, places=3)

    def test_converges_to_normal_at_large_df(self):
        self.assertAlmostEqual(stats.student_t_two_sided_p(1.96, 1_000_000), 0.05, places=3)

    def test_zero_t_gives_p_of_one(self):
        self.assertAlmostEqual(stats.student_t_two_sided_p(0.0, 10), 1.0, places=6)

    def test_heavier_tails_than_normal_at_small_df(self):
        # Same t is *less* significant with few degrees of freedom.
        self.assertGreater(
            stats.student_t_two_sided_p(2.0, 3),
            stats.student_t_two_sided_p(2.0, 300),
        )


class WilsonIntervalTests(unittest.TestCase):
    def test_small_sample_hit_rate_still_spans_a_coin_flip(self):
        lo, hi = stats.wilson_interval(6, 10)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_interval_narrows_as_sample_grows(self):
        narrow = stats.wilson_interval(600, 1000)
        wide = stats.wilson_interval(6, 10)
        self.assertLess(narrow[1] - narrow[0], wide[1] - wide[0])

    def test_does_not_collapse_at_the_boundaries(self):
        # The normal approximation gives zero width here, which is backwards:
        # 10/10 is weak evidence, not certainty.
        lo, hi = stats.wilson_interval(10, 10)
        self.assertLess(lo, 1.0)
        self.assertEqual(hi, 1.0)

    def test_stays_inside_zero_one(self):
        lo, hi = stats.wilson_interval(0, 10)
        self.assertGreaterEqual(lo, 0.0)
        self.assertLessEqual(hi, 1.0)

    def test_empty_sample_returns_none(self):
        self.assertIsNone(stats.wilson_interval(0, 0))


class EffectiveSampleSizeTests(unittest.TestCase):
    def test_non_overlapping_trials_count_fully(self):
        windows = [
            ("A", date(2025, 1, 1), date(2025, 1, 31)),
            ("A", date(2025, 3, 1), date(2025, 3, 31)),
        ]
        self.assertEqual(stats.effective_sample_size(windows), 2.0)

    def test_fully_overlapping_trials_count_once(self):
        windows = [
            ("A", date(2025, 1, 1), date(2025, 1, 31)),
            ("A", date(2025, 1, 8), date(2025, 2, 7)),
        ]
        self.assertEqual(stats.effective_sample_size(windows), 1.0)

    def test_different_tickers_do_not_overlap(self):
        windows = [
            ("A", date(2025, 1, 1), date(2025, 1, 31)),
            ("B", date(2025, 1, 1), date(2025, 1, 31)),
        ]
        self.assertEqual(stats.effective_sample_size(windows), 2.0)

    def test_weekly_trials_at_monthly_horizon_collapse(self):
        # The default-ish configuration: --interval weekly with --horizon 30.
        base = date(2025, 1, 1)
        windows = [
            ("A", base + timedelta(days=7 * i), base + timedelta(days=7 * i + 30))
            for i in range(5)
        ]
        self.assertEqual(stats.effective_sample_size(windows), 1.0)

    def test_empty_input(self):
        self.assertEqual(stats.effective_sample_size([]), 0.0)


class TTestTests(unittest.TestCase):
    def test_overlap_correction_can_remove_significance(self):
        returns = [0.02, 0.03, -0.01, 0.04, 0.01, 0.02, 0.03, -0.005, 0.025, 0.015]

        _, p_nominal = stats.t_test_vs_zero(returns)
        _, p_effective = stats.t_test_vs_zero(returns, n_eff=3.0)

        self.assertLess(p_nominal, 0.05)
        self.assertGreater(p_effective, 0.05)

    def test_returns_none_for_degenerate_input(self):
        self.assertEqual(stats.t_test_vs_zero([0.01]), (None, None))
        self.assertEqual(stats.t_test_vs_zero([0.01, 0.01, 0.01]), (None, None))


class SharpeSelectionBiasTests(unittest.TestCase):
    def test_psr_penalises_negative_skew_and_fat_tails(self):
        normal = stats.probabilistic_sharpe_ratio(0.5, 20, 0.0, 3.0)
        skewed = stats.probabilistic_sharpe_ratio(0.5, 20, -1.5, 8.0)
        self.assertLess(skewed, normal)

    def test_expected_max_sharpe_grows_with_search_breadth(self):
        few = stats.expected_max_sharpe(3, 0.04)
        many = stats.expected_max_sharpe(50, 0.04)
        self.assertGreater(many, few)

    def test_expected_max_sharpe_needs_a_real_comparison(self):
        self.assertIsNone(stats.expected_max_sharpe(1, 0.04))
        self.assertIsNone(stats.expected_max_sharpe(6, 0.0))

    def test_deflated_sharpe_is_below_undeflated_psr(self):
        psr = stats.probabilistic_sharpe_ratio(0.5, 20, 0.0, 3.0)
        dsr = stats.deflated_sharpe_ratio(0.5, 20, 0.0, 3.0, n_strategies=6, sr_variance=0.04)
        self.assertLess(dsr, psr)


class FisherIntervalTests(unittest.TestCase):
    def test_weak_ic_on_small_sample_spans_zero(self):
        lo, hi = stats.fisher_ci(0.15, 20)
        self.assertLess(lo, 0.0)
        self.assertGreater(hi, 0.0)

    def test_undefined_below_four_observations(self):
        self.assertIsNone(stats.fisher_ci(0.5, 3))


# ----------------------------------------------------------------------
def _trial(
    ticker: str,
    as_of: date,
    signal: Signal,
    realized: float | None,
    horizon: int = 30,
    conviction: float = 0.5,
) -> BacktestTrial:
    return BacktestTrial(
        ticker=ticker,
        as_of_date=as_of,
        horizon_days=horizon,
        entry_price=100.0,
        exit_date=as_of + timedelta(days=horizon),
        exit_price=100.0 * (1 + (realized or 0.0)),
        realized_return=realized,
        overall_signal=signal,
        conviction_score=conviction,
        signal_convergence=0.75,
        agent_signals={"technical": signal.value},
    )


def _result(trials: list[BacktestTrial]) -> BacktestResult:
    return BacktestResult(
        trials=trials,
        settings={"horizon_days": 30, "quick_think_model": "haiku"},
        started_at=date(2026, 1, 1),
        finished_at=date(2026, 1, 1),
    )


class ScorerUncertaintyTests(unittest.TestCase):
    def _spaced_trials(self, n: int = 6, spacing: int = 90) -> list[BacktestTrial]:
        base = date(2025, 3, 1)
        returns = [0.05, -0.02, 0.03, 0.04, -0.01, 0.02]
        return [
            _trial("AAA", base + timedelta(days=spacing * i), Signal.BUY, returns[i])
            for i in range(n)
        ]

    def test_hit_rate_carries_an_interval_and_a_denominator(self):
        report = Scorer.score(_result(self._spaced_trials()))

        self.assertEqual(report.directional_trials, 6)
        self.assertIsNotNone(report.hit_rate_ci_95)
        lo, hi = report.hit_rate_ci_95
        self.assertLessEqual(lo, report.overall_hit_rate)
        self.assertGreaterEqual(hi, report.overall_hit_rate)

    def test_effective_n_discounts_overlapping_trials(self):
        spaced = Scorer.score(_result(self._spaced_trials(spacing=90)))
        overlapping = Scorer.score(_result(self._spaced_trials(spacing=7)))

        self.assertEqual(spaced.effective_n, 6.0)
        self.assertLess(overlapping.effective_n, spaced.effective_n)
        self.assertEqual(overlapping.directional_trials, spaced.directional_trials)

    def test_neutral_trials_split_the_two_mean_return_denominators(self):
        base = date(2025, 3, 1)
        trials = [
            _trial("AAA", base, Signal.BUY, 0.10),
            _trial("AAA", base + timedelta(days=90), Signal.NEUTRAL, 0.10),
        ]
        report = Scorer.score(_result(trials))

        # Directional-only average sees one +10% trade.
        self.assertAlmostEqual(report.active_mean_return, 0.10)
        # All-trials average dilutes it with the flat trial.
        self.assertAlmostEqual(report.directional_mean_return, 0.05)
        self.assertEqual(report.directional_trials, 1)
        self.assertEqual(report.completed_trials, 2)

    def test_costs_reduce_net_return_by_the_round_trip(self):
        report = Scorer.score(_result(self._spaced_trials()), cost_bps_per_side=25.0)

        self.assertEqual(report.cost_bps_per_side, 25.0)
        self.assertAlmostEqual(
            report.directional_mean_return - report.net_directional_mean_return,
            0.005,  # 25 bps × 2 sides
            places=6,
        )

    def test_costs_are_not_charged_to_flat_trials(self):
        base = date(2025, 3, 1)
        trials = [
            _trial("AAA", base + timedelta(days=90 * i), Signal.NEUTRAL, 0.01)
            for i in range(3)
        ]
        report = Scorer.score(_result(trials), cost_bps_per_side=50.0)

        self.assertEqual(report.net_directional_mean_return, 0.0)

    def test_markdown_flags_an_interval_that_spans_a_coin_flip(self):
        base = date(2025, 3, 1)
        # 2 wins, 2 losses — a hit rate of exactly 50%.
        trials = [
            _trial("AAA", base, Signal.BUY, 0.05),
            _trial("AAA", base + timedelta(days=90), Signal.BUY, -0.05),
            _trial("AAA", base + timedelta(days=180), Signal.BUY, 0.05),
            _trial("AAA", base + timedelta(days=270), Signal.BUY, -0.05),
        ]
        result = _result(trials)
        markdown = Scorer.to_markdown(result, Scorer.score(result))

        self.assertIn("coin flip", markdown)
        self.assertIn("Effective sample size", markdown)
        self.assertIn("How to read this", markdown)

    def test_markdown_warns_when_costs_are_unmodelled(self):
        result = _result(self._spaced_trials())
        self.assertIn("Costs not modelled", Scorer.to_markdown(result, Scorer.score(result)))
        with_costs = Scorer.score(result, cost_bps_per_side=10.0)
        self.assertIn("Net of costs", Scorer.to_markdown(result, with_costs))

    def test_empty_run_does_not_crash(self):
        result = _result([])
        markdown = Scorer.to_markdown(result, Scorer.score(result))
        self.assertIn("Backtest Report", markdown)


class PortfolioCostAndSelectionTests(unittest.TestCase):
    def _trials(self) -> list[BacktestTrial]:
        base = date(2025, 3, 1)
        returns = [0.06, -0.02, 0.04, 0.03, -0.01, 0.05]
        return [
            _trial("AAA", base + timedelta(days=90 * i), Signal.BUY, returns[i])
            for i in range(6)
        ]

    def test_round_trip_cost_is_deducted_from_every_trade(self):
        result = _result(self._trials())
        free = portfolio_mod.simulate(result, PortfolioConfig(), strategies=["overall"])
        costed = portfolio_mod.simulate(
            result, PortfolioConfig(cost_bps_per_side=50.0), strategies=["overall"]
        )

        free_trade = free.strategies[0].trades[0]
        costed_trade = costed.strategies[0].trades[0]
        self.assertAlmostEqual(
            free_trade.return_pct - costed_trade.return_pct, 0.01, places=6
        )
        self.assertLess(costed.strategies[0].final_balance, free.strategies[0].final_balance)

    def test_winner_is_identified_and_deflated(self):
        report = portfolio_mod.simulate(_result(self._trials()))

        self.assertEqual(report.n_strategies_tested, len(report.strategies))
        self.assertIsNotNone(report.best_strategy)
        winner = next(s for s in report.strategies if s.strategy == report.best_strategy)
        for other in report.strategies:
            if other.trade_sharpe is not None:
                self.assertGreaterEqual(winner.trade_sharpe, other.trade_sharpe)

    def test_markdown_reports_selection_bias(self):
        markdown = portfolio_mod.to_markdown(portfolio_mod.simulate(_result(self._trials())))

        self.assertIn("Selection bias", markdown)
        self.assertIn("none modelled", markdown)

    def test_no_trades_does_not_crash(self):
        base = date(2025, 3, 1)
        trials = [_trial("AAA", base, Signal.NEUTRAL, 0.01)]
        report = portfolio_mod.simulate(_result(trials), strategies=["overall"])
        self.assertEqual(report.strategies[0].n_trades, 0)
        self.assertIsNone(report.strategies[0].trade_sharpe)


if __name__ == "__main__":
    unittest.main()
