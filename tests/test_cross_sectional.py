from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from stock_analysis.backtest.cross_sectional import (
    CrossSectionalConfig,
    CrossSectionalReport,
    OverlappingSealedWindowsError,
    run_cross_sectional_backtest,
    run_cross_sectional_trial_backtest,
    to_markdown,
    trial_allocation_to_markdown,
)
from stock_analysis.backtest.runner import BacktestTrial
from stock_analysis.models.agent_reports import Signal


def _history(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=len(closes), freq="ME")
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000] * len(closes),
        }
    )


def _trial(
    ticker: str,
    as_of: date,
    exit_date: date,
    entry_price: float,
    exit_price: float,
) -> BacktestTrial:
    return BacktestTrial(
        ticker=ticker,
        as_of_date=as_of,
        horizon_days=(exit_date - as_of).days,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        realized_return=exit_price / entry_price - 1.0,
        overall_signal=Signal.NEUTRAL,
        conviction_score=0.0,
        signal_convergence=0.0,
        agent_signals={},
    )


class CrossSectionalBacktestTests(unittest.TestCase):
    def _histories(self) -> dict[str, pd.DataFrame]:
        return {
            "AAA": _history([100, 110, 120, 130, 140, 150, 160, 170]),
            "BBB": _history([100, 90, 95, 96, 97, 98, 99, 100]),
        }

    def test_signal_uses_only_trailing_months_and_next_period_return(self):
        report = run_cross_sectional_backtest(
            self._histories(),
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1, cost_bps_per_side=0),
        )

        first = report.period_log[0]
        self.assertEqual(first.as_of_date, date(2020, 3, 31))
        self.assertEqual(first.entry_date, date(2020, 4, 30))
        self.assertEqual(first.exit_date, date(2020, 5, 31))
        self.assertEqual(first.selected_tickers, ["AAA"])
        self.assertAlmostEqual(first.gross_return, 140 / 130 - 1)

    def test_strict_benchmark_uses_same_window_and_costs(self):
        report = run_cross_sectional_backtest(
            self._histories(),
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1, cost_bps_per_side=10),
        )

        gross_benchmark = ((170 / 130 - 1) + (100 / 96 - 1)) / 2
        expected = (1 + gross_benchmark) * (1 - 0.001) ** 2 - 1
        self.assertAlmostEqual(report.buy_and_hold_return, expected)
        self.assertEqual(report.oos_start, date(2020, 3, 31))
        self.assertEqual(report.oos_end, date(2020, 8, 31))
        self.assertEqual(report.signal_date_cutoff, date(2020, 7, 31))
        self.assertEqual(report.data_end, report.oos_end)

    def test_execution_uses_next_common_session_open(self):
        histories = self._histories()
        histories["AAA"].loc[3, "open"] = 200.0
        histories["AAA"].loc[4, "open"] = 220.0

        report = run_cross_sectional_backtest(
            histories,
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1, cost_bps_per_side=0),
        )

        first = report.period_log[0]
        self.assertEqual(first.entry_date, date(2020, 4, 30))
        self.assertEqual(first.exit_date, date(2020, 5, 31))
        self.assertAlmostEqual(first.gross_return, 220 / 200 - 1)

    def test_timezone_aware_price_dates_keep_the_exchange_session_day(self):
        histories = self._histories()
        for frame in histories.values():
            frame["date"] = pd.DatetimeIndex(pd.to_datetime(frame["date"])).tz_localize(
                "America/New_York"
            )

        report = run_cross_sectional_backtest(
            histories,
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1, cost_bps_per_side=0),
        )

        self.assertEqual(report.period_log[0].entry_date, date(2020, 4, 30))

    def test_reports_rebalanced_equal_weight_passive_baseline_and_paired_ci(self):
        report = run_cross_sectional_backtest(
            self._histories(),
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(
                lookback_months=2,
                top_n=1,
                cost_bps_per_side=10,
                bootstrap_block_periods=1,
                bootstrap_resamples=200,
                bootstrap_seed=17,
            ),
        )

        self.assertGreater(
            report.matched_passive_excess_return,
            0.0,
        )
        self.assertEqual(len(report.period_log), 4)
        self.assertTrue(all(p.matched_passive_net_return is not None for p in report.period_log))
        self.assertIsNotNone(report.strict_hold_log_excess_ci_95)
        self.assertIsNotNone(report.matched_passive_log_excess_ci_95)

    def test_markdown_exposes_benchmark_and_non_ai_scope(self):
        report = run_cross_sectional_backtest(
            self._histories(),
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1),
        )

        markdown = to_markdown(report)

        self.assertIn("Strict equal-weight buy-and-hold", markdown)
        self.assertIn("not an AI forecast", markdown)

    def test_legacy_report_parses_without_relabelling_old_drawdown(self):
        report = run_cross_sectional_backtest(
            self._histories(),
            start=date(2020, 3, 1),
            end=date(2020, 7, 31),
            config=CrossSectionalConfig(lookback_months=2, top_n=1),
        )
        legacy = report.model_dump(mode="python")
        for key in (
            "matched_passive_return",
            "matched_passive_excess_return",
            "strict_hold_log_excess_ci_95",
            "matched_passive_log_excess_ci_95",
            "buy_and_hold_max_drawdown",
            "matched_passive_max_drawdown",
            "signal_date_cutoff",
            "drawdown_basis",
            "price_basis",
        ):
            legacy.pop(key, None)
        legacy["config"].pop("bootstrap_block_periods")
        legacy["config"].pop("bootstrap_resamples")
        legacy["config"].pop("bootstrap_seed")
        for period in legacy["period_log"]:
            for key in (
                "entry_date",
                "matched_passive_gross_return",
                "matched_passive_net_return",
                "matched_passive_turnover",
                "strict_hold_net_return",
            ):
                period.pop(key, None)

        parsed = CrossSectionalReport.model_validate(legacy)

        self.assertEqual(parsed.drawdown_basis, "rebalance_period_end")
        self.assertEqual(parsed.price_basis, "close")

    def test_sealed_trial_allocator_ranks_before_reading_forward_returns(self):
        histories = {
            "AAA": _history([100, 110, 120, 130, 140, 150]),
            "BBB": _history([100, 90, 95, 1_000, 1_000, 1_000]),
        }
        as_of = date(2020, 3, 31)
        report = run_cross_sectional_trial_backtest(
            histories,
            [
                _trial("AAA", as_of, date(2020, 4, 30), 120, 130),
                _trial("BBB", as_of, date(2020, 4, 30), 95, 96),
            ],
            config=CrossSectionalConfig(
                lookback_months=2, top_n=1, cost_bps_per_side=0
            ),
        )

        self.assertEqual(report.period_log[0].selected_tickers, ["AAA"])
        self.assertAlmostEqual(report.period_log[0].gross_return, 130 / 120 - 1)

    def test_sealed_trial_allocator_uses_strict_benchmark_cost_contract(self):
        histories = {
            "AAA": _history([100, 110, 120, 130, 140]),
            "BBB": _history([100, 90, 95, 96, 97]),
        }
        trials = [
            _trial("AAA", date(2020, 3, 31), date(2020, 4, 30), 120, 130),
            _trial("BBB", date(2020, 3, 31), date(2020, 4, 30), 95, 96),
            _trial("AAA", date(2020, 5, 1), date(2020, 5, 29), 130, 140),
            _trial("BBB", date(2020, 5, 1), date(2020, 5, 29), 96, 97),
        ]
        report = run_cross_sectional_trial_backtest(
            histories,
            trials,
            config=CrossSectionalConfig(
                lookback_months=2, top_n=1, cost_bps_per_side=10
            ),
        )

        expected = (
            ((140 / 120) * (1 - 0.001) ** 2 - 1)
            + ((97 / 95) * (1 - 0.001) ** 2 - 1)
        ) / 2
        self.assertAlmostEqual(report.buy_and_hold_return, expected)
        self.assertEqual(report.completed_trials, 4)

    def test_sealed_allocator_compares_with_all_names_on_same_windows(self):
        histories = self._histories()
        as_of = date(2020, 3, 31)
        report = run_cross_sectional_trial_backtest(
            histories,
            [
                _trial("AAA", as_of, date(2020, 4, 30), 120, 132),
                _trial("BBB", as_of, date(2020, 4, 30), 95, 100),
            ],
            config=CrossSectionalConfig(
                lookback_months=2,
                top_n=1,
                cost_bps_per_side=10,
                bootstrap_block_periods=1,
                bootstrap_resamples=200,
                bootstrap_seed=17,
            ),
        )

        expected_passive = ((132 / 120 - 1) + (100 / 95 - 1)) / 2
        expected_passive = (1 + expected_passive) * (1 - 0.001) ** 2 - 1
        self.assertAlmostEqual(report.matched_passive_return, expected_passive)
        self.assertGreater(report.matched_passive_excess_return, 0.0)
        self.assertIsNone(report.matched_passive_log_excess_ci_95)

    def test_sealed_allocator_rejects_overlapping_windows(self):
        as_of_1 = date(2020, 3, 31)
        as_of_2 = date(2020, 4, 15)
        trials = [
            _trial("AAA", as_of_1, date(2020, 4, 30), 120, 130),
            _trial("BBB", as_of_1, date(2020, 4, 30), 95, 96),
            _trial("AAA", as_of_2, date(2020, 5, 15), 130, 140),
            _trial("BBB", as_of_2, date(2020, 5, 15), 96, 97),
        ]

        with self.assertRaisesRegex(OverlappingSealedWindowsError, "overlapping sealed windows"):
            run_cross_sectional_trial_backtest(
                self._histories(),
                trials,
                config=CrossSectionalConfig(lookback_months=2, top_n=1),
            )

    def test_sealed_trial_markdown_keeps_allocator_separate_from_ai(self):
        histories = self._histories()
        as_of = date(2020, 3, 31)
        report = run_cross_sectional_trial_backtest(
            histories,
            [
                _trial("AAA", as_of, date(2020, 4, 30), 120, 130),
                _trial("BBB", as_of, date(2020, 4, 30), 95, 96),
            ],
            config=CrossSectionalConfig(lookback_months=2, top_n=1),
        )

        markdown = trial_allocation_to_markdown(report)

        self.assertIn("Sealed-Trial Cross-Sectional Allocation", markdown)
        self.assertIn("not an AI forecast result", markdown)
        self.assertIn("Strict equal-weight buy-and-hold", markdown)


if __name__ == "__main__":
    unittest.main()
