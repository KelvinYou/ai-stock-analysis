"""Evidence preflight: find why an input is thin, repair it, or refuse to run.

A run that proceeds on a missing analyst input does not fail; it quietly turns
that analyst neutral/low. Neutral stays in the convergence denominator, so a
thin input starves the actionability gate and the briefing reads as "no view"
when the truth is "not enough data to have one". The 2026-10-07 backtest ran
with sentiment 0/96, macro a single rate and fundamentals 55/96 — convergence
could not exceed 0.33 against a 0.4 gate, so zero trades was a data property,
not a judgement.

This module is that check, kept deterministic and ahead of every LLM call:

1. ``diagnose`` names each gap with a reason code instead of a bare "missing".
2. ``ensure_evidence`` repairs what a live run can repair deterministically
   (one provider refetch; macro from FRED primary data), then re-diagnoses.
3. If the technical input is unusable, or fewer than
   ``Settings.min_evidence_classes`` of the four evidence classes are usable,
   it raises ``InsufficientEvidenceError`` before a run row or any model call.

Repairs never run for historical/replay captures: filling a past cutoff with
today's data would leak the future. Those only get a diagnosis.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

from stock_analysis.config import Settings
from stock_analysis.data.evidence import (
    financials_are_usable,
    financials_have_evidence,
    macro_snapshot_is_usable,
)
from stock_analysis.models.market_data import MacroSnapshot, TickerData

EVIDENCE_CLASSES = ("technical", "fundamentals", "sentiment", "macro")
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


@dataclass(frozen=True)
class Gap:
    evidence: str
    code: str
    detail: str


@dataclass(frozen=True)
class RepairAttempt:
    evidence: str
    action: str
    ok: bool
    detail: str


@dataclass
class PreflightReport:
    ticker: str
    as_of: date
    live: bool
    gaps: list[Gap] = field(default_factory=list)
    repairs: list[RepairAttempt] = field(default_factory=list)
    usable: dict[str, bool] = field(default_factory=dict)
    quorum_met: bool = False
    min_classes: int = 3

    def render(self) -> str:
        mode = "live" if self.live else "historical: diagnosis only, no repair"
        verdict = "OK" if self.quorum_met else "INSUFFICIENT"
        head = (
            f"{self.ticker} as of {self.as_of} ({mode}): "
            f"{sum(self.usable.values())}/{len(self.usable)} evidence classes usable "
            f"(need technical + {self.min_classes} total) -> {verdict}"
        )
        lines = [head]
        lines += [f"  gap    {g.evidence}/{g.code}: {g.detail}" for g in self.gaps]
        lines += [
            f"  repair {r.evidence}/{r.action}: {'ok' if r.ok else 'FAILED'} - {r.detail}"
            for r in self.repairs
        ]
        return "\n".join(lines)


class InsufficientEvidenceError(RuntimeError):
    """Raised before any run or model call when evidence cannot support analysis."""

    def __init__(self, report: PreflightReport):
        self.report = report
        super().__init__(report.render())


class MacroRepairError(RuntimeError):
    """Macro primary source could not be read; message names the cause."""


def is_live_capture(data: TickerData, as_of: date) -> bool:
    """Same live/historical rule as ``current_metadata_are_usable``."""
    return data.provider_capture == "current" or (
        data.provider_capture is None and as_of >= date.today()
    )


def diagnose(
    data: TickerData,
    as_of: date,
    *,
    min_price_bars: int = 200,
    max_bar_age_days: int = 5,
    cutoff: date | None = None,
) -> list[Gap]:
    """Return every reason an evidence class is unusable, with a stable code.

    ``as_of`` is the day the run happens (bar staleness). ``cutoff`` is the run's
    knowledge cutoff, the capture date downstream gates use; evidence must be
    knowable by it, so it defaults to ``as_of``.
    """
    cutoff = cutoff or as_of
    gaps: list[Gap] = []

    bars = [b for b in data.price_history if b.date <= as_of]
    if len(bars) < min_price_bars:
        gaps.append(
            Gap(
                "technical",
                "price_history_short",
                f"{len(bars)} bars, need {min_price_bars} for SMA-200",
            )
        )
    if bars and (as_of - bars[-1].date).days > max_bar_age_days:
        gaps.append(
            Gap(
                "technical",
                "price_bars_stale",
                f"last bar {bars[-1].date} is {(as_of - bars[-1].date).days}d "
                f"before {as_of} (limit {max_bar_age_days}d)",
            )
        )

    fin = data.financials
    if fin is None:
        gaps.append(Gap("fundamentals", "financials_missing", "provider returned no statements"))
    elif not financials_have_evidence(fin):
        gaps.append(Gap("fundamentals", "financials_empty", "statements carry no measured value"))
    elif not financials_are_usable(fin, cutoff):
        gaps.append(
            Gap(
                "fundamentals",
                "financials_not_knowable",
                f"period end {fin.fiscal_period_end} / available {fin.available_as_of} "
                f"is after {as_of}",
            )
        )

    if not data.news_headlines:
        gaps.append(
            Gap(
                "sentiment",
                "news_empty",
                "no dated, independent headline inside the freshness window",
            )
        )

    snap = data.macro_snapshot
    if snap is None:
        gaps.append(
            Gap(
                "macro",
                "macro_missing",
                "no macro_snapshot; live runs only get one from an evidence replay dir",
            )
        )
    elif not macro_snapshot_is_usable(snap, cutoff):
        gaps.append(
            Gap(
                "macro",
                "macro_unusable",
                f"snapshot {snap.as_of_date} (available {snap.available_as_of}) "
                f"has no value or is after {as_of}",
            )
        )
    return gaps


def _fred_series(client: httpx.Client, series: str) -> list[tuple[date, float]]:
    try:
        response = client.get(FRED_CSV.format(series=series))
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MacroRepairError(f"FRED {series}: {type(exc).__name__}: {exc}") from exc
    rows = list(csv.reader(io.StringIO(response.text)))[1:]
    out = []
    for row in rows:
        try:
            out.append((date.fromisoformat(row[0]), float(row[1])))
        except (ValueError, IndexError):
            continue  # FRED marks missing observations with "."
    if not out:
        raise MacroRepairError(f"FRED {series}: no numeric observations")
    return out


def fetch_fred_macro(as_of: date, *, client: httpx.Client | None = None) -> MacroSnapshot:
    """Build a dated macro snapshot from FRED primary data (no API key).

    Raises ``MacroRepairError`` with the underlying cause (DNS, TLS, HTTP status)
    rather than returning an empty snapshot. TLS verification is never disabled.
    """
    owned = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    try:
        dff = [o for o in _fred_series(client, "DFF") if o[0] <= as_of]
        cpi = {d: v for d, v in _fred_series(client, "CPIAUCSL") if d <= as_of}
    finally:
        if owned:
            client.close()
    if not dff or not cpi:
        raise MacroRepairError("FRED returned no observation on or before the run cutoff")
    rate_date, rate = dff[-1]
    # Use the newest month whose prior-year value exists: BLS skipped some months
    # entirely (October 2025, shutdown), so the newest month alone can have no base.
    pairs = [m for m in sorted(cpi, reverse=True) if date(m.year - 1, m.month, 1) in cpi]
    if not pairs:
        raise MacroRepairError(
            "FRED CPIAUCSL has no month with a prior-year observation for year-over-year"
        )
    month = pairs[0]
    prior = date(month.year - 1, month.month, 1)
    return MacroSnapshot(
        as_of_date=rate_date,
        available_as_of=as_of,
        source="FRED:DFF+CPIAUCSL",
        fed_funds_rate=rate,
        inflation=round((cpi[month] / cpi[prior] - 1) * 100, 2),
        sector_factors=[f"CPI year-over-year is for {month:%Y-%m} (FRED:CPIAUCSL)"],
    )


def ensure_evidence(
    data: TickerData,
    as_of: date,
    settings: Settings,
    *,
    refetch: Callable[[], TickerData] | None = None,
    macro_source: Callable[[date], MacroSnapshot] | None = None,
) -> tuple[TickerData, PreflightReport]:
    """Repair what is repairable, then require a usable quorum or raise."""
    macro_source = macro_source or fetch_fred_macro  # resolved at call time
    live = is_live_capture(data, as_of)
    # Downstream gates judge evidence at the capture date, not the day the run
    # happens; a snapshot stamped later than that is rejected there.
    cutoff = min(as_of, data.fetched_at.date())
    opts = {
        "cutoff": cutoff,
        "min_price_bars": settings.preflight_min_price_bars,
        "max_bar_age_days": settings.preflight_max_bar_age_days,
    }
    report = PreflightReport(
        data.info.symbol, as_of, live, min_classes=settings.min_evidence_classes
    )
    gaps = diagnose(data, as_of, **opts)

    if gaps and live:
        provider_gaps = [g for g in gaps if g.evidence != "macro"]
        if provider_gaps and refetch is not None:
            try:
                fresh = refetch()
                kept = data.macro_snapshot
                data = (
                    fresh
                    if fresh.macro_snapshot is not None
                    else fresh.model_copy(update={"macro_snapshot": kept})
                )
                report.repairs.append(
                    RepairAttempt(
                        provider_gaps[0].evidence,
                        "provider_refetch",
                        True,
                        f"retried once for {sorted({g.evidence for g in provider_gaps})}",
                    )
                )
            except Exception as exc:  # provider failure is a finding, not a crash
                report.repairs.append(
                    RepairAttempt(
                        provider_gaps[0].evidence,
                        "provider_refetch",
                        False,
                        f"{type(exc).__name__}: {exc}",
                    )
                )
        if not macro_snapshot_is_usable(data.macro_snapshot, cutoff):
            try:
                data = data.model_copy(update={"macro_snapshot": macro_source(cutoff)})
                report.repairs.append(
                    RepairAttempt(
                        "macro", "fred_primary", True, "built snapshot from FRED DFF + CPIAUCSL"
                    )
                )
            except MacroRepairError as exc:
                report.repairs.append(RepairAttempt("macro", "fred_primary", False, str(exc)))
        gaps = diagnose(data, as_of, **opts)

    report.gaps = gaps
    blocked = {g.evidence for g in gaps}
    report.usable = {name: name not in blocked for name in EVIDENCE_CLASSES}
    report.quorum_met = report.usable["technical"] and (
        sum(report.usable.values()) >= settings.min_evidence_classes
    )
    if live and not report.quorum_met:
        raise InsufficientEvidenceError(report)
    return data, report


def _filings_advisory(data_dir: Path, ticker: str) -> str | None:
    if not (data_dir / ticker / "filings" / "manifest.json").exists():
        return (
            f"{ticker}: no filing index, the fundamentals analyst cannot search 10-K/10-Q. "
            f"Build it: SEC_USER_AGENT='<name> <email>' stock-filings {ticker}"
        )
    return None


def cli(argv: list[str] | None = None) -> int:
    """``stock-preflight``: gate an in-session run on the evidence already on disk.

    Exit 0 = quorum met, 2 = insufficient (do not run analysts), 1 = no local data.
    ``--fix`` writes a repaired macro_snapshot back into ``fundamentals.json``.
    """
    from stock_analysis.data.store import DataStore

    p = argparse.ArgumentParser(description=cli.__doc__)
    p.add_argument("tickers", nargs="+")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--fix", action="store_true")
    args = p.parse_args(argv)
    settings = Settings.from_env()
    store = DataStore(args.data_dir)
    status = 0
    for raw in args.tickers:
        ticker = raw.upper()
        data = store.load_market_data(ticker)
        if data is None:
            print(f"{ticker}: no local market data; run stock-fetch {ticker} first")
            status = max(status, 1)
            continue
        # Judge the snapshot for a run today: a stale capture must fail, and a
        # statement filed after the last bar is knowable once the capture date passes.
        as_of = date.today()
        data = data.model_copy(update={"provider_capture": data.provider_capture or "current"})
        try:
            repaired, report = ensure_evidence(data, as_of, settings)
        except InsufficientEvidenceError as exc:
            print(exc.report.render())
            status = max(status, 2)
            continue
        print(report.render())
        if args.fix and repaired.macro_snapshot is not data.macro_snapshot:
            path = Path(args.data_dir) / ticker / "fundamentals.json"
            payload = json.loads(path.read_text())
            payload["macro_snapshot"] = json.loads(repaired.macro_snapshot.model_dump_json())
            path.write_text(json.dumps(payload, indent=2))
            print(f"  wrote repaired macro_snapshot to {path}")
        note = _filings_advisory(Path(args.data_dir), ticker)
        if note:
            print(f"  note   {note}")
    return status


if __name__ == "__main__":
    sys.exit(cli())
