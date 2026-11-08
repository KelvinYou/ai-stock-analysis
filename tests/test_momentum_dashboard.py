from datetime import UTC, datetime

import pandas as pd
import pytest

from stock_analysis.momentum_dashboard import build_momentum_dashboard


def test_daily_preview_and_completed_month_targets_are_separate_and_future_safe():
    config = {
        "id": "synthetic",
        "lookback_months": 12,
        "top_n": 3,
        "universe": ["AAA", "BBB", "CCC", "DDD"],
    }
    histories = {
        ticker: pd.DataFrame(
            {
                "date": ["2025-09-30", "2025-10-24", "2026-09-30", "2026-10-26"],
                "close": [100, 100, monthly, latest],
            }
        )
        for ticker, monthly, latest in [
            ("AAA", 150, 110),
            ("BBB", 140, 120),
            ("CCC", 130, 130),
            ("DDD", 120, 150),
        ]
    }
    result = build_momentum_dashboard(histories, config, now=datetime(2026, 10, 27, 3, tzinfo=UTC))
    assert result["ai_required"] is False
    assert result["preview"]["as_of"] == "2026-10-26"
    assert result["monthly"]["as_of"] == "2026-09-30"
    assert [r["ticker"] for r in result["monthly"]["ranking"][:3]] == ["AAA", "BBB", "CCC"]
    assert [r["ticker"] for r in result["preview"]["ranking"][:3]] == ["DDD", "CCC", "BBB"]
    assert result["cycle_month"] == "2026-10"
    histories["DDD"].loc[3, "close"] = 999999
    again = build_momentum_dashboard(histories, config, now=datetime(2026, 10, 27, 3, tzinfo=UTC))
    assert again["monthly"] == result["monthly"]


def test_calendar_rollover_on_weekend_uses_the_last_completed_month():
    config = {
        "id": "synthetic",
        "lookback_months": 12,
        "top_n": 3,
        "universe": ["AAA", "BBB", "CCC"],
    }
    histories = {
        n: pd.DataFrame(
            {
                "date": ["2025-09-30", "2025-10-30", "2026-09-30", "2026-10-30"],
                "close": [100, 100, 110, 120],
            }
        )
        for n in config["universe"]
    }
    october = build_momentum_dashboard(histories, config, now=datetime(2026, 10, 31, 1, tzinfo=UTC))
    november = build_momentum_dashboard(histories, config, now=datetime(2026, 11, 1, 1, tzinfo=UTC))
    assert october["monthly"]["as_of"] == "2026-09-30"
    assert november["monthly"]["as_of"] == "2026-10-30"
    assert november["cycle_month"] == "2026-11"


def test_failed_refresh_preserves_the_previous_published_snapshot(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "refresh_momentum", Path(__file__).parents[1] / "scripts/refresh_momentum_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = {
        "id": "synthetic",
        "lookback_months": 12,
        "top_n": 3,
        "universe": ["AAA", "BBB", "CCC"],
    }
    histories = {
        n: pd.DataFrame({"date": ["2025-10-24", "2026-10-26"], "close": [100, 120]})
        for n in config["universe"]
    }
    output = tmp_path / "momentum.json"
    output.write_text("previous-data")
    output.with_suffix(".sha256").write_text("previous-hash")
    with pytest.raises(ValueError):
        module.publish_snapshot(
            histories, config, output, now=datetime(2026, 10, 27, 1, tzinfo=UTC)
        )
    assert output.read_text() == "previous-data"
    assert output.with_suffix(".sha256").read_text() == "previous-hash"


def test_missing_symbol_is_not_silently_removed_from_the_strategy():
    config = {
        "id": "synthetic",
        "lookback_months": 12,
        "top_n": 3,
        "universe": ["AAA", "BBB", "CCC"],
    }
    with pytest.raises(ValueError, match="complete"):
        build_momentum_dashboard({}, config, now=datetime(2026, 10, 27, 1, tzinfo=UTC))


