#!/usr/bin/env python3
"""Sweep every ticker's stored data for the three defects that faked a signal.

The META incident was found by hand, one ticker at a time. All three defects
are silent by construction, so the only way to know the blast radius is to
check every ticker:

1. **Unusable bars** — a non-finite OHLC row in `price_history.csv`. Voids
   SMA-20/50/200, RSI, Bollinger and ATR for up to 200 following bars while
   EMA/MACD survive, leaving a rump of indicators that reads bullish in a
   bounce rather than reading as broken.
2. **Provisional tail bars** — an intraday snapshot stored as a completed
   daily bar, recognisable by a fraction of the session's usual volume.
3. **Stale briefings** — a briefing whose analysis read older bars than the
   `technicals.json` sitting beside it, so its signal describes a tape that
   has already moved.

Usage:
    python scripts/audit_data_health.py                 # report only
    python scripts/audit_data_health.py --fix           # repair 1 & 2 in place
    python scripts/audit_data_health.py --data-dir DIR  # non-default location

`--fix` rewrites `price_history.csv` without the rejected rows and recomputes
`technicals.json`. It deliberately cannot fix a stale briefing: that needs the
LLM pipeline rerun, and the script prints the command instead of guessing.

Exit codes: 0 clean (or everything fixed), 1 findings remain.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from stock_analysis.data.bars import (  # noqa: E402
    drop_invalid_bars,
    provisional_tail_reason,
)
from stock_analysis.data.technicals import compute_technicals  # noqa: E402
from stock_analysis.models.market_data import PriceBar  # noqa: E402
from stock_analysis.synthesis.freshness import assess_freshness  # noqa: E402


def _read_bars(csv_path: Path) -> list[PriceBar]:
    """Read the CSV leniently — a malformed row is a finding, not a crash."""
    bars: list[PriceBar] = []
    with csv_path.open() as f:
        for row in csv.DictReader(f):
            try:
                bars.append(
                    PriceBar(
                        date=date.fromisoformat(row["date"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return bars


def _write_bars(csv_path: Path, bars: list[PriceBar]) -> None:
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "open", "high", "low", "close", "volume"])
        for bar in bars:
            writer.writerow(
                [bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume]
            )


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def scan_ticker(ticker_dir: Path) -> list[str]:
    """Return this ticker's findings. Pure — reads, never writes."""
    findings: list[str] = []
    symbol = ticker_dir.name
    csv_path = ticker_dir / "price_history.csv"

    bars: list[PriceBar] = []
    if csv_path.exists():
        bars = _read_bars(csv_path)
        audit = drop_invalid_bars(bars)
        for reason in audit.dropped:
            findings.append(f"{symbol}: unusable bar — {reason}")
        tail = provisional_tail_reason(audit.bars)
        if tail:
            findings.append(f"{symbol}: {tail}")

    briefing = _load_json(ticker_dir / "briefing.json")
    technicals = _load_json(ticker_dir / "technicals.json")
    if briefing:
        latest = (technicals or {}).get("as_of_date") or (
            bars[-1].date.isoformat() if bars else None
        )
        freshness = assess_freshness(
            briefing.get("date"), briefing.get("data_as_of"), latest
        )
        if freshness.stale:
            findings.append(f"{symbol}: stale briefing — {freshness.reason}")
            findings.append(f"{symbol}:   rerun: stock-analysis {symbol}")

    return findings


def repair_ticker(ticker_dir: Path) -> str | None:
    """Drop unusable and provisional bars, recompute technicals.

    Returns a one-line note when something changed. A stale briefing is
    deliberately not "repaired" — only the LLM pipeline can do that, and
    silently re-dating a stale verdict is the defect, not the fix.
    """
    symbol = ticker_dir.name
    csv_path = ticker_dir / "price_history.csv"
    if not csv_path.exists():
        return None

    bars = _read_bars(csv_path)
    audit = drop_invalid_bars(bars)
    tail = provisional_tail_reason(audit.bars)
    if not audit.dropped and not tail:
        return None

    repaired = audit.bars[:-1] if tail else audit.bars
    if not repaired:
        return f"{symbol}: CANNOT FIX — no usable bars remain"

    _write_bars(csv_path, repaired)
    snapshot = compute_technicals(symbol, repaired)
    (ticker_dir / "technicals.json").write_text(snapshot.model_dump_json(indent=2))
    dropped = len(bars) - len(repaired)
    return (
        f"{symbol}: FIXED — dropped {dropped} bar(s), {len(repaired)} kept, "
        f"technicals recomputed to {snapshot.as_of_date}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Per-ticker data directory (default: ./data)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite price_history.csv without bad bars and recompute technicals",
    )
    args = parser.parse_args()

    base = Path(args.data_dir)
    if not base.exists():
        print(f"ERR data dir not found: {base}", file=sys.stderr)
        return 1

    ticker_dirs = sorted(
        d for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    repairs: list[str] = []
    if args.fix:
        for ticker_dir in ticker_dirs:
            note = repair_ticker(ticker_dir)
            if note:
                repairs.append(note)

    # Scanned after repairing, so the count reported is what is still wrong.
    findings: list[str] = []
    for ticker_dir in ticker_dirs:
        findings.extend(scan_ticker(ticker_dir))

    print(f"Audited {len(ticker_dirs)} tickers in {base}")
    for line in repairs:
        print(line)
    if repairs:
        print()
    for line in findings:
        print(line)

    blocking = [f for f in findings if ":   rerun:" not in f]
    if not findings:
        print("No findings.")
    else:
        print(f"\n{len(blocking)} finding(s) remaining.")
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
