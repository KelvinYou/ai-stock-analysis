"""Whether a stored briefing still describes the current price data.

The pipeline's layers refresh independently: `stock-fetch` rewrites
`price_history.csv` and `technicals.json` daily, while the LLM layers
(`analyst_reports` → `debate` → `briefing`) only rerun when the full pipeline
does. Nothing previously compared the two, so a briefing adjudicated on the
2026-09-02 close sat beside technicals from 2026-09-08 and read as current: a
`buy` formed at $592.85, presented against a $617.79 tape and an RSI of 88.6
that no analyst in that run ever saw.

This module is the comparison, kept deterministic and out of the LLM layers so
a briefing cannot vouch for its own currency.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from stock_analysis.models.market_data import TechnicalSnapshot
from stock_analysis.models.synthesis import Briefing

# Beyond this, a briefing is old news even when no newer bar exists to compare
# it against — it matches the swing horizon the briefings are written for.
STALE_AFTER_DAYS = 7


@dataclass(frozen=True)
class Freshness:
    """Whether a briefing may be presented as current, and why not."""

    stale: bool
    reason: str | None = None

    def __bool__(self) -> bool:  # `if freshness:` reads as "is it fresh"
        return not self.stale


_FRESH = Freshness(stale=False)


def _as_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def assess_freshness(
    briefing_date: str | date | None,
    data_as_of: str | date | None,
    latest_bar_date: str | date | None,
    *,
    today: date | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> Freshness:
    """Compare what a briefing analysed against what the price data now shows.

    ``data_as_of`` is the newest bar the analysis actually saw and is preferred
    over ``briefing_date`` (which records when the run happened, not what it
    read). Briefings written before that field existed fall back to the run
    date, which is the same day or later, so the comparison stays conservative.
    """
    reference = _as_date(data_as_of) or _as_date(briefing_date)
    if reference is None:
        return Freshness(stale=True, reason="Briefing has no date; treat as unverified.")

    latest = _as_date(latest_bar_date)
    if latest is not None and latest > reference:
        lag = (latest - reference).days
        return Freshness(
            stale=True,
            reason=(
                f"Briefing analysed price data through {reference}; bars now run "
                f"to {latest} ({lag}d newer). Its signal, conviction and levels "
                "predate the current tape — rerun the pipeline before acting."
            ),
        )

    age = ((today or date.today()) - reference).days
    if age > stale_after_days:
        return Freshness(
            stale=True,
            reason=(
                f"Briefing analysed price data through {reference}, {age} days "
                f"ago (limit {stale_after_days}d). Rerun the pipeline before acting."
            ),
        )

    return _FRESH


def briefing_freshness(
    briefing: Briefing | None,
    technicals: TechnicalSnapshot | None = None,
    latest_bar_date: str | date | None = None,
    *,
    today: date | None = None,
) -> Freshness:
    """``assess_freshness`` for the loaded-model case."""
    if briefing is None:
        return Freshness(stale=False)
    return assess_freshness(
        briefing.date,
        briefing.data_as_of,
        latest_bar_date or (technicals.as_of_date if technicals else None),
        today=today,
    )
