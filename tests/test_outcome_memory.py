"""Outcome memory: leakage guard, calibration arithmetic, and store round-tripping."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from stock_analysis.memory.outcomes import (
    OutcomeRecord,
    OutcomeStore,
    build_memory_context,
    compute_calibration,
    records_from_backtest,
)
from stock_analysis.models.agent_reports import Signal


def _record(
    as_of: str,
    exit_: str | None = None,
    signal: Signal = Signal.BUY,
    realized: float | None = 0.05,
    conviction: float = 0.6,
    convergence: float = 0.75,
    horizon: int = 30,
    ticker: str = "AAPL",
    source: str = "backtest",
) -> OutcomeRecord:
    return OutcomeRecord(
        ticker=ticker,
        as_of_date=date.fromisoformat(as_of),
        horizon_days=horizon,
        signal=signal,
        conviction_score=conviction,
        signal_convergence=convergence,
        entry_price=100.0,
        exit_date=date.fromisoformat(exit_) if exit_ else None,
        exit_price=105.0,
        realized_return=realized,
        source=source,
    )


class LeakageGuardTests(unittest.TestCase):
    """A dated analysis must not see an outcome that had not resolved yet."""

    def test_record_resolving_before_the_analysis_date_is_visible(self):
        record = _record("2024-01-01", "2024-01-31")
        self.assertTrue(record.visible_on(date(2024, 3, 1)))

    def test_record_resolving_after_the_analysis_date_is_hidden(self):
        record = _record("2024-01-01", "2024-06-01")
        self.assertFalse(record.visible_on(date(2024, 3, 1)))

    def test_entry_in_the_past_does_not_make_a_future_exit_visible(self):
        # The trap this guard exists for: entry is old, but the outcome is not
        # yet known on the analysis date.
        record = _record("2023-12-01", "2024-05-01")
        self.assertFalse(record.visible_on(date(2024, 1, 1)))

    def test_exit_on_the_analysis_date_itself_is_hidden(self):
        record = _record("2024-01-01", "2024-03-01")
        self.assertFalse(record.visible_on(date(2024, 3, 1)))

    def test_unresolved_record_is_never_visible_to_a_dated_run(self):
        record = _record("2024-01-01", exit_=None, realized=None)
        self.assertFalse(record.visible_on(date(2030, 1, 1)))

    def test_live_run_with_no_date_sees_everything(self):
        self.assertTrue(_record("2024-01-01", "2024-06-01").visible_on(None))

    def test_store_applies_the_filter_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutcomeStore(tmp)
            store.append(
                [
                    _record("2024-01-01", "2024-01-31"),
                    _record("2024-04-01", "2024-04-30"),
                    _record("2024-08-01", "2024-08-31"),
                ]
            )
            visible = store.load("AAPL", before=date(2024, 5, 1))
            self.assertEqual([r.as_of_date.isoformat() for r in visible],
                             ["2024-01-01", "2024-04-01"])
            self.assertEqual(len(store.load("AAPL")), 3)


class CalibrationTests(unittest.TestCase):
    def test_hit_rate_counts_direction_not_magnitude(self):
        records = [
            _record("2024-01-01", "2024-01-31", Signal.BUY, realized=0.02),
            _record("2024-02-01", "2024-02-28", Signal.BUY, realized=-0.09),
            _record("2024-03-01", "2024-03-31", Signal.SELL, realized=-0.04),
            _record("2024-04-01", "2024-04-30", Signal.SELL, realized=0.01),
        ]
        summary = compute_calibration("AAPL", records)
        self.assertEqual(summary.directional_trials, 4)
        self.assertEqual(summary.hit_rate, 0.5)

    def test_neutral_calls_are_excluded_from_hit_rate(self):
        records = [
            _record("2024-01-01", "2024-01-31", Signal.NEUTRAL, realized=0.05),
            _record("2024-02-01", "2024-02-28", Signal.BUY, realized=0.05),
        ]
        summary = compute_calibration("AAPL", records)
        self.assertEqual(summary.neutral_trials, 1)
        self.assertEqual(summary.directional_trials, 1)
        self.assertEqual(summary.hit_rate, 1.0)

    def test_unresolved_records_are_not_counted_as_misses(self):
        records = [
            _record("2024-01-01", "2024-01-31", realized=0.05),
            _record("2024-02-01", exit_=None, realized=None),
        ]
        summary = compute_calibration("AAPL", records)
        self.assertEqual(summary.trials, 1)
        self.assertEqual(summary.hit_rate, 1.0)

    def test_conviction_separation_is_reported_when_it_fails(self):
        records = [
            # High conviction, all wrong.
            *[
                _record(f"2024-01-{d:02d}", f"2024-02-{d:02d}", conviction=0.9, realized=-0.05)
                for d in range(1, 4)
            ],
            # Low conviction, all right.
            *[
                _record(f"2024-03-{d:02d}", f"2024-04-{d:02d}", conviction=0.35, realized=0.05)
                for d in range(1, 4)
            ],
        ]
        summary = compute_calibration("AAPL", records)
        self.assertEqual(summary.high_conviction_hit_rate, 0.0)
        self.assertEqual(summary.low_conviction_hit_rate, 1.0)
        self.assertIs(summary.conviction_separates, False)

    def test_conviction_separation_is_unknown_on_a_tiny_sample(self):
        records = [
            _record("2024-01-01", "2024-01-31", conviction=0.9, realized=0.05),
            _record("2024-02-01", "2024-02-28", conviction=0.2, realized=-0.05),
        ]
        self.assertIsNone(compute_calibration("AAPL", records).conviction_separates)

    def test_small_samples_are_not_called_a_track_record(self):
        records = [_record("2024-01-01", "2024-01-31")]
        self.assertFalse(compute_calibration("AAPL", records).sufficient_sample)

    def test_empty_history_yields_zero_trials_not_an_error(self):
        summary = compute_calibration("AAPL", [])
        self.assertEqual(summary.trials, 0)
        self.assertIsNone(summary.hit_rate)

    def test_per_signal_buckets_are_broken_out(self):
        records = [
            _record("2024-01-01", "2024-01-31", Signal.STRONG_BUY, realized=0.10),
            _record("2024-02-01", "2024-02-28", Signal.BUY, realized=-0.02),
        ]
        buckets = {b.signal: b for b in compute_calibration("AAPL", records).buckets}
        self.assertEqual(buckets[Signal.STRONG_BUY].hit_rate, 1.0)
        self.assertEqual(buckets[Signal.BUY].hit_rate, 0.0)


class StoreTests(unittest.TestCase):
    def test_append_is_idempotent_on_rerun(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutcomeStore(tmp)
            records = [_record("2024-01-01", "2024-01-31")]
            self.assertEqual(store.append(records), 1)
            self.assertEqual(store.append(records), 0)
            self.assertEqual(len(store.load("AAPL")), 1)

    def test_records_split_by_ticker(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutcomeStore(tmp)
            store.append(
                [
                    _record("2024-01-01", "2024-01-31", ticker="AAPL"),
                    _record("2024-01-01", "2024-01-31", ticker="MSFT"),
                ]
            )
            self.assertEqual(len(store.load("AAPL")), 1)
            self.assertEqual(len(store.load("MSFT")), 1)

    def test_malformed_line_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutcomeStore(tmp)
            store.append([_record("2024-01-01", "2024-01-31")])
            path = Path(tmp) / "AAPL" / "outcomes.jsonl"
            path.write_text(path.read_text() + '{"broken": true}\n' + "\n")
            self.assertEqual(len(store.load("AAPL")), 1)

    def test_missing_file_loads_as_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(OutcomeStore(tmp).load("NOSUCH"), [])

    def test_calibration_file_is_written_only_with_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = OutcomeStore(tmp)
            self.assertIsNone(store.save_calibration("AAPL"))
            store.append([_record("2024-01-01", "2024-01-31")])
            self.assertIsNotNone(store.save_calibration("AAPL"))


class MemoryContextTests(unittest.TestCase):
    def test_returns_none_with_no_history(self):
        self.assertIsNone(build_memory_context([], compute_calibration("AAPL", [])))

    def test_context_states_hit_rate_and_warns_on_small_samples(self):
        records = [_record("2024-01-01", "2024-01-31")]
        text = build_memory_context(records, compute_calibration("AAPL", records))
        self.assertIn("hit rate", text.lower())
        self.assertIn("too few trials", text)

    def test_context_warns_against_flipping_on_past_misses(self):
        records = [_record("2024-01-01", "2024-01-31", realized=-0.05)]
        text = build_memory_context(records, compute_calibration("AAPL", records))
        self.assertIn("not evidence about the stock's future", text)

    def test_context_is_truncated_to_max_records(self):
        records = [
            _record(f"2024-0{m}-01", f"2024-0{m}-28") for m in range(1, 8)
        ]
        text = build_memory_context(
            records, compute_calibration("AAPL", records), max_records=3
        )
        self.assertEqual(text.count("called **"), 3)


class _FakeTrial:
    def __init__(self, realized=0.05, error=None):
        self.ticker = "AAPL"
        self.as_of_date = date(2024, 1, 1)
        self.horizon_days = 30
        self.overall_signal = Signal.BUY
        self.conviction_score = 0.6
        self.signal_convergence = 0.7
        self.entry_price = 100.0
        self.exit_date = date(2024, 1, 31)
        self.exit_price = 105.0
        self.realized_return = realized
        self.error = error


class _FakeResult:
    def __init__(self, trials):
        self.trials = trials
        self.settings = {"horizon_days": 30}


class BacktestBridgeTests(unittest.TestCase):
    def test_converts_resolved_trials(self):
        records = records_from_backtest(_FakeResult([_FakeTrial()]))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].realized_return, 0.05)

    def test_skips_errored_and_unresolved_trials(self):
        result = _FakeResult(
            [_FakeTrial(realized=None), _FakeTrial(error="no forward price")]
        )
        self.assertEqual(records_from_backtest(result), [])


if __name__ == "__main__":
    unittest.main()
