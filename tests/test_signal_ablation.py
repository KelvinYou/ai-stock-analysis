from __future__ import annotations

import unittest
from datetime import date

from stock_analysis.backtest.cross_sectional import CrossSectionalPeriod
from stock_analysis.backtest.runner import BacktestTrial
from stock_analysis.backtest.signal_ablation import (
    SignalAblationConfig,
    run_signal_ablation,
    signal_ablation_to_markdown,
)
from stock_analysis.models.agent_reports import Signal


class SignalAblationTests(unittest.TestCase):
    def _run(self, *, cost_bps: float = 0.0, signals=None, missing_entry_date=False):
        as_of = date(2020, 3, 31)
        entry = None if missing_entry_date else date(2020, 4, 1)
        exit_date = date(2020, 4, 30)
        returns = {"AAA": 0.20, "BBB": -0.20, "CCC": 0.05, "DDD": 0.0}
        signals = signals or {
            "AAA": Signal.BUY,
            "BBB": Signal.NEUTRAL,
            "CCC": Signal.STRONG_BUY,
            "DDD": Signal.SELL,
        }
        trials = [
            BacktestTrial(
                ticker=ticker,
                as_of_date=as_of,
                horizon_days=30,
                entry_price=100.0,
                exit_date=exit_date,
                exit_price=100.0 * (1.0 + realized_return),
                realized_return=realized_return,
                overall_signal=signals[ticker],
                conviction_score=0.8 if signals[ticker] == Signal.STRONG_BUY else 0.4,
                signal_convergence=0.8,
                agent_signals={},
                entry_date=entry,
            )
            for ticker, realized_return in returns.items()
        ]
        cost_rate = cost_bps / 10_000.0
        allocator_return = (1.0 + (returns["AAA"] + returns["BBB"]) / 2.0) * (
            1.0 - cost_rate
        ) ** 2 - 1.0
        allocator_period = CrossSectionalPeriod(
            as_of_date=as_of,
            entry_date=entry,
            exit_date=exit_date,
            selected_tickers=["AAA", "BBB"],
            turnover=1.0,
            gross_return=(returns["AAA"] + returns["BBB"]) / 2.0,
            allocation_cost=1.0 - (1.0 - cost_rate) ** 2,
            net_return=allocator_return,
        )
        report = run_signal_ablation(
            trials,
            [allocator_period],
            config=SignalAblationConfig(
                top_n=2,
                cost_bps_per_side=cost_bps,
                bootstrap_block_periods=3,
                bootstrap_resamples=100,
                permutation_resamples=1_000,
                permutation_seed=17,
            ),
        )
        return report

    def test_ai_and_hybrid_arms_use_fixed_sleeves_and_exposure_matched_controls(self):
        report = self._run()

        self.assertEqual(report.candidate_arms_tested, 2)
        self.assertEqual(report.ai_only.net_compound_return, 0.125)
        self.assertEqual(report.ai_only.mean_exposure, 1.0)
        self.assertAlmostEqual(report.hybrid.net_compound_return, 0.10)
        self.assertEqual(report.hybrid.mean_exposure, 0.5)
        self.assertEqual(report.period_log[0].hybrid_matched_allocator_net_return, 0.0)
        self.assertEqual(report.hybrid.paired_log_excess_ci_95, None)

    def test_conditional_permutation_preserves_exposure_and_is_reproducible(self):
        first = self._run()
        second = self._run()

        self.assertEqual(first.permutation_status, "INFORMATIVE")
        self.assertEqual(
            first.permutation_upper_tail_p_value,
            second.permutation_upper_tail_p_value,
        )
        self.assertGreater(first.permutation_upper_tail_p_value, 0.35)
        self.assertLess(first.permutation_upper_tail_p_value, 0.65)
        self.assertEqual(first.permutation_informative_periods, 1)

    def test_costs_are_charged_only_on_invested_hybrid_weight(self):
        report = self._run(cost_bps=10.0)

        expected_hybrid = 0.5 * (1.2 * (1.0 - 0.001) ** 2 - 1.0)
        self.assertAlmostEqual(report.period_log[0].hybrid_net_return, expected_hybrid)
        self.assertAlmostEqual(report.period_log[0].hybrid_exposure, 0.5)

    def test_all_positive_labels_make_conditional_permutation_uninformative(self):
        report = self._run(
            signals={
                "AAA": Signal.BUY,
                "BBB": Signal.STRONG_BUY,
                "CCC": Signal.NEUTRAL,
                "DDD": Signal.SELL,
            }
        )

        self.assertEqual(report.permutation_status, "UNINFORMATIVE")
        self.assertIsNone(report.permutation_upper_tail_p_value)
        self.assertIsNone(report.permutation_null_interval_95)
        self.assertIn("Uninformative", signal_ablation_to_markdown(report))

    def test_legacy_reports_without_open_entry_dates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "explicit next-session entry dates are required"):
            self._run(missing_entry_date=True)


if __name__ == "__main__":
    unittest.main()
