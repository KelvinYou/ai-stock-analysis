"""Single owner of "is this OHLCV bar fit to compute on".

Two distinct failure modes killed a real briefing and both are handled here so
no caller re-invents the check:

1. **Non-finite bars.** yfinance occasionally returns a row of NaN OHLC with a
   plausible volume (seen on META 2026-08-28). Written to `price_history.csv`
   it is not a local defect: `close.rolling(200).mean()` returns NaN for the
   *next 200 bars*, so one bad row silently voids SMA-20/50/200, RSI,
   Bollinger and ATR while `ewm()`-based EMA/MACD survive by skipping NaN.
   The surviving pair are exactly the indicators that turn positive first in a
   bounce, so the failure mode is not neutral — it strips the bear's evidence
   and biases the technical agent bullish.

2. **Provisional tail bars.** An intraday snapshot fetched before the close
   lands as a completed daily bar with a fraction of the session's volume
   (META 2026-09-08: 1.9M against a 15.3M 20-day average). It corrupts
   `volume_ratio`, the last candle, and any close-based indicator until the
   real bar replaces it — which incremental fetch never does, because it only
   ever asks for dates *after* the newest stored one.

Both checks are deliberately arithmetic and dependency-free: they run in Layer
1 ingestion, in `DataStore` on the way to and from disk, and again defensively
in `compute_technicals`, so a poisoned CSV already on disk heals without a
refetch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from stock_analysis.models.market_data import PriceBar

# A tail bar carrying less than this share of the recent median session volume
# is treated as an unfinished session rather than a real bar. Half-days (the
# US afternoon after Thanksgiving, Bursa's eve-of-holiday sessions) still clear
# it comfortably at roughly 30-50%.
PROVISIONAL_VOLUME_RATIO = 0.2

# Bars used to establish the volume baseline for the check above.
_VOLUME_BASELINE_BARS = 20

# Below this many prior bars there is no trustworthy baseline, so the tail bar
# is kept rather than guessed about.
_MIN_BASELINE_BARS = 5


@dataclass
class BarAudit:
    """Bars that survived, plus a human-readable reason per rejected bar."""

    bars: list[PriceBar]
    dropped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.dropped


def invalid_bar_reason(bar: PriceBar) -> str | None:
    """Return why ``bar`` is unfit to compute on, or None if it is fine."""
    for name in ("open", "high", "low", "close"):
        value = getattr(bar, name)
        if not math.isfinite(value):
            return f"{bar.date}: non-finite {name} ({value!r})"
        if value <= 0:
            return f"{bar.date}: non-positive {name} ({value!r})"
    if bar.high < bar.low:
        return f"{bar.date}: high {bar.high} below low {bar.low}"
    if bar.volume < 0:
        return f"{bar.date}: negative volume ({bar.volume})"
    return None


def drop_invalid_bars(bars: list[PriceBar]) -> BarAudit:
    """Remove bars whose OHLC cannot be computed on.

    Order-independent: a bad bar costs only itself, never the rolling window
    that follows it.
    """
    kept: list[PriceBar] = []
    dropped: list[str] = []
    for bar in bars:
        reason = invalid_bar_reason(bar)
        if reason is None:
            kept.append(bar)
        else:
            dropped.append(reason)
    return BarAudit(bars=kept, dropped=dropped)


def provisional_tail_reason(
    bars: list[PriceBar],
    *,
    min_volume_ratio: float = PROVISIONAL_VOLUME_RATIO,
) -> str | None:
    """Return why the newest bar looks like an unfinished session, else None.

    Only the final bar is ever suspect — an interior bar with thin volume is a
    real quiet day, not a snapshot artefact.
    """
    if len(bars) <= _MIN_BASELINE_BARS:
        return None

    last = bars[-1]
    baseline_bars = bars[-(_VOLUME_BASELINE_BARS + 1) : -1]
    volumes = sorted(b.volume for b in baseline_bars)
    if len(volumes) < _MIN_BASELINE_BARS:
        return None

    mid = len(volumes) // 2
    median = (
        volumes[mid]
        if len(volumes) % 2
        else (volumes[mid - 1] + volumes[mid]) / 2
    )
    # A ticker whose own recent median is zero is genuinely untraded; there is
    # no baseline to call the tail bar thin against.
    if median <= 0:
        return None

    ratio = last.volume / median
    if ratio >= min_volume_ratio:
        return None
    return (
        f"{last.date}: provisional bar — volume {last.volume:,} is "
        f"{ratio:.1%} of the {len(volumes)}-bar median {median:,.0f} "
        f"(< {min_volume_ratio:.0%}); session likely still open"
    )


def strip_provisional_tail(
    bars: list[PriceBar],
    *,
    min_volume_ratio: float = PROVISIONAL_VOLUME_RATIO,
) -> BarAudit:
    """Drop the newest bar when it reads as an unfinished session.

    Dropping rather than keeping-and-flagging is deliberate: the bar is not
    stored, so the next incremental fetch re-requests that date and writes the
    final version. Keeping it would freeze the snapshot permanently.
    """
    reason = provisional_tail_reason(bars, min_volume_ratio=min_volume_ratio)
    if reason is None:
        return BarAudit(bars=list(bars))
    return BarAudit(bars=list(bars[:-1]), dropped=[reason])


def sanitize_bars(
    bars: list[PriceBar],
    *,
    min_volume_ratio: float = PROVISIONAL_VOLUME_RATIO,
    check_provisional_tail: bool = True,
) -> BarAudit:
    """Full Layer 1 gate: drop uncomputable bars, then any provisional tail.

    ``check_provisional_tail=False`` is for callers holding a partial slice
    (an incremental fetch window) where the newest bar has no local baseline
    to be judged against; the merged series is checked instead.
    """
    invalid = drop_invalid_bars(bars)
    if not check_provisional_tail:
        return invalid
    tail = strip_provisional_tail(invalid.bars, min_volume_ratio=min_volume_ratio)
    return BarAudit(bars=tail.bars, dropped=invalid.dropped + tail.dropped)
