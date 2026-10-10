import runpy
from datetime import date
from pathlib import Path

import pytest

from stock_analysis.backtest.runner import BacktestResult, BacktestTrial
from stock_analysis.models.agent_reports import Signal

HELPERS = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts/research_pipeline_gaps.py")
)


def test_gap_decomposition_reconciles_and_preserves_unavailable():
    split = HELPERS["gap_decomposition"](-0.02, -0.03, 0.20)
    assert split["selection_vs_matched"] == pytest.approx(0.01)
    assert split["deployment_and_timing_vs_hold"] == pytest.approx(-0.23)
    assert split["total_excess_vs_hold"] == pytest.approx(
        split["selection_vs_matched"] + split["deployment_and_timing_vs_hold"]
    )
    no_trades = HELPERS["gap_decomposition"](0, None, 0.20)
    assert no_trades["selection_vs_matched"] is None
    assert no_trades["deployment_and_timing_vs_hold"] is None


def test_refusal_partition_does_not_count_overlapping_reasons_as_separate_calls():
    partition = HELPERS["refusal_partition"]
    assert partition(Signal.BUY, Signal.NEUTRAL) == "raw_buy_declined"
    assert partition(Signal.STRONG_SELL, Signal.NEUTRAL) == "raw_sell_declined"
    assert partition(Signal.NEUTRAL, Signal.NEUTRAL) == "raw_neutral"
    assert partition(Signal.BUY, Signal.BUY) == "buy_passed_guards"
    assert partition(Signal.SELL, Signal.SELL) == "sell_passed_guards_long_only_skip"
    with pytest.raises(ValueError, match="reverse"):
        partition(Signal.BUY, Signal.SELL)
    with pytest.raises(ValueError, match="neutral source"):
        partition(Signal.NEUTRAL, Signal.BUY)


def test_episode_selections_ignore_outcomes_and_ft_does_not_inherit_ai_ranking():
    trials = []
    histories = {}
    for index, ticker in enumerate(["AAA", "BBB", "CCC", "DDD"]):
        histories[ticker] = [
            {"date": "2024-01-01", "open": 100, "close": 100},
            {"date": "2025-01-01", "open": 140 - 10 * index, "close": 140 - 10 * index},
            {"date": "2025-01-31", "open": 140 - 10 * index, "close": 140 - 10 * index},
        ]
        for as_of, entry, exit_ in [
            (date(2025, 1, 1), date(2025, 1, 2), date(2025, 2, 1)),
            (date(2025, 1, 31), date(2025, 2, 3), date(2025, 3, 3)),
        ]:
            trials.append(BacktestTrial(
                ticker=ticker, as_of_date=as_of, horizon_days=30,
                entry_date=entry, exit_date=exit_, entry_price=100, exit_price=105,
                realized_return=0.05, overall_signal=Signal.BUY,
                conviction_score=(index + 1) / 4, signal_convergence=1,
                agent_signals={"ft_weighted": "buy", "ft_agreement": "neutral"},
            ))
    result = BacktestResult(trials=trials, settings={},
                            started_at=date(2025, 1, 1), finished_at=date(2025, 3, 3))
    original = result.model_dump(mode="json")
    before = HELPERS["episode_experiment"](result, histories, 10)
    changed = result.model_copy(deep=True)
    changed.trials.reverse()
    for trial in changed.trials:
        trial.realized_return = 0.75 if trial.ticker == "DDD" else -0.10
        trial.exit_price = trial.entry_price * (1 + trial.realized_return)
    after = HELPERS["episode_experiment"](changed, histories, 10)
    assert before["selected_dates"] == after["selected_dates"]
    assert [p["selected_tickers"] for p in before["allocator"]["period_log"]] == [
        p["selected_tickers"] for p in after["allocator"]["period_log"]
    ]
    for label in ["ai", "ft_weighted", "ft_agreement"]:
        for a, b in zip(before["signal_views"][label]["period_log"],
                        after["signal_views"][label]["period_log"], strict=True):
            assert a["ai_only_selected_tickers"] == b["ai_only_selected_tickers"]
            assert a["hybrid_selected_tickers"] == b["hybrid_selected_tickers"]
    assert before["signal_views"]["ft_weighted"]["period_log"][0]["ai_only_selected_tickers"] == ["AAA", "BBB", "CCC"]
    assert before["signal_views"]["ai"]["period_log"][0]["ai_only_selected_tickers"] == ["DDD", "CCC", "BBB"]
    assert all(row["n_strategies_tested"] == 8 for row in before["summary"])
    assert before["signal_views"]["ft_agreement"]["ai_only"]["paired_log_excess_ci_95"] is None
    assert result.model_dump(mode="json") == original


def test_artifact_writer_refuses_to_replace_frozen_output(tmp_path):
    path = tmp_path / "protocol.json"
    HELPERS["write_json"](path, {"frozen": True})
    content = path.read_bytes()
    with pytest.raises(FileExistsError):
        HELPERS["write_json"](path, {"frozen": False})
    assert path.read_bytes() == content
