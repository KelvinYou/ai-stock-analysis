"""Immutable prospective research cohorts; scores only after exit closes.

This workflow never places orders, writes outcome memory, or changes forecasts.
US and MY returns are evaluated separately in their local currencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from stock_analysis.config import Settings
from stock_analysis.models.agent_reports import AnalystReports
from stock_analysis.models.synthesis import Briefing

from .portfolio import PortfolioConfig, simulate, to_markdown
from .runner import Backtester, BacktestResult, BacktestTrial, execution_signal
from .scorer import Scorer


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(
    source: Path,
    output: Path,
    *,
    forecast_date: date,
    horizon: int = 30,
    cost_bps: float = 10,
    stress_bps: float = 20,
) -> dict:
    today = datetime.now(UTC).date()
    if forecast_date != today or horizon <= 0 or min(cost_bps, stress_bps) <= 0:
        raise ValueError("Freeze must be today, with positive horizon and costs")
    rows = []
    files = []
    for path in sorted(source.glob("*/briefing.json")):
        briefing = Briefing.model_validate_json(path.read_text())
        ticker = briefing.ticker
        if path.parent.name != ticker or date.fromisoformat(briefing.date) != forecast_date:
            raise ValueError(f"Forecast identity/date mismatch: {path}")
        if briefing.data_as_of is None or date.fromisoformat(briefing.data_as_of) > forecast_date:
            raise ValueError(f"Missing/future data clock: {ticker}")
        analyst_path = path.parent / "analyst_reports.json"
        analysts = AnalystReports.model_validate_json(analyst_path.read_text())
        info_path = source / "inputs" / ticker / "fundamentals.json"
        info = json.loads(info_path.read_text())["info"]
        if info["symbol"] != ticker or info["market"] not in ("US", "MY"):
            raise ValueError(f"Invalid market identity: {ticker}")
        signal = execution_signal(briefing)
        rows.append(
            dict(
                ticker=ticker,
                market=info["market"],
                currency=info["currency"],
                as_of_date=forecast_date.isoformat(),
                data_as_of=briefing.data_as_of,
                overall_signal=signal.value,
                conviction_score=briefing.conviction.score,
                signal_convergence=briefing.conviction.signal_convergence,
                agent_signals={
                    n: getattr(analysts, n).signal.value
                    for n in ("fundamentals", "sentiment", "technical", "macro")
                },
            )
        )
        files.extend(
            [
                path,
                analyst_path,
                path.parent / "debate_result.json",
                path.parent / "research_verdict.json",
            ]
        )
        files.extend((source / "inputs" / ticker).glob("*"))
    if not rows or len({x["ticker"] for x in rows}) != len(rows):
        raise ValueError("Empty/duplicate cohort")
    if any(not p.is_file() for p in files):
        raise ValueError("Incomplete source artifacts")
    output.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for path in files:
        target = output / "frozen" / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[str(target.relative_to(output))] = _hash(target)
    predictions = output / "predictions.json"
    predictions.write_text(json.dumps(rows, indent=2) + "\n")
    hashes["predictions.json"] = _hash(predictions)
    protocol = dict(
        version=1,
        frozen_at_utc=datetime.now(UTC).isoformat(),
        forecast_date=forecast_date.isoformat(),
        entry_target=(forecast_date + timedelta(days=1)).isoformat(),
        exit_target=(forecast_date + timedelta(days=horizon)).isoformat(),
        score_not_before_utc=(forecast_date + timedelta(days=horizon + 1)).isoformat(),
        horizon_days=horizon,
        source=str(source),
        count=len(rows),
        hashes=hashes,
        cost_bps_per_side=cost_bps,
        stress_bps_per_side=stress_bps,
        allow_short=False,
        markets_separate=True,
        position_size=0.1,
        starting_balance=10000,
        benchmark="strict equal-weight hold and same-exposure passive",
        execution="first eligible open on/after entry_target; first eligible close on/after exit_target; no limit/stop simulation",
        cost_note="Frozen assumptions: US10/20bps; MY50/100bps per side. Not broker-calibrated.",
        market_cost_bps={"US": [cost_bps, stress_bps], "MY": [50, 100]},
        limits=[
            "One cohort cannot establish statistical reliability",
            "Prices are adjusted provider bars, not licensed vintage total-return proof",
            "Fixed current watchlist; future conclusions apply only to this cohort",
            "No FX conversion or aggregate US/MY return",
            "Neutral/sell skip new long allocations; no real holdings or orders",
        ],
    )
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(protocol, indent=2) + "\n")
    (output / "manifest.sha256").write_text(_hash(manifest) + "\n")
    return protocol


def verify(output: Path) -> dict:
    path = output / "manifest.json"
    if _hash(path) != (output / "manifest.sha256").read_text().strip():
        raise ValueError("Frozen manifest changed")
    protocol = json.loads(path.read_text())
    for name, digest in protocol["hashes"].items():
        target = (output / name).resolve()
        if not target.is_relative_to(output.resolve()) or _hash(target) != digest:
            raise ValueError(f"Frozen artifact changed: {name}")
    return protocol


def score(output: Path) -> None:
    protocol = verify(output)
    today = datetime.now(UTC).date()
    if today < date.fromisoformat(protocol["score_not_before_utc"]):
        raise ValueError(
            f"Cohort not mature; no price fetch before {protocol['score_not_before_utc']} UTC"
        )
    rows = json.loads((output / "predictions.json").read_text())
    results = {}
    for market in sorted({x["market"] for x in rows}):
        runner = Backtester(
            Settings(storage_backend="local"), market=market, horizon_days=protocol["horizon_days"]
        )
        trials, paths = [], {}
        for row in rows:
            if row["market"] != market:
                continue
            entry_target = date.fromisoformat(protocol["entry_target"])
            exit_target = date.fromisoformat(protocol["exit_target"])
            hist = runner._fetch_price_series(
                row["ticker"], entry_target, min(today, exit_target + timedelta(days=11))
            )
            entry, entered = runner._price_on_or_after(hist, entry_target, price_column="Open")
            exit_price, exited = runner._price_on_or_after(hist, exit_target)
            if not entry or not exit_price or not exited or exited >= today:
                raise ValueError(
                    f"Incomplete completed outcome: {row['ticker']}; fixed panel is not reduced"
                )
            trials.append(
                BacktestTrial(
                    ticker=row["ticker"],
                    as_of_date=date.fromisoformat(row["as_of_date"]),
                    horizon_days=protocol["horizon_days"],
                    entry_price=entry,
                    entry_date=entered,
                    exit_price=exit_price,
                    exit_date=exited,
                    realized_return=exit_price / entry - 1,
                    overall_signal=row["overall_signal"],
                    conviction_score=row["conviction_score"],
                    signal_convergence=row["signal_convergence"],
                    agent_signals=row["agent_signals"],
                )
            )
            paths[row["ticker"]] = runner._price_bars(hist)
        result = BacktestResult(
            trials=trials,
            settings={
                "market": market,
                "pipeline_mode": "prospective-frozen",
                "horizon_days": protocol["horizon_days"],
                "entry_execution": "next_session_open",
            },
            started_at=date.fromisoformat(protocol["forecast_date"]),
            finished_at=today,
            price_paths=paths,
        )
        arms = {}
        for bps in protocol["market_cost_bps"][market]:
            stats = Scorer.score(result, cost_bps_per_side=bps)
            portfolio = simulate(result, PortfolioConfig(cost_bps_per_side=bps))
            arms[str(bps)] = {
                "report": stats.model_dump(mode="json"),
                "portfolio": portfolio.model_dump(mode="json"),
            }
            results.setdefault("markdown", []).append(
                f"## {market}, {bps} bps per side\n\n"
                + Scorer.to_markdown(result, stats)
                + "\n"
                + to_markdown(portfolio)
            )
        results[market] = {"result": result.model_dump(mode="json"), "arms": arms}
    markdown = results.pop("markdown")
    # No partial results are written when a market/ticker is missing.
    with (output / "score.json").open("x") as f:
        json.dump(results, f, indent=2)
    (output / "score.md").write_text(
        "[Status: Warning] Prospective cohort; one date cluster is insufficient to establish edge.\n\n"
        + "\n".join(markdown)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "verify", "score"])
    parser.add_argument("--cohort", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--forecast-date", type=date.fromisoformat)
    args = parser.parse_args()
    if args.action == "freeze":
        if not args.source or not args.forecast_date:
            parser.error("freeze requires --source and --forecast-date")
        protocol = freeze(args.source, args.cohort, forecast_date=args.forecast_date)
        print(f"Frozen {protocol['count']} predictions; exit {protocol['exit_target']}")
    elif args.action == "verify":
        protocol = verify(args.cohort)
        rows = json.loads((args.cohort / "predictions.json").read_text())
        print(
            f"Verified {protocol['count']} immutable forecasts: {dict(Counter(x['overall_signal'] for x in rows))}"
        )
    else:
        score(args.cohort)


if __name__ == "__main__":
    main()
