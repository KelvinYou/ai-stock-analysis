"""Layer 1 bar hygiene: the two ingestion defects that voided a real briefing.

Regression anchors for META 2026-08-28 (a NaN OHLC row that nulled every
rolling indicator for the following 200 bars) and META 2026-09-08 (an intraday
snapshot stored as a completed daily bar).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from stock_analysis.data.bars import (
    drop_invalid_bars,
    invalid_bar_reason,
    provisional_tail_reason,
    sanitize_bars,
    strip_provisional_tail,
)
from stock_analysis.data.store import DataStore
from stock_analysis.data.technicals import compute_technicals
from stock_analysis.models.market_data import (
    Market,
    PriceBar,
    TickerData,
    TickerInfo,
)

NAN = float("nan")


def _bar(day: int, close: float = 100.0, volume: int = 1_000_000) -> PriceBar:
    return PriceBar(
        date=date(2026, 1, 1) + timedelta(days=day),
        open=close - 1,
        high=close + 1,
        low=close - 2,
        close=close,
        volume=volume,
    )


def _series(n: int = 260, volume: int = 1_000_000) -> list[PriceBar]:
    """A clean rising series long enough for SMA-200 to be defined."""
    return [_bar(i, close=100.0 + i * 0.5, volume=volume) for i in range(n)]


# --- invalid bars ---------------------------------------------------------


@pytest.mark.parametrize(
    "field_name",
    ["open", "high", "low", "close"],
)
def test_non_finite_ohlc_is_rejected(field_name: str) -> None:
    bar = _bar(0).model_copy(update={field_name: NAN})
    reason = invalid_bar_reason(bar)
    assert reason is not None
    assert "non-finite" in reason
    assert field_name in reason


def test_non_positive_and_inverted_bars_are_rejected() -> None:
    assert invalid_bar_reason(_bar(0).model_copy(update={"close": 0.0})) is not None
    assert invalid_bar_reason(_bar(0).model_copy(update={"low": -5.0})) is not None
    inverted = _bar(0).model_copy(update={"high": 90.0, "low": 110.0})
    assert "below low" in (invalid_bar_reason(inverted) or "")


def test_clean_bar_is_accepted() -> None:
    assert invalid_bar_reason(_bar(0)) is None


def test_one_bad_bar_costs_only_itself() -> None:
    bars = _series(30)
    bars[10] = bars[10].model_copy(
        update={"open": NAN, "high": NAN, "low": NAN, "close": NAN}
    )

    audit = drop_invalid_bars(bars)

    assert len(audit.bars) == 29
    assert len(audit.dropped) == 1
    assert bars[10].date.isoformat() in audit.dropped[0]
    assert all(b.date != bars[10].date for b in audit.bars)


# --- provisional tail ----------------------------------------------------


def test_thin_tail_bar_is_flagged_as_provisional() -> None:
    bars = _series(30, volume=15_000_000)
    bars[-1] = bars[-1].model_copy(update={"volume": 1_900_000})  # ~12.7%

    reason = provisional_tail_reason(bars)

    assert reason is not None
    assert "provisional" in reason
    assert bars[-1].date.isoformat() in reason
    assert strip_provisional_tail(bars).bars == bars[:-1]


def test_normal_and_half_day_tail_volume_is_kept() -> None:
    bars = _series(30, volume=15_000_000)
    assert provisional_tail_reason(bars) is None

    half_day = list(bars)
    half_day[-1] = half_day[-1].model_copy(update={"volume": 6_000_000})  # 40%
    assert provisional_tail_reason(half_day) is None


def test_interior_thin_bar_is_a_quiet_day_not_an_artefact() -> None:
    bars = _series(30, volume=15_000_000)
    bars[-5] = bars[-5].model_copy(update={"volume": 100})

    assert provisional_tail_reason(bars) is None
    assert strip_provisional_tail(bars).bars == bars


def test_untraded_ticker_has_no_volume_baseline() -> None:
    """A ticker whose own median volume is zero cannot have a "thin" tail."""
    bars = _series(30, volume=0)
    assert provisional_tail_reason(bars) is None


def test_short_history_is_left_alone() -> None:
    bars = _series(4, volume=15_000_000)
    bars[-1] = bars[-1].model_copy(update={"volume": 1})
    assert provisional_tail_reason(bars) is None


def test_sanitize_can_skip_the_tail_check_for_partial_slices() -> None:
    bars = _series(30, volume=15_000_000)
    bars[-1] = bars[-1].model_copy(update={"volume": 1_000})

    assert len(sanitize_bars(bars).bars) == 29
    assert len(sanitize_bars(bars, check_provisional_tail=False).bars) == 30


# --- the indicator blast radius the checks exist to prevent ---------------


def test_nan_bar_no_longer_voids_two_hundred_bars_of_indicators() -> None:
    bars = _series(260)
    poisoned = list(bars)
    poisoned[-30] = poisoned[-30].model_copy(
        update={"open": NAN, "high": NAN, "low": NAN, "close": NAN}
    )

    snapshot = compute_technicals("TEST", poisoned)

    # This is the exact set that came back null on the real 2026-09-03 run.
    for indicator in ("sma_20", "sma_50", "sma_200", "rsi_14", "bb_upper", "atr_14"):
        assert getattr(snapshot, indicator) is not None, indicator
    assert snapshot.above_sma_200 is not None
    assert snapshot.as_of_date == bars[-1].date


def test_technicals_drop_the_nan_bar_from_the_chart_series() -> None:
    bars = _series(40)
    bad_date = bars[-10].date
    bars[-10] = bars[-10].model_copy(
        update={"open": NAN, "high": NAN, "low": NAN, "close": NAN}
    )

    snapshot = compute_technicals("TEST", bars)

    assert all(point.date != bad_date for point in snapshot.series)


def test_technicals_reject_a_series_with_no_usable_bars() -> None:
    bars = [
        _bar(0).model_copy(update={"open": NAN, "high": NAN, "low": NAN, "close": NAN})
    ]
    with pytest.raises(ValueError, match="no usable price bars"):
        compute_technicals("TEST", bars)


# --- persistence boundary ------------------------------------------------


def _ticker_data(bars: list[PriceBar]) -> TickerData:
    from datetime import datetime

    return TickerData(
        info=TickerInfo(symbol="TEST", name="Test", market=Market.US, currency="USD"),
        price_history=bars,
        fetched_at=datetime(2026, 9, 10, 12, 0, 0),
    )


def test_store_refuses_to_persist_a_nan_bar(tmp_path) -> None:
    store = DataStore(str(tmp_path))
    bars = _series(30)
    bars[5] = bars[5].model_copy(
        update={"open": NAN, "high": NAN, "low": NAN, "close": NAN}
    )

    merged = store.merge_market_data("TEST", _ticker_data(bars))

    assert len(merged) == 29
    csv_text = (tmp_path / "TEST" / "price_history.csv").read_text()
    assert "nan" not in csv_text.lower()


def test_store_heals_a_nan_bar_already_on_disk(tmp_path) -> None:
    """The poisoned CSV in the repo must not need a refetch to recover."""
    d = tmp_path / "TEST"
    d.mkdir()
    (d / "price_history.csv").write_text(
        "date,open,high,low,close,volume\n"
        "2026-08-27,576.48,588.39,567.62,571.1,15221400\n"
        "2026-08-28,nan,nan,nan,nan,15573685\n"
        "2026-08-31,576.77,578.675,569.1386,571.7,5180931\n"
    )
    store = DataStore(str(tmp_path))

    merged = store.merge_market_data("TEST", _ticker_data([]))

    assert [b.date.isoformat() for b in merged] == ["2026-08-27", "2026-08-31"]
    assert "nan" not in (d / "price_history.csv").read_text().lower()


def test_store_drops_a_provisional_tail_so_the_next_fetch_can_replace_it(
    tmp_path,
) -> None:
    store = DataStore(str(tmp_path))
    bars = _series(30, volume=15_000_000)
    bars[-1] = bars[-1].model_copy(update={"volume": 1_936_755})

    merged = store.merge_market_data("TEST", _ticker_data(bars))

    assert len(merged) == 29
    assert store.last_price_bar_date("TEST") == bars[-2].date
