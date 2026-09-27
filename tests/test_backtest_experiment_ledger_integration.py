import hashlib
import json
import sys
from argparse import Namespace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from stock_analysis.backtest import main as backtest_main
from stock_analysis.backtest.runner import BacktestResult, BacktestTrial
from stock_analysis.models.agent_reports import Signal


def test_rescore_reuses_exact_result_and_refuses_to_overwrite_input(tmp_path, monkeypatch):
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "result": BacktestResult(
                    trials=[],
                    settings={"pipeline_mode": "in-session"},
                    started_at=date(2026, 1, 1),
                    finished_at=date(2026, 1, 2),
                ).model_dump(mode="json")
            }
        )
    )
    seen = []
    monkeypatch.setattr(backtest_main, "_score_and_write", lambda result, args: seen.append((result, args)))
    monkeypatch.setattr(
        sys,
        "argv",
        ["backtest", "--mode", "rescore", "--score-report", str(source), "--output", str(tmp_path / "new")],
    )

    backtest_main.cli()

    assert len(seen) == 1
    assert seen[0][0].trials == []
    assert seen[0][1]._rescore_source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()

    monkeypatch.setattr(
        sys,
        "argv",
        ["backtest", "--mode", "rescore", "--score-report", str(source), "--output", str(tmp_path / "source")],
    )
    with pytest.raises(SystemExit):
        backtest_main.cli()

    monkeypatch.setattr(
        sys,
        "argv",
        ["backtest", "--mode", "rescore", "--score-report", str(source), "--record-outcomes"],
    )
    with pytest.raises(SystemExit):
        backtest_main.cli()


def test_rescore_allocator_uses_frozen_histories_or_fails_closed(tmp_path, monkeypatch):
    result = BacktestResult(
        trials=[], settings={}, started_at=date(2026, 1, 1), finished_at=date(2026, 1, 2)
    )
    args = Namespace(mode="rescore", data_dir=tmp_path)
    settings = SimpleNamespace(storage_backend="local")
    monkeypatch.setattr(
        backtest_main,
        "load_price_history",
        lambda *_: (_ for _ in ()).throw(AssertionError("live price read")),
    )
    with pytest.raises(ValueError, match="frozen allocator histories"):
        backtest_main._load_allocator_price_histories(result, args, settings)

    args._rescore_allocator_histories = {
        "TEST": [
            {"date": "2025-01-02", "open": 100.0, "close": 101.0},
        ]
    }
    histories = backtest_main._load_allocator_price_histories(result, args, settings)
    assert histories["TEST"]["close"].tolist() == [101.0]


def test_allocator_snapshot_excludes_bars_after_last_decision():
    result = BacktestResult(
        trials=[
            BacktestTrial(
                ticker="TEST",
                as_of_date=date(2025, 7, 30),
                horizon_days=30,
                entry_price=100.0,
                exit_date=date(2025, 8, 29),
                exit_price=105.0,
                realized_return=0.05,
                overall_signal=Signal.BUY,
                conviction_score=0.5,
                signal_convergence=0.5,
                agent_signals={},
                entry_date=date(2025, 7, 31),
            )
        ],
        settings={},
        started_at=date(2025, 7, 30),
        finished_at=date(2025, 8, 29),
    )
    panel = {
        "TEST": pd.DataFrame(
            [
                {"date": "2025-07-29", "open": 99.0, "close": 100.0},
                {"date": "2025-07-30", "open": 100.0, "close": 101.0},
                {"date": "2025-07-31", "open": 101.0, "close": 102.0},
            ]
        )
    }
    snapshot = backtest_main._freeze_allocator_histories(panel, result)
    assert snapshot == {
        "TEST": [
            {"date": "2025-07-29", "open": 99.0, "close": 100.0},
            {"date": "2025-07-30", "open": 100.0, "close": 101.0},
        ]
    }


def test_api_cli_rejects_duplicate_tickers_before_running(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "backtest", "--mode", "api", "--tickers", "AAPL,aapl",
            "--start", "2025-01-01", "--end", "2025-03-01",
        ],
    )
    monkeypatch.setattr(
        backtest_main,
        "Backtester",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("API trial started")),
    )
    with pytest.raises(SystemExit, match="2"):
        backtest_main.cli()

def test_nonoverlap_subset_uses_only_dates_and_keeps_complete_groups():
    windows = [
        (date(2026, 1, 1), date(2026, 1, 2), date(2026, 2, 2)),
        (date(2026, 1, 31), date(2026, 2, 2), date(2026, 3, 2)),
        (date(2026, 3, 2), date(2026, 3, 3), date(2026, 4, 2)),
    ]
    trials = [
        BacktestTrial(
            ticker=ticker,
            as_of_date=as_of,
            horizon_days=30,
            entry_date=entry,
            entry_price=100.0,
            exit_date=exit_,
            exit_price=100.0 * (1 + realized),
            realized_return=realized,
            overall_signal=Signal.BUY,
            conviction_score=0.5,
            signal_convergence=0.5,
            agent_signals={"technical": "buy"},
        )
        for as_of, entry, exit_ in windows
        for ticker, realized in (("AAA", 0.8), ("BBB", -0.8))
    ]

    selected, dates = backtest_main._nonoverlapping_trial_subset(trials)

    assert dates == [date(2026, 1, 1), date(2026, 3, 2)]
    assert len(selected) == 4
    changed_returns = [trial.model_copy(update={"realized_return": 0.01}) for trial in trials]
    assert backtest_main._nonoverlapping_trial_subset(changed_returns)[1] == dates
    with pytest.raises(ValueError, match="Incomplete trial group"):
        backtest_main._nonoverlapping_trial_subset(trials[:-1])


