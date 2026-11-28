"""Fetch point-in-time SEC CompanyFacts fundamentals for a ticker list (read-only, public)."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from stock_analysis.backtest.replay_builder import build_sec_fundamentals

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", required=True)
    ap.add_argument("--start", type=date.fromisoformat, default=date(2017, 1, 1))
    ap.add_argument("--end", type=date.fromisoformat, required=True)
    ap.add_argument("--user-agent", default="ai-stock-analysis research script")
    ap.add_argument("--output", type=Path, default=ROOT / "reports/analysis/2026-11-11-fundamentals-pit")
    args = ap.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    folder = args.output / "fundamentals"
    folder.mkdir(parents=True, exist_ok=True)
    coverage = {}
    source: dict = {}
    for ticker in tickers:  # one at a time so one bad filer cannot lose the rest
        try:
            grouped, source = build_sec_fundamentals(
                [ticker], start=args.start, end=args.end, user_agent=args.user_agent,
                lookback_days=800,
            )
        except Exception as exc:
            coverage[ticker] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:200]}
            continue
        rows = grouped.get(ticker, [])
        (folder / f"{ticker}.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True, allow_nan=False) + "\n" for r in rows)
        )
        coverage[ticker] = {
            "status": "ok", "records": len(rows),
            "first_available": rows[0]["available_as_of"] if rows else None,
            "last_available": rows[-1]["available_as_of"] if rows else None,
        }
        print(ticker, coverage[ticker], flush=True)
    (args.output / "manifest.json").write_text(
        json.dumps({"source": source, "coverage": coverage}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
