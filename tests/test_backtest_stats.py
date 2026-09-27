"""Tests for backtest uncertainty quantification.

These pin the behaviour that stops a backtest from overstating itself: interval
estimates that admit when they span the null, sample sizes discounted for
overlapping holding periods, and Sharpe figures priced for selection bias.
"""
from __future__ import annotations

import asyncio
import unittest
from datetime import date, timedelta

from stock_analysis.backtest import portfolio as portfolio_mod
from stock_analysis.backtest import stats
from stock_analysis.backtest.portfolio import PortfolioConfig, StrategyReport
from stock_analysis.backtest.runner import Backtester, BacktestResult, BacktestTrial
from stock_analysis.backtest.scorer import Scorer
from stock_analysis.models.agent_reports import Signal
from stock_analysis.models.market_data import PriceBar


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


class MovingBlockBootstrapTests(unittest.TestCase):
    def test_is_reproducible_and_returns_ordered_interval(self):
        values = [0.01, -0.02, 0.04, 0.03, -0.01, 0.05, 0.02, -0.005]

        first = stats.moving_block_bootstrap_ci(
            values, block_length=2, n_resamples=500, seed=17
        )
        second = stats.moving_block_bootstrap_ci(
            values, block_length=2, n_resamples=500, seed=17
        )

        self.assertEqual(first, second)
        self.assertIsNotNone(first)
        self.assertLessEqual(first[0], first[1])

    def test_refuses_a_sample_shorter_than_the_registered_block(self):
        self.assertIsNone(
            stats.moving_block_bootstrap_ci(
                [0.01, -0.01], block_length=3, n_resamples=100, seed=1
            )
        )

    def test_rejects_invalid_bootstrap_configuration(self):
        with self.assertRaises(ValueError):
            stats.moving_block_bootstrap_ci(
                [0.01, 0.02], block_length=0, n_resamples=100
            )

    def test_old_backtest_artifact_defaults_new_execution_fields(self):
        legacy = BacktestResult.model_validate(
            {
                "trials": [],
                "settings": {"horizon_days": 30},
                "started_at": "2025-01-01",
                "finished_at": "2025-01-02",
            }
        )

        self.assertEqual(legacy.price_paths, {})

    def test_api_resume_rejects_unversioned_cached_briefings(self):
        backtester = Backtester.__new__(Backtester)
        with self.assertRaisesRegex(ValueError, "unsafe without cache provenance"):
            asyncio.run(backtester.run(["AAPL"], [date(2025, 3, 1)], resume=True))


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
    def test_evidence_coverage_discloses_source_breadth(self):
        trial = _trial("AAA", date(2025, 3, 1), Signal.NEUTRAL, 0.01)
        result = _result([trial])
        result.settings["pipeline_mode"] = "in-session"
        result.settings["evidence_coverage"] = {
            "total_trials": 1,
            "available": {"technical": 1, "fundamentals": 1, "sentiment": 1, "macro": 1},
            "sources": {
                "technical": {"historical_price_replay": 1},
                "fundamentals": {"sec_companyfacts": 1},
                "sentiment": {"sec_filing_events_only": 1},
                "macro": {"FRED:DFF": 1},
            },
        }

        markdown = Scorer.to_markdown(result, Scorer.score(result))

        self.assertIn("sentiment: 1/1 trials", markdown)
        self.assertIn("Sources: sec_filing_events_only 1/1", markdown)
        self.assertIn("input presence, not feed completeness", markdown)

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

    def test_effective_n_clusters_different_tickers_on_the_same_date(self):
        as_of = date(2025, 3, 1)
        trials = [_trial(ticker, as_of, Signal.BUY, 0.05) for ticker in ("AAA", "BBB", "CCC")]

        report = Scorer.score(_result(trials))

        self.assertEqual(report.directional_trials, 3)
        self.assertEqual(report.effective_n, 1.0)

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
        self.assertIn("not a portfolio hold", markdown)

    def test_markdown_warns_when_costs_are_unmodelled(self):
        result = _result(self._spaced_trials())
        self.assertIn("Costs not modelled", Scorer.to_markdown(result, Scorer.score(result)))
        with_costs = Scorer.score(result, cost_bps_per_side=10.0)
        self.assertIn("Net of costs", Scorer.to_markdown(result, with_costs))

    def test_markdown_surfaces_point_in_time_evidence_coverage(self):
        result = _result(self._spaced_trials())
        result.settings["evidence_coverage"] = {
            "total_trials": 6,
            "available": {
                "technical": 6,
                "fundamentals": 3,
                "sentiment": 0,
                "macro": 0,
            },
        }

        markdown = Scorer.to_markdown(result, Scorer.score(result))

        self.assertIn("Point-in-time evidence coverage", markdown)
        self.assertIn("fundamentals: 3/6 trials (50.0%)", markdown)
        self.assertIn("macro: 0/6 trials (0.0%)", markdown)

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

    def test_portfolio_effective_n_clusters_same_date_across_tickers(self):
        as_of = date(2025, 3, 1)
        trials = [_trial(ticker, as_of, Signal.BUY, 0.05) for ticker in ("AAA", "BBB", "CCC")]

        report = portfolio_mod.simulate(_result(trials), PortfolioConfig(), strategies=["overall"])

        self.assertEqual(report.strategies[0].n_trades, 3)
        self.assertEqual(report.strategies[0].effective_n, 1.0)

    def test_buy_and_hold_is_one_equal_weight_position_per_ticker(self):
        base = date(2025, 3, 1)
        trials = [
            _trial("AAA", base, Signal.BUY, 0.10),
            _trial("AAA", base + timedelta(days=90), Signal.BUY, -0.20),
            _trial("BBB", base + timedelta(days=30), Signal.BUY, 0.30),
        ]

        report = portfolio_mod.simulate(
            _result(trials),
            PortfolioConfig(cost_bps_per_side=10.0),
            strategies=["buy_and_hold", "rolling_long"],
        )
        strict = report.strategies[0]
        rolling = report.strategies[1]

        self.assertEqual(strict.strategy, "buy_and_hold")
        self.assertEqual(strict.n_trades, 2)
        self.assertEqual(rolling.n_trades, 3)
        self.assertAlmostEqual(strict.trades[0].stake, 5_000.0)
        self.assertAlmostEqual(strict.final_balance, 10_480.0)
        self.assertAlmostEqual(strict.total_return_pct, 0.048)

    def test_same_day_orders_are_invariant_to_trial_order(self):
        as_of = date(2025, 3, 1)
        trials = [
            _trial("BBB", as_of, Signal.BUY, -0.20),
            _trial("AAA", as_of, Signal.BUY, 0.30),
            _trial("CCC", as_of, Signal.NEUTRAL, 0.10),
        ]
        config = PortfolioConfig(position_size_pct=0.10)

        forward = portfolio_mod.simulate(
            _result(trials), config, strategies=["overall", "buy_and_hold"]
        )
        reversed_ = portfolio_mod.simulate(
            _result(list(reversed(trials))),
            config,
            strategies=["overall", "buy_and_hold"],
        )

        self.assertEqual(forward.model_dump(), reversed_.model_dump())
        self.assertEqual(
            {trade.ticker: trade.stake for trade in forward.strategies[0].trades},
            {"AAA": 1_000.0, "BBB": 1_000.0},
        )

    def test_same_day_orders_share_cash_when_targets_exceed_balance(self):
        as_of = date(2025, 3, 1)
        trials = [_trial(ticker, as_of, Signal.BUY, 0.10) for ticker in ("AAA", "BBB", "CCC")]

        strategy = portfolio_mod.simulate(
            _result(trials),
            PortfolioConfig(position_size_pct=0.50),
            strategies=["overall"],
        ).strategies[0]

        self.assertAlmostEqual(sum(trade.stake for trade in strategy.trades), 10_000.0)
        self.assertTrue(all(trade.stake <= 10_000.0 / 3 for trade in strategy.trades))

    def test_failed_trial_blocks_portfolio_comparison(self):
        as_of = date(2025, 3, 1)
        valid = _trial("AAA", as_of, Signal.BUY, 0.10)
        failed = _trial("BBB", as_of, Signal.NEUTRAL, 0.0).model_copy(
            update={"exit_date": None, "realized_return": None, "error": "model failed"}
        )

        with self.assertRaisesRegex(ValueError, "1/2 incomplete"):
            portfolio_mod.simulate(
                _result([valid, failed]), strategies=["overall", "buy_and_hold"]
            )

    def test_winner_is_identified_and_deflated(self):
        report = portfolio_mod.simulate(_result(self._trials()))

        self.assertEqual(report.n_strategies_tested, len(report.strategies))
        self.assertIsNotNone(report.best_strategy)
        winner = next(s for s in report.strategies if s.strategy == report.best_strategy)
        for other in report.strategies:
            if other.trade_sharpe is not None:
                self.assertGreaterEqual(winner.trade_sharpe, other.trade_sharpe)

    def test_benchmark_comparison_and_promotion_gate_are_explicit(self):
        report = portfolio_mod.simulate(_result(self._trials()))

        benchmark = next(
            strategy for strategy in report.strategies if strategy.strategy == "buy_and_hold"
        )
        for strategy in report.strategies:
            self.assertAlmostEqual(
                strategy.excess_return_pct,
                strategy.total_return_pct - benchmark.total_return_pct,
            )
        self.assertFalse(report.benchmark_beaten)
        self.assertFalse(report.promotion_ready)

    def test_twice_cost_stress_is_reported_for_pipeline_and_strict_hold(self):
        report = portfolio_mod.simulate(
            _result(self._trials()),
            PortfolioConfig(cost_bps_per_side=25.0),
            strategies=["overall", "buy_and_hold"],
        )

        pipeline = next(item for item in report.strategies if item.strategy == "overall")
        strict = next(item for item in report.strategies if item.strategy == "buy_and_hold")

        self.assertIsNotNone(pipeline.twice_cost_return_pct)
        self.assertAlmostEqual(
            pipeline.twice_cost_excess_pct,
            pipeline.twice_cost_return_pct - strict.twice_cost_return_pct,
        )

    def test_promotion_drawdown_tolerance_has_correct_negative_sign(self):
        strict = StrategyReport(
            strategy="buy_and_hold",
            starting_balance=10_000,
            final_balance=12_000,
            total_return_pct=0.20,
            max_drawdown_pct=-0.27,
            n_trades=11,
            n_wins=7,
            n_losses=4,
            win_rate=7 / 11,
            best_trade_pct=0.3,
            worst_trade_pct=-0.2,
            equity_curve=[],
            trades=[],
        )

        def candidate(drawdown: float) -> StrategyReport:
            return StrategyReport(
                strategy="overall",
                starting_balance=10_000,
                final_balance=13_000,
                total_return_pct=0.30,
                max_drawdown_pct=drawdown,
                n_trades=40,
                n_wins=25,
                n_losses=15,
                win_rate=0.625,
                best_trade_pct=0.3,
                worst_trade_pct=-0.2,
                equity_curve=[],
                trades=[],
                beats_benchmark=True,
                effective_n=40,
                deflated_sharpe=0.98,
                strict_hold_log_excess_ci_95=(0.001, 0.02),
                twice_cost_excess_pct=0.01,
            )

        self.assertTrue(
            portfolio_mod._promotion_ready(
                [candidate(-0.30), strict], strict, modeled_cost=True
            )
        )
        self.assertFalse(
            portfolio_mod._promotion_ready(
                [candidate(-0.40), strict], strict, modeled_cost=True
            )
        )

    def test_same_day_open_entry_cannot_reuse_close_exit_proceeds(self):
        base = date(2025, 3, 1)
        first_exit = base + timedelta(days=33)
        trials = [
            _trial("AAA", base, Signal.BUY, 0.20, horizon=33).model_copy(
                update={"entry_date": base + timedelta(days=2), "exit_date": first_exit}
            ),
            _trial("BBB", first_exit - timedelta(days=1), Signal.BUY, 0.10).model_copy(
                update={"entry_date": first_exit}
            ),
        ]

        strategy = portfolio_mod.simulate(
            _result(trials),
            PortfolioConfig(position_size_pct=0.10),
            strategies=["overall"],
        ).strategies[0]

        self.assertEqual([trade.stake for trade in strategy.trades], [1_000.0, 900.0])

    def test_markdown_reports_selection_bias(self):
        markdown = portfolio_mod.to_markdown(portfolio_mod.simulate(_result(self._trials())))

        self.assertIn("Selection bias", markdown)
        self.assertIn("none modelled", markdown)
        self.assertIn("Benchmark gate", markdown)
        self.assertIn("conditions on signal timing", markdown)
        self.assertIn("Capital utilization", markdown)

    def test_no_trades_does_not_crash(self):
        base = date(2025, 3, 1)
        trials = [_trial("AAA", base, Signal.NEUTRAL, 0.01)]
        report = portfolio_mod.simulate(_result(trials), strategies=["overall"])
        self.assertEqual(report.strategies[0].n_trades, 0)
        self.assertIsNone(report.strategies[0].trade_sharpe)

    def test_signal_timing_long_matches_directional_trade_dates(self):
        base = date(2025, 3, 1)
        trials = [
            _trial("AAA", base, Signal.BUY, 0.10),
            _trial("AAA", base + timedelta(days=90), Signal.SELL, -0.10),
            _trial("AAA", base + timedelta(days=180), Signal.NEUTRAL, 0.05),
        ]

        report = portfolio_mod.simulate(
            _result(trials), strategies=["overall", "signal_timing_long"]
        )

        overall, timing_long = report.strategies
        self.assertEqual(overall.n_trades, 1)
        self.assertEqual(timing_long.n_trades, 2)
        self.assertEqual(timing_long.trades[0].entry_date, overall.trades[0].entry_date)

    def test_daily_price_path_captures_intra_trade_drawdown(self):
        entry = date(2025, 3, 3)
        middle = date(2025, 3, 4)
        exit_ = date(2025, 3, 5)
        trial = _trial("AAA", entry, Signal.BUY, 0.20).model_copy(
            update={
                "entry_date": entry,
                "entry_price": 100.0,
                "exit_date": exit_,
                "exit_price": 120.0,
                "realized_return": 0.20,
            }
        )
        result = _result([trial]).model_copy(
            update={
                "price_paths": {
                    "AAA": [
                        PriceBar(date=entry, open=100, high=101, low=99, close=100, volume=1),
                        PriceBar(date=middle, open=100, high=101, low=49, close=50, volume=1),
                        PriceBar(date=exit_, open=50, high=121, low=49, close=120, volume=1),
                    ]
                }
            }
        )

        report = portfolio_mod.simulate(
            result,
            PortfolioConfig(position_size_pct=0.5),
            strategies=["overall"],
        ).strategies[0]

        self.assertEqual(report.drawdown_basis, "daily_close_mark_to_market")
        self.assertAlmostEqual(report.final_balance, 11_000.0)
        self.assertAlmostEqual(report.max_drawdown_pct, -0.25)

    def test_capital_utilization_uses_one_shared_calendar_and_includes_exit_day(self):
        first_entry = date(2025, 3, 3)
        second_entry = date(2025, 3, 4)
        exit_ = date(2025, 3, 5)
        trials = [
            _trial("AAA", date(2025, 3, 1), Signal.BUY, 0.05).model_copy(
                update={
                    "entry_date": first_entry,
                    "entry_price": 100.0,
                    "exit_date": exit_,
                    "exit_price": 105.0,
                }
            ),
            _trial("BBB", date(2025, 3, 2), Signal.BUY, 0.05).model_copy(
                update={
                    "entry_date": second_entry,
                    "entry_price": 100.0,
                    "exit_date": exit_,
                    "exit_price": 105.0,
                }
            ),
        ]
        bars = [
            PriceBar(date=day, open=100, high=106, low=99, close=105, volume=1)
            for day in (first_entry, second_entry, exit_)
        ]
        result = _result(trials).model_copy(
            update={"price_paths": {"AAA": bars, "BBB": bars}}
        )

        strategy = portfolio_mod.simulate(
            result, PortfolioConfig(), strategies=["overall"]
        ).strategies[0]

        # Entries are on separate days: the second uses the reduced cash balance.
        self.assertAlmostEqual(strategy.mean_committed_principal_pct, 0.16)
        self.assertAlmostEqual(strategy.peak_committed_principal_pct, 0.19)
        self.assertEqual(strategy.capital_utilization_active_sessions, 3)
        self.assertEqual(strategy.capital_utilization_market_sessions, 3)
        self.assertIn("not mark-to-market exposure", strategy.capital_utilization_basis)

    def test_matched_exposure_passive_uses_same_trade_window_and_stake(self):
        entry = date(2025, 3, 3)
        exit_ = date(2025, 3, 5)
        trial = _trial("AAA", date(2025, 3, 1), Signal.BUY, 0.20).model_copy(
            update={
                "entry_date": entry,
                "entry_price": 100.0,
                "exit_date": exit_,
                "exit_price": 120.0,
                "realized_return": 0.20,
            }
        )
        result = _result([trial]).model_copy(
            update={
                "price_paths": {
                    "AAA": [
                        PriceBar(date=entry, open=100, high=111, low=99, close=110, volume=1),
                        PriceBar(date=exit_, open=110, high=121, low=109, close=120, volume=1),
                    ],
                    "BBB": [
                        PriceBar(date=entry, open=100, high=101, low=99, close=100, volume=1),
                        PriceBar(date=exit_, open=100, high=101, low=79, close=80, volume=1),
                    ],
                }
            }
        )

        strategy = portfolio_mod.simulate(
            result, strategies=["overall"]
        ).strategies[0]

        self.assertAlmostEqual(strategy.matched_exposure_baseline_return_pct, 0.0)
        self.assertAlmostEqual(strategy.matched_exposure_excess_pct, 0.02)

    def test_missing_daily_price_path_does_not_report_zero_drawdown(self):
        result = _result(self._trials())

        report = portfolio_mod.simulate(
            result, strategies=["overall"]
        ).strategies[0]

        self.assertIsNone(report.max_drawdown_pct)
        self.assertEqual(report.drawdown_basis, "event_only_incomplete")
        self.assertIsNone(report.mean_committed_principal_pct)
        self.assertIsNone(report.capital_utilization_market_sessions)


if __name__ == "__main__":
    unittest.main()