def test_monthly_anchor_matches_backtest_month_ends_when_calendar_day_differs():
    config = {
        "id": "synthetic",
        "lookback_months": 12,
        "top_n": 3,
        "universe": ["AAA", "BBB", "CCC", "DDD"],
    }
    histories = {
        n: pd.DataFrame(
            {"date": ["2025-10-30", "2025-10-31", "2026-10-30"], "close": [100, anchor, latest]}
        )
        for n, anchor, latest in [
            ("AAA", 100, 150),
            ("BBB", 100, 140),
            ("CCC", 300, 130),
            ("DDD", 40, 120),
        ]
    }
    result = build_momentum_dashboard(histories, config, now=datetime(2026, 11, 1, 1, tzinfo=UTC))
    assert [r["ticker"] for r in result["monthly"]["ranking"][:3]] == ["DDD", "AAA", "BBB"]
    assert result["monthly"]["ranking"][0]["lookback_date"] == "2025-10-31"


def test_price_evidence_preserves_gaps_and_supplements_without_changing_ranks():
    import copy

    config = {"id": "test", "lookback_months": 12, "top_n": 3, "universe": ["AAA", "BBB", "CCC"]}
    histories = {
        n: pd.DataFrame(
            {
                "date": ["2025-09-30", "2025-10-24", "2026-09-30", "2026-10-26"],
                "close": [100, 100, 110, 120],
            }
        )
        for n in config["universe"]
    }
    evidence = {
        "primary_source": {"name": "Primary", "url": "https://example.com/"},
        "supplemental_source": {"name": "Secondary", "url": "https://example.org/"},
        "missing_sessions": [{"date": "2026-10-26", "tickers": ["AAA"]}],
        "supplemented_sessions": [{"date": "2026-10-26", "tickers": ["AAA"]}],
    }
    now = datetime(2026, 10, 27, 3, tzinfo=UTC)
    baseline = build_momentum_dashboard(histories, config, now=now)
    result = build_momentum_dashboard(histories, config, now=now, price_evidence=evidence)
    assert result["price_evidence"] == evidence
    assert result["monthly"] == baseline["monthly"]
    assert result["preview"] == baseline["preview"]
    assert "price_evidence" not in baseline  # Legacy snapshots remain explicitly unknown.
    for mutate in (
        lambda e: e.update(supplemental_source=None),
        lambda e: e["primary_source"].update(url="javascript:alert(1)"),
        lambda e: e["missing_sessions"][0].update(tickers=["OTHER"]),
        lambda e: e["supplemented_sessions"][0].update(date="2026-10-25"),
        lambda e: e["missing_sessions"][0].update(date="2026-10-27"),
        lambda e: e.update(private_balance=123),
    ):
        invalid = copy.deepcopy(evidence)
        mutate(invalid)
        with pytest.raises(ValueError):
            build_momentum_dashboard(histories, config, now=now, price_evidence=invalid)


def test_refresh_records_sanitized_missing_sessions_without_guessing_local_provider(
    tmp_path, monkeypatch
):
    import importlib.util
    import json
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "refresh_momentum_evidence",
        Path(__file__).parents[1] / "scripts/refresh_momentum_dashboard.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Clock(datetime):
        @staticmethod
        def now(tz):
            return datetime(2026, 10, 27, 3, tzinfo=tz)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "momentum.json").write_text(
        json.dumps(
            {"id": "test", "lookback_months": 12, "top_n": 3, "universe": ["AAA", "BBB", "CCC"]}
        )
    )
    prices = tmp_path / "prices"
    prices.mkdir()
    for ticker in ["AAA", "BBB", "CCC"]:
        frame = pd.DataFrame(
            {
                "date": ["2025-09-30", "2025-10-23", "2026-09-30", "2026-10-22", "2026-10-26"],
                **{
                    key: [100, 100, 110, float("nan"), 120]
                    for key in ["open", "high", "low", "close"]
                },
                "volume": [1000] * 5,
            }
        )
        frame.to_csv(prices / f"{ticker}.csv", index=False)
    target = tmp_path / "momentum.json"
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(
        "sys.argv", ["refresh", "--prices-dir", str(prices), "--output", str(target)]
    )
    module.main()
    result = json.loads(target.read_text())
    assert result["preview"]["as_of"] == "2026-10-26"
    assert result["price_evidence"]["primary_source"] == {"name": "Local price files", "url": None}
    assert result["price_evidence"]["missing_sessions"] == [
        {"date": "2026-10-22", "tickers": ["AAA", "BBB", "CCC"]}
    ]
    assert result["price_evidence"]["supplemented_sessions"] == []
