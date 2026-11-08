from datetime import date

import pandas as pd
import pytest

from stock_analysis.allocation_snapshot import build_current_momentum, public_current_momentum


def histories():
    return {
        name: pd.DataFrame({"date": ["2025-10-24", "2026-10-26"], "close": [100, last]})
        for name, last in [("AAA", 150), ("BBB", 120), ("CCC", 110), ("DDD", 90)]
    }


def test_current_ranking_is_a_complete_dated_preview_with_equal_sleeves():
    snapshot = build_current_momentum(histories(), today=date(2026, 10, 27))
    assert snapshot["status"] == "available"
    assert snapshot["scope"] == "indicative_price_only"
    assert snapshot["as_of"] == "2026-10-26"
    assert [r["ticker"] for r in snapshot["ranking"]] == ["AAA", "BBB", "CCC", "DDD"]
    assert [r["target_weight"] for r in snapshot["ranking"]] == [1 / 3, 1 / 3, 1 / 3, 0]
    assert snapshot["ranking"][0]["score"] == pytest.approx(0.5)
    assert snapshot["ranking"][0]["lookback_date"] == "2025-10-24"


@pytest.mark.parametrize(
    "problem", ["mixed", "stale", "future", "duplicate", "nan", "anchor", "current_day"]
)
def test_unusable_inputs_never_emit_a_partial_buy_list(problem):
    data = histories()
    if problem == "mixed":
        data["AAA"].loc[1, "date"] = "2026-10-23"
    elif problem in ("stale", "future", "current_day"):
        for frame in data.values():
            frame.loc[1, "date"] = {
                "stale": "2026-10-20",
                "future": "2026-10-28",
                "current_day": "2026-10-27",
            }[problem]
    elif problem == "duplicate":
        data["AAA"] = pd.concat([data["AAA"], data["AAA"].tail(1)])
    elif problem == "nan":
        data["AAA"].loc[1, "close"] = float("nan")
    else:
        data["AAA"] = data["AAA"].tail(1)
    result = build_current_momentum(data, today=date(2026, 10, 27))
    assert result["status"] == "unavailable"
    assert "ranking" not in result


def test_negative_scores_and_ties_do_not_invent_a_cash_or_ai_filter():
    data = histories()
    for frame in data.values():
        frame.loc[1, "close"] = 80
    result = build_current_momentum(data, today=date(2026, 10, 27))
    assert [r["ticker"] for r in result["ranking"]] == ["AAA", "BBB", "CCC", "DDD"]
    assert sum(r["target_weight"] for r in result["ranking"]) == 1


def test_public_snapshot_requires_full_universe_and_drops_unapproved_fields():
    raw = build_current_momentum(histories(), today=date(2026, 10, 27))
    raw.update(captured_at_utc="2026-10-27T03:00:00+00:00", secret="do-not-export")
    public = public_current_momentum(
        raw, universe=sorted(histories()), source_hash="a" * 64, today=date(2026, 10, 27)
    )
    assert "secret" not in public
    assert public["source_sha256"] == "a" * 64
    raw["ranking"].pop()
    with pytest.raises(ValueError, match="complete"):
        public_current_momentum(
            raw, universe=sorted(histories()), source_hash="a" * 64, today=date(2026, 10, 27)
        )