class _ModelDump:
    def __init__(self, payload):
        self.payload = payload

    def model_dump(self, mode="python"):
        return self.payload


def test_scored_pipeline_runs_append_ledger_even_when_report_prefix_is_reused(
    tmp_path, monkeypatch
):
    result = BacktestResult(
        trials=[
            BacktestTrial(
                ticker="AAPL",
                as_of_date=date(2026, 1, 2),
                horizon_days=30,
                entry_price=100.0,
                exit_date=date(2026, 2, 3),
                exit_price=105.0,
                realized_return=0.05,
                overall_signal=Signal.BUY,
                conviction_score=0.7,
                signal_convergence=0.6,
                agent_signals={"technical": "buy"},
                entry_date=date(2026, 1, 5),
            )
        ],
        settings={
            "market": "US",
            "horizon_days": 30,
            "lookback_days": 365,
            "entry_execution": "next_session_open",
        },
        started_at=date(2026, 1, 2),
        finished_at=date(2026, 2, 4),
    )
    portfolio_payload = {
        "config": {"starting_balance": 10_000.0, "cost_bps_per_side": 10.0},
        "n_strategies_tested": 2,
        "strategies": [
            {
                "strategy": "overall",
                "total_return_pct": 3.0,
                "excess_return_pct": -2.0,
                "beats_benchmark": False,
                "effective_n": 1.0,
                "effective_n_basis": "portfolio_overlap_clustered_v1",
                "deflated_sharpe": 0.2,
            },
            {
                "strategy": "buy_and_hold",
                "total_return_pct": 5.0,
                "excess_return_pct": 0.0,
                "beats_benchmark": None,
            },
        ],
    }
    portfolio = _ModelDump(portfolio_payload)
    portfolio.config = _ModelDump(portfolio_payload["config"])
    portfolio.strategies = portfolio_payload["strategies"]
    monkeypatch.setattr(
        backtest_main.Scorer,
        "score",
        staticmethod(lambda *_args, **_kwargs: _ModelDump({"headline": "test"})),
    )
    monkeypatch.setattr(
        backtest_main.Scorer,
        "to_markdown",
        staticmethod(lambda *_args, **_kwargs: "# Scored test"),
    )
    monkeypatch.setattr(backtest_main.portfolio_mod, "simulate", lambda *_a, **_k: portfolio)
    monkeypatch.setattr(backtest_main.portfolio_mod, "to_markdown", lambda _report: "## Portfolio")
    monkeypatch.setattr(
        backtest_main,
        "_load_allocator_price_histories",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("test no prices")),
    )

    output_prefix = tmp_path / "backtest"
    ledger_path = tmp_path / "experiments.jsonl"
    args = Namespace(
        mode="api",
        cost_bps=10.0,
        starting_balance=10_000.0,
        position_size=0.1,
        allow_short=False,
        cross_sectional_lookback_months=12,
        cross_sectional_top_n=3,
        output=str(output_prefix),
        experiment_ledger=ledger_path,
        record_outcomes=False,
        start="2026-01-01",
        end="2026-02-01",
        interval="monthly",
        horizon=30,
        lookback=365,
        no_resume=False,
        market="US",
        _settings=SimpleNamespace(storage_backend="local"),
    )

    backtest_main._score_and_write(result, args)
    first_prefix = ledger_path.read_bytes()
    backtest_main._score_and_write(result, args)

    rows = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    artifact = json.loads(Path(f"{output_prefix}.json").read_text())
    assert artifact["quality_analysis"]["verdict"] == "research_only"
    assert any(
        finding["code"] == "promotion_gate_failed"
        for finding in artifact["quality_analysis"]["findings"]
    )
    assert "## Automatic Quality Analysis" in Path(f"{output_prefix}.md").read_text()
    assert artifact["signal_ablation"] is None
    assert "sealed-trial allocator is unavailable" in artifact["signal_ablation_error"]
    assert (
        "sealed-trial allocator is unavailable"
        in artifact["experiment"]["diagnostics"]["signal_ablation"]["error"]
    )
    assert "## AI Signal Ablation" in Path(f"{output_prefix}.md").read_text()
    assert len(rows) == 2
    assert ledger_path.read_bytes().startswith(first_prefix)
    assert [row["ledger"]["sequence"] for row in rows] == [1, 2]
    assert rows[1]["ledger"]["unique_candidate_count_after"] == 2
    assert artifact["experiment"]["portfolio_dsr_candidate_count_in_run"] == 2
    assert artifact["experiment"]["cross_run_dsr_adjustment"].startswith("not_applied")
    overall_arm = next(
        arm
        for arm in rows[0]["candidate_arms"]
        if arm["family"] == "portfolio_comparison" and arm["strategy"] == "overall"
    )
    assert overall_arm["metrics"]["effective_n_basis"] == "portfolio_overlap_clustered_v1"
