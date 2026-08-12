"""Layer 6 — outcome memory: what previous calls actually earned.

Every run before this was a cold start. The pipeline already produced the raw
material for a track record (`BacktestTrial.realized_return`, the scorer's hit
rate) but nothing fed it back, so the same mistake on the same ticker could be
made indefinitely without the system ever noticing.

This module closes that loop deterministically:

1. `OutcomeRecord` — one resolved call: what was predicted, what happened.
2. `OutcomeStore` — append-only JSONL per ticker, deduplicated by
   (as_of_date, horizon).
3. `CalibrationSummary` — computed, never LLM-written: hit rate, mean realized
   return, and whether high-conviction calls actually did better than
   low-conviction ones.
4. `build_memory_context()` — the prompt fragment injected into synthesis.

The leakage guard is the critical part. A backtest trial dated 2024-03-01 must
never see an outcome that resolved in 2024-06-01, or the "track record" silently
becomes future knowledge and every backtest metric turns meaningless. So reads
are filtered by `visible_on`, which admits a record only when its *exit* date
is strictly before the analysis date — not its entry date, since a position
opened in the past but closed in the future is still future information.

Calibration is reported, never applied. Nothing here rescales conviction: a
15-trial sample is a hint to a human reader, not a coefficient, and quietly
multiplying signals by a small-sample hit rate would be a much subtler error
than the cold start it replaced.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from stock_analysis.models.agent_reports import Signal

logger = logging.getLogger(__name__)

OUTCOMES_FILENAME = "outcomes.jsonl"
CALIBRATION_FILENAME = "calibration.json"

# Below this, a hit rate is noise. Reported with the count attached rather than
# suppressed, but never described as a track record.
MIN_TRIALS_FOR_SIGNAL = 8

_DIRECTION: dict[Signal, int] = {
    Signal.STRONG_BUY: 1,
    Signal.BUY: 1,
    Signal.NEUTRAL: 0,
    Signal.SELL: -1,
    Signal.STRONG_SELL: -1,
}


class OutcomeRecord(BaseModel):
    """One resolved prediction. `realized_return` is a fraction, not percent."""

    ticker: str
    as_of_date: date
    horizon_days: int
    signal: Signal
    conviction_score: float
    signal_convergence: float
    entry_price: float | None = None
    exit_date: date | None = None
    exit_price: float | None = None
    realized_return: float | None = None
    source: str = "backtest"
    note: str | None = None

    @property
    def resolved(self) -> bool:
        return self.realized_return is not None and self.exit_date is not None

    @property
    def direction(self) -> int:
        return _DIRECTION[self.signal]

    @property
    def correct(self) -> bool | None:
        """Did the direction pay? None for neutral calls and unresolved trials.

        A neutral call has no direction to be right about, so scoring it as a
        hit or a miss would be inventing an opinion the pipeline declined to
        have. It is excluded from hit rate and counted separately.
        """
        if self.realized_return is None or self.direction == 0:
            return None
        return self.direction * self.realized_return > 0

    def visible_on(self, as_of: date | None) -> bool:
        """Whether this record is knowable when analyzing `as_of`.

        Gated on exit date: a trade entered before `as_of` but closed after it
        has an outcome that had not happened yet.
        """
        if as_of is None:
            return True
        if self.exit_date is None:
            return False
        return self.exit_date < as_of


class SignalBucket(BaseModel):
    signal: Signal
    trials: int
    hit_rate: float | None = None
    mean_return: float | None = None


class CalibrationSummary(BaseModel):
    """Deterministic scoring of a ticker's resolved history."""

    ticker: str
    trials: int = 0
    directional_trials: int = 0
    neutral_trials: int = 0
    hit_rate: float | None = None
    mean_return: float | None = None
    mean_return_when_right: float | None = None
    mean_return_when_wrong: float | None = None
    high_conviction_hit_rate: float | None = None
    low_conviction_hit_rate: float | None = None
    conviction_separates: bool | None = None
    buckets: list[SignalBucket] = Field(default_factory=list)
    first_as_of: date | None = None
    last_exit: date | None = None

    @property
    def sufficient_sample(self) -> bool:
        return self.directional_trials >= MIN_TRIALS_FOR_SIGNAL


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def compute_calibration(
    ticker: str,
    records: list[OutcomeRecord],
    high_conviction_threshold: float = 0.5,
) -> CalibrationSummary:
    """Score resolved records. Unresolved records are ignored, not counted as misses."""
    resolved = [r for r in records if r.resolved]
    if not resolved:
        return CalibrationSummary(ticker=ticker.upper())

    directional = [r for r in resolved if r.direction != 0]
    neutral = [r for r in resolved if r.direction == 0]
    hits = [r for r in directional if r.correct]
    misses = [r for r in directional if r.correct is False]

    buckets: list[SignalBucket] = []
    for signal in Signal:
        in_bucket = [r for r in resolved if r.signal is signal]
        if not in_bucket:
            continue
        bucket_directional = [r for r in in_bucket if r.direction != 0]
        bucket_hits = [r for r in bucket_directional if r.correct]
        buckets.append(
            SignalBucket(
                signal=signal,
                trials=len(in_bucket),
                hit_rate=(
                    round(len(bucket_hits) / len(bucket_directional), 4)
                    if bucket_directional
                    else None
                ),
                mean_return=_mean(
                    [r.realized_return for r in in_bucket if r.realized_return is not None]
                ),
            )
        )

    high = [r for r in directional if abs(r.conviction_score) >= high_conviction_threshold]
    low = [r for r in directional if abs(r.conviction_score) < high_conviction_threshold]
    high_rate = (
        round(len([r for r in high if r.correct]) / len(high), 4) if high else None
    )
    low_rate = round(len([r for r in low if r.correct]) / len(low), 4) if low else None

    separates: bool | None = None
    if high_rate is not None and low_rate is not None and len(high) >= 3 and len(low) >= 3:
        separates = high_rate > low_rate

    exit_dates = [r.exit_date for r in resolved if r.exit_date is not None]

    return CalibrationSummary(
        ticker=ticker.upper(),
        trials=len(resolved),
        directional_trials=len(directional),
        neutral_trials=len(neutral),
        hit_rate=round(len(hits) / len(directional), 4) if directional else None,
        mean_return=_mean(
            [r.realized_return for r in resolved if r.realized_return is not None]
        ),
        mean_return_when_right=_mean(
            [r.realized_return for r in hits if r.realized_return is not None]
        ),
        mean_return_when_wrong=_mean(
            [r.realized_return for r in misses if r.realized_return is not None]
        ),
        high_conviction_hit_rate=high_rate,
        low_conviction_hit_rate=low_rate,
        conviction_separates=separates,
        buckets=buckets,
        first_as_of=min(r.as_of_date for r in resolved),
        last_exit=max(exit_dates) if exit_dates else None,
    )


