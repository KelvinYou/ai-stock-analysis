"""Current ranking contracts use synthetic prices, never owner data."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from stock_analysis.current_ranking import build_current_ranking, public_current_ranking

NAMES = ["AAA", "BBB", "CCC", "DDD", "EEE"]


def _histories(days: int = 700) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(3)
    index = pd.bdate_range(end="2026-11-10", periods=days)
    out = {}
    for i, name in enumerate(NAMES):
        close = 100 * np.cumprod(1 + rng.normal(0.0003 * (i + 1), 0.01 + 0.002 * i, days))
        out[name] = pd.DataFrame({"date": index, "close": close})
    return out


def _build(today=date(2026, 11, 11), **kw):
    return build_current_ranking(
        kw.pop("histories", _histories()), universes={"u": NAMES}, today=today, **kw
    )


def test_every_rule_ranks_the_full_universe_with_consistent_weights():
    result = _build()
    assert result["status"] == "available" and result["as_of"] == "2026-11-10"
    for rule in result["experiments"]["u"]["rules"]:
        rows = rule["ranking"]
        assert sorted(r["ticker"] for r in rows) == NAMES
        assert [r["rank"] for r in rows] == list(range(1, len(NAMES) + 1))
        assert abs(sum(r["weight"] for r in rows) + rule["cash_weight"] - 1.0) < 1e-9
        values = [r["value"] for r in rows if r["value"] is not None]
        assert values == sorted(values, reverse=rule["higher_is_better"])


def test_ma_distance_selects_top_three_by_its_metric():
    rules = {r["id"]: r for r in _build()["experiments"]["u"]["rules"]}
    rows = rules["ma_distance"]["ranking"]
    assert [r["ticker"] for r in rows if r["weight"] > 0] == [r["ticker"] for r in rows[:3]]


def test_stale_or_incomplete_evidence_is_rejected_not_filled():
    assert _build(today=date(2026, 11, 20))["status"] == "unavailable"  # last bar too old
    assert _build(today=date(2026, 11, 10))["status"] == "unavailable"  # session not complete
    partial = _histories()
    partial["EEE"] = partial["EEE"].iloc[:-3]
    assert _build(histories=partial)["status"] == "unavailable"  # symbols disagree on the tail
    missing = _histories()
    del missing["EEE"]
    assert _build(histories=missing)["status"] == "unavailable"


def test_public_view_expires_and_rejects_tampered_rankings():
    raw = _build()
    raw["captured_at_utc"] = "2026-11-11T03:00:00+00:00"
    good = public_current_ranking(
        raw, universes={"u": NAMES}, source_hash="a" * 64, today=date(2026, 11, 11)
    )
    assert good["status"] == "available"
    expired = public_current_ranking(
        raw,
        universes={"u": NAMES},
        source_hash="a" * 64,
        today=date(2026, 11, 10) + timedelta(days=9),
    )
    assert expired["status"] == "unavailable"
    raw["experiments"]["u"]["rules"][0]["ranking"][0]["weight"] += 0.3
    with pytest.raises(ValueError):
        public_current_ranking(
            raw, universes={"u": NAMES}, source_hash="a" * 64, today=date(2026, 11, 11)
        )


def test_selection_history_ends_at_the_current_preview_and_ignores_the_future():
    base = _histories()
    result = _build(histories=base)
    for rule in result["experiments"]["u"]["rules"]:
        history = rule["history"]
        assert history[-1]["as_of"] == result["as_of"]
        assert history[-1]["selected"] == sorted(
            r["ticker"] for r in rule["ranking"] if r["weight"] > 0
        )
        assert [h["as_of"] for h in history] == sorted({h["as_of"] for h in history})
    # A price shock after a past month-end must not change that month's selection.
    shocked = {k: v.copy() for k, v in base.items()}
    for frame in shocked.values():
        frame.loc[frame["date"] > pd.Timestamp("2026-08-31"), "close"] *= 2.5
    later = _build(histories=shocked)
    for a, b in zip(
        result["experiments"]["u"]["rules"], later["experiments"]["u"]["rules"], strict=True
    ):
        early = [h for h in a["history"] if h["as_of"] <= "2026-08-31"]
        assert early == [h for h in b["history"] if h["as_of"] <= "2026-08-31"], a["id"]
