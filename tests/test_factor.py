from __future__ import annotations

import unittest
from datetime import date, timedelta
from itertools import pairwise

import pandas as pd

from stock_analysis.backtest.factor import (
    FactorConfig,
    clean_price_history,
    run_factor_backtest,
    to_markdown,
)


def _price_frame() -> pd.DataFrame:
    closes = [
        10,
        9,
        10,
        11,
        12,
        13,
        12,
        11,
        10,
        11,
        12,
        13,
        12,
        11,
        10,
        11,
        12,
        13,
        14,
        13,
        12,
        11,
        12,
        13,
        14,
        15,
        14,
        13,
        12,
        13,
        14,
        15,
        16,
        15,
        14,
        13,
    ]
    return pd.DataFrame(
        {
            "date": [date(2024, 1, 1) + timedelta(days=i) for i in range(len(closes))],
            "open": [close * 0.98 for close in closes],
            "high": closes,
            "low": [close * 0.95 for close in closes],
            "close": closes,
            "volume": [1_000] * len(closes),
        }
    )


class CleanPriceHistoryTests(unittest.TestCase):
    def test_sorts_deduplicates_and_drops_invalid_rows_without_filling(self):
        frame = pd.DataFrame(
            {
                "date": ["2024-01-03", "bad", "2024-01-01", "2024-01-01"],
                "open": [12, 10, 0, 11],
                "close": [12, 10, 10, 11],
            }
        )

        cleaned = clean_price_history(frame)

        self.assertEqual(cleaned["date"].dt.strftime("%Y-%m-%d").tolist(), [
            "2024-01-01",
            "2024-01-03",
        ])
        self.assertEqual(cleaned["open"].tolist(), [11, 12])
        self.assertEqual(len(cleaned), 2)

    def test_requires_open_close_and_date(self):
        with self.assertRaisesRegex(ValueError, "missing required columns"):
            clean_price_history(pd.DataFrame({"date": ["2024-01-01"], "close": [10]}))


class FactorBacktestTests(unittest.TestCase):
    def _config(self, cost: float = 0.0) -> FactorConfig:
        return FactorConfig(
            lookback_bars=2,
            holding_bars=2,
            initial_train_bars=4,
            test_window_bars=6,
            cost_bps_per_side=cost,
        )

    def test_signal_uses_past_close_and_enters_next_bar(self):
        report = run_factor_backtest("TEST", _price_frame(), config=self._config())

        self.assertGreater(report.trades, 0)
        trade = report.trade_log[0]
        frame = _price_frame()
        signal_mask = pd.to_datetime(frame["date"]).dt.date == trade.signal_date
        signal_index = frame.index[signal_mask][0]
        expected_momentum = frame.loc[signal_index, "close"] / frame.loc[signal_index - 2, "close"] - 1

        self.assertAlmostEqual(trade.momentum, expected_momentum)
        self.assertEqual(
            trade.entry_date,
            pd.Timestamp(frame.loc[signal_index + 1, "date"]).date(),
        )
        self.assertAlmostEqual(trade.entry_price, frame.loc[signal_index + 1, "open"])
        self.assertNotEqual(trade.signal_date, trade.entry_date)

    def test_walk_forward_trades_do_not_overlap(self):
        report = run_factor_backtest("TEST", _price_frame(), config=self._config())

        for previous, current in pairwise(report.trade_log):
            self.assertLess(previous.exit_date, current.entry_date)
        self.assertEqual(
            report.opportunities,
            report.trades + report.flat_opportunities,
        )
        self.assertGreater(len(report.folds), 1)

    def test_costs_reduce_each_trade_by_two_legs(self):
        gross = run_factor_backtest("TEST", _price_frame(), config=self._config())
        costed = run_factor_backtest("TEST", _price_frame(), config=self._config(50.0))

        self.assertEqual(len(gross.trade_log), len(costed.trade_log))
        for gross_trade, costed_trade in zip(gross.trade_log, costed.trade_log, strict=True):
            expected = (1 + gross_trade.gross_return) * (1 - 0.005) ** 2 - 1
            self.assertAlmostEqual(costed_trade.net_return, expected)
            self.assertLess(costed_trade.net_return, gross_trade.gross_return)
        self.assertLess(costed.net_compound_return, gross.net_compound_return)

    def test_markdown_exposes_protocol_and_costed_metrics(self):
        report = run_factor_backtest("TEST", _price_frame(), config=self._config(10.0))

        markdown = to_markdown(report)

        self.assertIn("Momentum Factor Research Report", markdown)
        self.assertIn("next-bar open", markdown)
        self.assertIn("Gross compound return", markdown)
        self.assertIn("Net compound return", markdown)
        self.assertIn("Walk-forward folds", markdown)

    def test_rejects_test_window_without_a_complete_trade(self):
        with self.assertRaisesRegex(ValueError, "greater than holding_bars"):
            run_factor_backtest(
                "TEST",
                _price_frame(),
                config=FactorConfig(
                    lookback_bars=2,
                    holding_bars=2,
                    initial_train_bars=4,
                    test_window_bars=2,
                ),
            )


if __name__ == "__main__":
    unittest.main()