class OutcomeStore:
    """Append-only per-ticker outcome log under `data/<TICKER>/outcomes.jsonl`."""

    def __init__(self, base_dir: str | Path = "data"):
        self.base = Path(base_dir)

    def _path(self, ticker: str) -> Path:
        return self.base / ticker.upper() / OUTCOMES_FILENAME

    def load(self, ticker: str, before: date | None = None) -> list[OutcomeRecord]:
        """Load records for `ticker`, filtered to what was knowable before `before`."""
        path = self._path(ticker)
        if not path.is_file():
            return []
        records: list[OutcomeRecord] = []
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(OutcomeRecord.model_validate_json(line))
            except ValueError as exc:
                logger.warning("Skipping malformed outcome at %s:%d — %s", path, line_no, exc)
        records = [r for r in records if r.visible_on(before)]
        return sorted(records, key=lambda r: (r.as_of_date, r.horizon_days))

    def append(self, records: list[OutcomeRecord]) -> int:
        """Append records, skipping ones already logged. Returns the number written."""
        by_ticker: dict[str, list[OutcomeRecord]] = {}
        for record in records:
            by_ticker.setdefault(record.ticker.upper(), []).append(record)

        written = 0
        for ticker, incoming in by_ticker.items():
            path = self._path(ticker)
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = {
                (r.as_of_date, r.horizon_days, r.source) for r in self.load(ticker)
            }
            fresh = [
                r
                for r in incoming
                if (r.as_of_date, r.horizon_days, r.source) not in existing
            ]
            if not fresh:
                continue
            with path.open("a", encoding="utf-8") as handle:
                for record in fresh:
                    handle.write(record.model_dump_json() + "\n")
            written += len(fresh)
        return written

    def calibration(self, ticker: str, before: date | None = None) -> CalibrationSummary:
        return compute_calibration(ticker, self.load(ticker, before=before))

    def save_calibration(self, ticker: str) -> Path | None:
        """Persist the full-history calibration for dashboards and review.

        Written without a `before` filter on purpose — this file is for humans
        looking back, never an input to a dated analysis.
        """
        summary = self.calibration(ticker)
        if summary.trials == 0:
            return None
        path = self.base / ticker.upper() / CALIBRATION_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        return path


