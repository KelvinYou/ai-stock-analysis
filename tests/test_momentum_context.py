"""Independent arithmetic and time-boundary checks for display-only references."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from stock_analysis.momentum_dashboard import build_momentum_dashboard


def panel():
    dates = pd.bdate_range("2025-07-01", "2026-11-05")
    histories = {}
    for ticker, base, end in [
        ("AAA", 100, 110),
        ("BBB", 200, 210),
        ("CCC", 100, 102),
        ("DDD", 100, 101),
    ]:
        close = [base] * len(dates)
        close[-1] = end
        histories[ticker] = pd.DataFrame(
            {"date": dates, "close": close, "open": [base] * len(dates)}
        )
    ref = pd.DataFrame(
        {"date": dates, "close": [100] * (len(dates) - 1) + [104], "open": [100] * len(dates)}
    )
    config = {"id": "test", "lookback_months": 12, "top_n": 3, "universe": list(histories)}
    return histories, ref, config


def test_context_has_matched_references_gap_anchors_and_cost_scenario():
    histories, ref, config = panel()
    result = build_momentum_dashboard(
        histories, config, now=datetime(2026, 11, 6, 2, tzinfo=UTC), reference=ref
    )
    c = result["context"]
    assert c["decision_month_end"] == "2026-11-30"
    assert c["periods"]["m12"] == {"start": "2025-11-05", "end": "2026-11-05"}
    aaa, _bbb, ccc, ddd = c["stocks"]
    assert aaa["close"] == 110 and aaa["lookback_close"] == 100
    assert aaa["returns"]["d1"] == pytest.approx(0.10)
    assert ddd["gap_pp"] == pytest.approx(-1)
    assert ccc["gap_pp"] == 0
    assert c["previous_rank_date"] == "2026-11-04"
    assert c["market"]["returns"]["m12"] == pytest.approx(0.04)
    assert c["market"]["equal_weight_returns"]["m12"] == pytest.approx(0.045)
    assert c["market"]["curve"][0]["market"] == 100
    assert c["market"]["curve"][-1]["equal_weight"] == pytest.approx(104.5)
    assert c["cycle"]["start"] == "2026-11-02"
    basket = c["cycle"]["rows"][0]
    assert basket["gross"] == pytest.approx(0.17 / 3)
    assert basket["net_scenario"] == pytest.approx((1 + 0.17 / 3) * 0.998**2 - 1)
    assert [x["as_of"] for x in c["ranking_history"]] == ["2026-08-31", "2026-09-30", "2026-10-30"]
    assert c["transition"]["entries"] == []


def test_bad_reference_does_not_change_or_suppress_the_basket():
    histories, ref, config = panel()
    now = datetime(2026, 11, 6, 2, tzinfo=UTC)
    baseline = build_momentum_dashboard(histories, config, now=now)
    for broken in [
        ref.iloc[:-1],
        ref.assign(close=float("nan")),
        ref[ref.date != pd.Timestamp("2025-11-05")],
    ]:
        result = build_momentum_dashboard(histories, config, now=now, reference=broken)
        assert result["monthly"] == baseline["monthly"]
        assert result["preview"] == baseline["preview"]
        assert result["context"]["market"]["status"] == "unavailable"
        assert result["context"]["cycle"]["status"] == "unavailable"


def test_no_adjusted_open_is_not_a_fabricated_executable_return():
    histories, ref, config = panel()
    histories["AAA"] = histories["AAA"].drop(columns="open")
    c = build_momentum_dashboard(
        histories, config, now=datetime(2026, 11, 6, 2, tzinfo=UTC), reference=ref
    )["context"]
    assert c["market"]["status"] == "available"
    assert c["cycle"]["status"] == "unavailable"


def test_month_rollover_uses_current_cycle_and_previous_month_under_same_universe():
    histories, ref, config = panel()
    histories = {t: f[f.date <= "2026-10-30"] for t, f in histories.items()}
    result = build_momentum_dashboard(
        histories, config, now=datetime(2026, 11, 1, 2, tzinfo=UTC), reference=ref
    )
    c = result["context"]
    assert c["as_of"] == "2026-10-30"
    assert c["decision_month_end"] == "2026-11-30"
    assert c["transition"]["from"] == "2026-09-30"
    assert c["transition"]["to"] == "2026-10-30"
    assert c["cycle"]["status"] == "unavailable"


def test_recent_drawdown_is_not_confused_with_a_positive_long_term_rank():
    histories, ref, config = panel()
    histories["AAA"].loc[histories["AAA"].index[-1], "close"] = 90
    c = build_momentum_dashboard(
        histories, config, now=datetime(2026, 11, 6, 2, tzinfo=UTC), reference=ref
    )["context"]
    aaa = next(row for row in c["stocks"] if row["ticker"] == "AAA")
    assert aaa["drawdown_63"] == pytest.approx(-0.1)
    assert aaa["return_since_monthly_close"] == pytest.approx(-0.1)
    assert aaa["rank_change_previous"] == -3


def test_reference_future_rows_cannot_change_past_context_and_missing_curve_is_explicit():
    histories, ref, config = panel()
    now = datetime(2026, 11, 6, 2, tzinfo=UTC)
    baseline = build_momentum_dashboard(histories, config, now=now, reference=ref)["context"]
    future = pd.concat(
        [
            ref,
            pd.DataFrame({"date": [pd.Timestamp("2026-11-09")], "close": [99999], "open": [99999]}),
        ]
    )
    assert (
        build_momentum_dashboard(histories, config, now=now, reference=future)["context"]
        == baseline
    )
    missing = ref[ref.date != pd.Timestamp("2026-09-01")]
    market = build_momentum_dashboard(histories, config, now=now, reference=missing)["context"][
        "market"
    ]
    assert market["status"] == "available"
    assert market["returns"] == baseline["market"]["returns"]
    assert market["curve"] == []


def test_sparse_history_keeps_missing_horizons_and_drawdown_null():
    histories = {
        t: pd.DataFrame(
            {
                "date": ["2025-09-30", "2025-10-23", "2026-09-30", "2026-10-23"],
                "close": [100, 100, 110, 120],
            }
        )
        for t in ["AAA", "BBB", "CCC"]
    }
    c = build_momentum_dashboard(
        histories,
        {"id": "test", "universe": list(histories), "top_n": 3, "lookback_months": 12},
        now=datetime(2026, 10, 27, tzinfo=UTC),
    )["context"]
    assert c["stocks"][0]["drawdown_63"] is None
    assert c["stocks"][0]["returns"]["m1"] is None
    assert c["stocks"][0]["returns"]["m3"] is None
    assert c["market"]["status"] == "unavailable"


def test_supplemental_reference_must_be_present_and_before_capture():
    histories, ref, config = panel()
    evidence = {
        "primary_source": {"name": "Primary", "url": "https://example.com/"},
        "supplemental_source": {"name": "Secondary", "url": "https://example.org/"},
        "missing_sessions": [{"date": "2026-11-05", "tickers": ["SPY"]}],
        "supplemented_sessions": [{"date": "2026-11-05", "tickers": ["SPY"]}],
    }
    now = datetime(2026, 11, 6, 2, tzinfo=UTC)
    with pytest.raises(ValueError, match="sanitization"):
        build_momentum_dashboard(
            histories, config, now=now, reference=ref.iloc[:-1], reference_evidence=evidence
        )
    for key in ["missing_sessions", "supplemented_sessions"]:
        evidence[key][0]["date"] = "2026-11-06"
    with pytest.raises(ValueError, match="prior sessions"):
        build_momentum_dashboard(
            histories, config, now=now, reference=ref, reference_evidence=evidence
        )


def test_extra_etfs_are_references_only_with_matched_anchors_and_fixed_long_hold():
    histories, ref, config = panel()
    config["comparison_references"] = [
        {"ticker": "VOO", "label": "VOO"},
        {"ticker": "VT", "label": "VT"},
    ]
    vt = ref.copy()
    vt.loc[vt.index[-1], "close"] = 102
    result = build_momentum_dashboard(
        histories,
        config,
        now=datetime(2026, 11, 6, 2, tzinfo=UTC),
        reference=ref,
        comparisons={"VOO": ref, "VT": vt},
    )
    assert result["strategy"]["universe"] == list(histories)
    assert len(result["preview"]["ranking"]) == 4
    voo, world = result["context"]["comparisons"]
    assert voo["returns"]["m12"] == pytest.approx(0.04)
    assert world["returns"]["m12"] == pytest.approx(0.02)
    assert voo["curve"][0]["value"] == 100
    assert world["curve"][-1]["value"] == pytest.approx(102)
    assert world["cycle"]["gross"] == pytest.approx(0.02)
    assert result["context"]["market"]["equal_weight_returns"]["m12"] == pytest.approx(0.045)
    assert result["data_sessions"]["references"] == [
        {"ticker": "SPY", "date": "2026-11-05", "complete": True},
        {"ticker": "VOO", "date": "2026-11-05", "complete": True},
        {"ticker": "VT", "date": "2026-11-05", "complete": True},
    ]


def test_one_missing_etf_does_not_remove_other_comparisons_or_select_it():
    histories, ref, config = panel()
    config["comparison_references"] = [
        {"ticker": "VOO", "label": "VOO"},
        {"ticker": "VT", "label": "VT"},
    ]
    now = datetime(2026, 11, 6, 2, tzinfo=UTC)
    result = build_momentum_dashboard(
        histories, config, now=now, reference=ref, comparisons={"VOO": ref, "VT": ref.iloc[:-1]}
    )
    assert result["context"]["comparisons"][0]["status"] == "available"
    assert result["context"]["comparisons"][1]["status"] == "unavailable"
    assert result["data_sessions"]["references"][-1] == {
        "ticker": "VT",
        "date": "2026-11-04",
        "complete": False,
    }
    baseline = build_momentum_dashboard(histories, config, now=now)
    assert result["preview"] == baseline["preview"]
    assert result["monthly"] == baseline["monthly"]


def test_recapturing_old_prices_cannot_replace_a_published_snapshot(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "refresh_latest_guard", Path(__file__).parents[1] / "scripts/refresh_momentum_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    histories, _, config = panel()
    histories = {t: f.iloc[:-1] for t, f in histories.items()}  # November 4, one session missing.
    target = tmp_path / "momentum.json"
    target.write_text("previous verified snapshot")
    target.with_suffix(".sha256").write_text("previous hash")
    with pytest.raises(ValueError, match="latest completed exchange session"):
        module.publish_snapshot(histories, config, target, now=datetime(2026, 11, 6, 2, tzinfo=UTC))
    assert target.read_text() == "previous verified snapshot"
    assert target.with_suffix(".sha256").read_text() == "previous hash"
