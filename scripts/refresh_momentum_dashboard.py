"""Download prices and publish an AI-free momentum dashboard snapshot.

No analyst calls, model keys, personal holdings, or broker connections.
--prices-dir reads an existing public OHLCV panel for offline reproduction.
"""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from stock_analysis.data.bars import sanitize_bars
from stock_analysis.models.market_data import PriceBar
from stock_analysis.momentum_dashboard import build_momentum_dashboard

ROOT = Path(__file__).resolve().parents[1]


def publish_snapshot(
    histories,
    config,
    output: Path,
    *,
    now: datetime,
    price_evidence=None,
    reference=None,
    reference_evidence=None,
    comparisons=None,
    comparison_evidence=None,
):
    snapshot = build_momentum_dashboard(
        histories,
        config,
        now=now,
        price_evidence=price_evidence,
        reference=reference,
        reference_evidence=reference_evidence,
        comparisons=comparisons,
        comparison_evidence=comparison_evidence,
    )
    if snapshot["preview"]["status"] != "available":
        raise ValueError(snapshot["preview"]["reason"])
    if snapshot["monthly"]["status"] != "available":
        raise ValueError(snapshot["monthly"]["reason"])
    completed = [
        row
        for row in snapshot["session_calendar"]["sessions"]
        if datetime.fromisoformat(row["close_utc"]) <= now
    ]
    if not completed or snapshot["preview"]["as_of"] != completed[-1]["date"]:
        raise ValueError(
            "Price panel does not cover the latest completed exchange session; preserve the previous snapshot"
        )
    payload = json.dumps(snapshot, indent=2, allow_nan=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Validation finishes before replacing either published file. Hash mismatch
    # during a concurrent read fails closed and is retried on the next page load.
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(payload)
    os.replace(temporary, output)
    output.with_suffix(".sha256").write_text(hashlib.sha256(payload.encode()).hexdigest() + "\n")
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices-dir", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "web/data/momentum.json")
    parser.add_argument(
        "--price-evidence", type=Path, help="Public source/gap metadata for local inputs"
    )
    parser.add_argument(
        "--reference-prices", type=Path, help="Optional SPY OHLCV CSV for matched references"
    )
    parser.add_argument(
        "--reference-evidence", type=Path, help="Public provenance for the reference panel"
    )
    parser.add_argument(
        "--comparison-prices-dir", type=Path, help="Optional VOO/VT public OHLCV panel directory"
    )
    parser.add_argument(
        "--comparison-evidence", type=Path, help="Public evidence keyed by comparison ticker"
    )
    args = parser.parse_args()
    if args.price_evidence and not args.prices_dir:
        parser.error("--price-evidence requires --prices-dir")
    config = json.loads((ROOT / "config/momentum.json").read_text())
    now = datetime.now(UTC)
    histories = {}
    evidence = (
        json.loads(args.price_evidence.read_text())
        if args.price_evidence
        else {
            "primary_source": {
                "name": "Local price files" if args.prices_dir else "Yahoo Finance (yfinance)",
                "url": None if args.prices_dir else "https://finance.yahoo.com/",
            },
            "supplemental_source": None,
            "missing_sessions": [],
            "supplemented_sessions": [],
        }
    )
    excluded = {}
    for ticker in config["universe"]:
        if args.prices_dir:
            nested = args.prices_dir / ticker / "price_history.csv"
            path = nested if nested.exists() else args.prices_dir / f"{ticker}.csv"
            frame = pd.read_csv(path)
        else:
            import yfinance as yf

            start = (pd.Timestamp(now.date()) - pd.DateOffset(months=18)).date()
            frame = yf.Ticker(ticker).history(
                start=str(start), end=str(now.date()), auto_adjust=True, actions=False
            )
            frame.index = (
                frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
            )
            frame = frame.rename_axis("date").reset_index().rename(columns=str.lower)
        if frame.empty:
            raise ValueError(f"Missing history: {ticker}")
        bars = [
            PriceBar(
                date=pd.Timestamp(row["date"]).date(),
                **{k: row[k] for k in ("open", "high", "low", "close", "volume")},
            )
            for row in frame.to_dict("records")
        ]
        audit = sanitize_bars(sorted(bars, key=lambda bar: bar.date))
        if audit.dropped:
            print(f"{ticker}: excluded {len(audit.dropped)} invalid/provisional bars")
        kept_dates = {bar.date for bar in audit.bars}
        for bar in bars:
            if bar.date not in kept_dates:
                excluded.setdefault(str(bar.date), set()).add(ticker)
        histories[ticker] = pd.DataFrame(
            [{"date": str(bar.date), "open": bar.open, "close": bar.close} for bar in audit.bars]
        )
    gaps = {row["date"]: set(row["tickers"]) for row in evidence["missing_sessions"]}
    for session, tickers in excluded.items():
        gaps.setdefault(session, set()).update(tickers)
    evidence["missing_sessions"] = [
        {"date": session, "tickers": sorted(tickers)} for session, tickers in sorted(gaps.items())
    ]
    reference, reference_evidence = None, None
    reference_ticker = config.get("reference", {}).get("ticker", "SPY")
    reference_path = args.reference_prices or (
        args.prices_dir / f"{reference_ticker}.csv" if args.prices_dir else None
    )
    try:
        if reference_path:
            reference_frame = pd.read_csv(reference_path)
        else:
            import yfinance as yf

            start = (pd.Timestamp(now.date()) - pd.DateOffset(months=18)).date()
            reference_frame = yf.Ticker(reference_ticker).history(
                start=str(start),
                end=str(now.date()),
                auto_adjust=True,
                actions=False,
            )
            reference_frame.index = (
                reference_frame.index.tz_localize(None)
                if reference_frame.index.tz is not None
                else reference_frame.index
            )
            reference_frame = (
                reference_frame.rename_axis("date").reset_index().rename(columns=str.lower)
            )
        reference_bars = [
            PriceBar(
                date=pd.Timestamp(row["date"]).date(),
                **{k: row[k] for k in ("open", "high", "low", "close", "volume")},
            )
            for row in reference_frame.to_dict("records")
        ]
        audit = sanitize_bars(sorted(reference_bars, key=lambda bar: bar.date))
        reference = pd.DataFrame(
            [{"date": str(b.date), "open": b.open, "close": b.close} for b in audit.bars]
        )
        reference_evidence = (
            json.loads(args.reference_evidence.read_text())
            if args.reference_evidence
            else {
                "primary_source": {
                    "name": "Local price files" if reference_path else "Yahoo Finance (yfinance)",
                    "url": None if reference_path else "https://finance.yahoo.com/",
                },
                "supplemental_source": None,
                "missing_sessions": [],
                "supplemented_sessions": [],
            }
        )
        retained = {b.date for b in audit.bars}
        gaps = {row["date"]: set(row["tickers"]) for row in reference_evidence["missing_sessions"]}
        for b in reference_bars:
            if b.date not in retained:
                gaps.setdefault(str(b.date), set()).add(reference_ticker)
        reference_evidence["missing_sessions"] = [
            {"date": d, "tickers": sorted(t)} for d, t in sorted(gaps.items())
        ]
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"{reference_ticker} reference unavailable: {type(error).__name__}")
        reference = None
        reference_evidence = None
    comparisons, comparison_evidence = {}, {}
    supplied_evidence = (
        json.loads(args.comparison_evidence.read_text()) if args.comparison_evidence else {}
    )
    comparison_dir = args.comparison_prices_dir or (
        args.reference_prices.parent if args.reference_prices else args.prices_dir
    )
    for item in config.get("comparison_references", []):
        ticker = item["ticker"]
        try:
            if comparison_dir:
                frame = pd.read_csv(comparison_dir / f"{ticker}.csv")
            else:
                import yfinance as yf

                start = (pd.Timestamp(now.date()) - pd.DateOffset(months=18)).date()
                frame = yf.Ticker(ticker).history(
                    start=str(start), end=str(now.date()), auto_adjust=True, actions=False
                )
                frame.index = (
                    frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
                )
                frame = frame.rename_axis("date").reset_index().rename(columns=str.lower)
            bars = [
                PriceBar(
                    date=pd.Timestamp(row["date"]).date(),
                    **{k: row[k] for k in ("open", "high", "low", "close", "volume")},
                )
                for row in frame.to_dict("records")
            ]
            audit = sanitize_bars(sorted(bars, key=lambda b: b.date))
            comparisons[ticker] = pd.DataFrame(
                [{"date": str(b.date), "open": b.open, "close": b.close} for b in audit.bars]
            )
            meta = supplied_evidence.get(
                ticker,
                {
                    "primary_source": {
                        "name": "Local price files"
                        if comparison_dir
                        else "Yahoo Finance (yfinance)",
                        "url": None if comparison_dir else "https://finance.yahoo.com/",
                    },
                    "supplemental_source": None,
                    "missing_sessions": [],
                    "supplemented_sessions": [],
                },
            )
            retained = {b.date for b in audit.bars}
            gaps = {r["date"]: set(r["tickers"]) for r in meta["missing_sessions"]}
            for bar in bars:
                if bar.date not in retained:
                    gaps.setdefault(str(bar.date), set()).add(ticker)
            meta["missing_sessions"] = [
                {"date": d, "tickers": sorted(t)} for d, t in sorted(gaps.items())
            ]
            comparison_evidence[ticker] = meta
        except (OSError, KeyError, ValueError, TypeError) as error:
            print(f"{ticker} reference unavailable: {type(error).__name__}")
    # A claimed replacement must survive sanitization, not merely exist in raw input.
    snapshot = publish_snapshot(
        histories,
        config,
        args.output,
        now=now,
        price_evidence=evidence,
        reference=reference,
        reference_evidence=reference_evidence,
        comparisons=comparisons,
        comparison_evidence=comparison_evidence,
    )
    print("Daily preview: " + ", ".join(r["ticker"] for r in snapshot["preview"]["ranking"][:3]))
    print(
        f"Monthly model ({snapshot['monthly']['as_of']}): "
        + ", ".join(r["ticker"] for r in snapshot["monthly"]["ranking"][:3])
    )


if __name__ == "__main__":
    main()