def build_memory_context(
    records: list[OutcomeRecord],
    calibration: CalibrationSummary,
    max_records: int = 6,
) -> str | None:
    """Render prior outcomes as a prompt fragment, or None when there is nothing.

    Returns None rather than a "no history" paragraph: telling the model it has
    no track record invites it to comment on the absence, which is noise.
    """
    if not records or calibration.trials == 0:
        return None

    lines = [
        "## Prior outcomes for this ticker (this system's own track record)",
        "",
        (f"Resolved calls: {calibration.trials} "
        f"({calibration.directional_trials} directional, "
        f"{calibration.neutral_trials} neutral)."),
    ]

    if calibration.hit_rate is not None:
        confidence_note = (
            "" if calibration.sufficient_sample else " — too few trials to be a track record"
        )
        lines.append(
            f"Directional hit rate: {calibration.hit_rate:.0%}{confidence_note}."
        )
    if calibration.mean_return is not None:
        lines.append(f"Mean realized return over the horizon: {calibration.mean_return:+.2%}.")
    if calibration.conviction_separates is False:
        lines.append(
            "High-conviction calls did NOT beat low-conviction calls here "
            f"({calibration.high_conviction_hit_rate:.0%} vs "
            f"{calibration.low_conviction_hit_rate:.0%}) — past conviction on this "
            "ticker carried no information."
        )
    elif calibration.conviction_separates is True:
        lines.append(
            "High-conviction calls beat low-conviction calls "
            f"({calibration.high_conviction_hit_rate:.0%} vs "
            f"{calibration.low_conviction_hit_rate:.0%})."
        )

    lines.extend(["", "Most recent resolved calls:"])
    for record in sorted(records, key=lambda r: r.as_of_date, reverse=True)[:max_records]:
        verdict = {True: "correct", False: "wrong", None: "n/a (neutral)"}[record.correct]
        realized = (
            f"{record.realized_return:+.2%}" if record.realized_return is not None else "n/a"
        )
        lines.append(
            f"- {record.as_of_date}: called **{record.signal.value}** "
            f"(conviction {record.conviction_score:+.2f}, "
            f"convergence {record.signal_convergence:.2f}) → "
            f"{realized} over {record.horizon_days}d — {verdict}"
        )

    lines.extend(
        [
            "",
            ("How to use this: it is evidence about this system's past accuracy on "
            "this ticker, not evidence about the stock's future. Do not flip a view "
            "the current data supports merely because past calls missed, and do not "
            "extrapolate a small sample. If prior calls failed for a reason that is "
            "still present in today's data, say so explicitly in your uncertainties."),
        ]
    )
    return "\n".join(lines)


def records_from_backtest(result, source: str = "backtest") -> list[OutcomeRecord]:
    """Convert a `BacktestResult` into outcome records.

    Kept out of `backtest/` so the memory layer owns its own schema, and typed
    loosely to avoid a circular import between the two packages.
    """
    records: list[OutcomeRecord] = []
    horizon_default = int(result.settings.get("horizon_days") or 0)
    for trial in result.trials:
        if trial.realized_return is None or trial.error:
            continue
        records.append(
            OutcomeRecord(
                ticker=trial.ticker,
                as_of_date=trial.as_of_date,
                horizon_days=trial.horizon_days or horizon_default,
                signal=trial.overall_signal,
                conviction_score=trial.conviction_score,
                signal_convergence=trial.signal_convergence,
                entry_price=trial.entry_price,
                exit_date=trial.exit_date,
                exit_price=trial.exit_price,
                realized_return=trial.realized_return,
                source=source,
            )
        )
    return records
