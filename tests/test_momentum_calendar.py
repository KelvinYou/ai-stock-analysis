from datetime import UTC, datetime

from stock_analysis.momentum_calendar import build_session_calendar


def test_exchange_calendar_has_holidays_early_close_and_dst():
    calendar = build_session_calendar(datetime(2026, 11, 6, 2, tzinfo=UTC))
    closes = {s["date"]: s["close_utc"] for s in calendar["sessions"]}
    assert closes["2026-10-30"] == "2026-10-30T20:00:00+00:00"
    assert closes["2026-11-05"] == "2026-11-05T21:00:00+00:00"
    assert "2026-11-26" not in closes  # NYSE Thanksgiving closure.
    assert closes["2026-11-27"] == "2026-11-27T18:00:00+00:00"
    assert "2026-11-07" not in closes
    assert calendar["valid_from_utc"] < "2026-11-06T02:00:00+00:00" < calendar["valid_until_utc"]
