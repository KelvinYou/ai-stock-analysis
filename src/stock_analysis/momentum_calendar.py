"""Public XNYS close schedule projected into snapshots for runtime freshness checks."""

from datetime import UTC, datetime, timedelta
from importlib.metadata import version

import exchange_calendars as xcals


def build_session_calendar(now: datetime) -> dict:
    if now.tzinfo is None:
        raise ValueError("An explicit calendar capture timezone is required")
    now = now.astimezone(UTC)
    start, end = now.date() - timedelta(days=10), now.date() + timedelta(days=70)
    calendar = xcals.get_calendar("XNYS", start=str(start), end=str(end))
    schedule = calendar.schedule.loc[str(start) : str(end)]
    return {
        "exchange": "XNYS",
        "library": f"exchange_calendars {version('exchange-calendars')}",
        "source_url": "https://www.nyse.com/trade/hours-calendars",
        "valid_from_utc": f"{start}T00:00:00+00:00",
        "valid_until_utc": f"{end + timedelta(days=1)}T00:00:00+00:00",
        "sessions": [
            {"date": str(session.date()), "close_utc": close.isoformat()}
            for session, close in schedule["close"].items()
        ],
    }
