from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import build_store
from stock_analysis.memory.cloud import build_outcome_store
from stock_analysis.memory.outcomes import records_from_backtest

from . import portfolio as portfolio_mod
from .factor import (
    FactorConfig,
    load_price_history,
    run_factor_backtest,
)
from .factor import (
    to_markdown as factor_to_markdown,
)
from .portfolio import PortfolioConfig
from .runner import Backtester
from .scorer import Scorer
from .session import prepare_session_bundle, score_session_bundle

logger = logging.getLogger(__name__)


def cli():
    load_env()
    parser = argparse.ArgumentParser(
        description="Backtest the AI stock analysis pipeline against historical prices."
    )
    parser.add_argument(
        "--mode",
        choices=["api", "factor", "session-prepare", "session-score"],
        default="api",
        help=(
            "api runs the SDK pipeline; factor runs the deterministic momentum slice; "
            "session-prepare writes point-in-time packets; session-score scores "
            "session predictions (default: api)."
        ),
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated list of tickers (e.g., AAPL,NVDA,MSFT).",
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--interval",
        choices=["weekly", "biweekly", "monthly", "quarterly"],
        default="monthly",
        help="Spacing between as-of dates (default: monthly).",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=30,
        help="Forward-looking holding period in calendar days (default: 30).",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=365,
        help="Historical price window passed to agents, in days (default: 365).",
    )
    parser.add_argument(
        "--factor-lookback-bars",
        type=int,
        default=20,
        help="Momentum lookback for --mode factor (default: 20 trading bars).",
    )
    parser.add_argument(
        "--factor-holding-bars",
        type=int,
        default=20,
        help="Holding period for --mode factor (default: 20 trading bars).",
    )
    parser.add_argument(
        "--walk-forward-train-bars",
        type=int,
        default=252,
        help="Initial expanding walk-forward warm-up for --mode factor (default: 252).",
    )
    parser.add_argument(
        "--walk-forward-test-bars",
        type=int,
        default=63,
        help="Out-of-sample window for --mode factor (default: 63 trading bars).",
    )
    parser.add_argument("--market", choices=["US", "MY"], default="US")
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Debate rounds per trial (default: 1 — backtest cost control).",
    )
    parser.add_argument(
        "--model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Model for analyst agents (default: haiku).",
    )
    parser.add_argument(
        "--debate-model",
        choices=["haiku", "sonnet", "opus"],
        default="sonnet",
        help="Model for debate agents (default: sonnet — haiku is too unreliable for structured output).",
    )
    parser.add_argument(
        "--synthesis-model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Model for synthesis (default: haiku).",
    )
    parser.add_argument(
        "--output",
        default="backtest_report",
        help="Output file prefix — writes <prefix>.json and <prefix>.md.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=Path("backtest_session"),
        help="Directory for session packets, predictions, and outcomes.",
    )
    parser.add_argument(
        "--record-outcomes",
        action="store_true",
        help=(
            "Append realized outcomes to the configured outcome backend so future runs "
            "see this track record. Off by default: recording changes what "
            "later runs read, so back-to-back backtests would stop being comparable."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Where per-ticker price history/outcomes live (default: data).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ignore cached briefings and re-run every trial.",
    )
    parser.add_argument(
        "--starting-balance",
        type=float,
        default=10_000.0,
        help="Simulated starting cash for portfolio simulation (default: 10000).",
    )
    parser.add_argument(
        "--position-size",
        type=float,
        default=0.10,
        help="Fraction of current cash allocated per trade (default: 0.10).",
    )
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Take short positions on sell/strong_sell signals (default: skip).",
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=0.0,
        help=(
            "One-way transaction cost in basis points (commission + spread + "
            "slippage), charged on entry and again on exit. Default 0 keeps "
            "historical reports comparable, but 0 is an assumption, not a "
            "neutral default — try 10 for liquid US large caps, 30-50+ for "
            "Bursa small caps."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.mode == "session-score":
        result = score_session_bundle(args.session_dir)
        _score_and_write(result, args)
        return

    if not args.tickers or not args.start or not args.end:
        parser.error("--tickers, --start, and --end are required for this mode")

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if start >= end:
        parser.error("--start must be before --end")

    dates = _build_dates(start, end, args.interval)
    if not dates:
        parser.error("No as-of dates generated — widen your date range.")

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        parser.error("--tickers is empty")

    if args.mode == "factor":
        if len(tickers) != 1:
            parser.error("--mode factor currently accepts exactly one ticker")
        _run_factor_and_write(tickers[0], start, end, args)
        return

    if args.mode == "session-prepare":
        manifest = prepare_session_bundle(
            tickers=tickers,
            as_of_dates=dates,
            output_dir=args.session_dir,
            market=args.market,
            horizon_days=args.horizon,
            lookback_days=args.lookback,
        )
        print(
            f"Prepared {len(manifest.trials)} session trials in {args.session_dir}."
        )
        print(
            "Have the current session write SessionPrediction JSON objects to "
            f"{args.session_dir / manifest.predictions_file}, then run:"
        )
        print(
            "  stock-analysis-backtest --mode session-score "
            f"--session-dir {args.session_dir}"
        )
        return

    settings = Settings.from_env(
        quick_think_model=args.model,
        deep_think_model=args.debate_model,
        synthesis_model=args.synthesis_model,
        debate_rounds=args.rounds,
    )
    backtester = Backtester(
        settings=settings,
        market=args.market,
        horizon_days=args.horizon,
        lookback_days=args.lookback,
    )
    args._settings = settings

    print(
        f"Running {len(tickers)} tickers × {len(dates)} dates = "
        f"{len(tickers) * len(dates)} trials. Horizon: {args.horizon}d."
    )

    try:
        result = asyncio.run(
            backtester.run(tickers, dates, resume=not args.no_resume)
        )
    finally:
        backtester.close()
    _score_and_write(result, args)


def _score_and_write(result, args) -> None:
    cost_bps = getattr(args, "cost_bps", 0.0) or 0.0
    report = Scorer.score(result, cost_bps_per_side=cost_bps)
    markdown = Scorer.to_markdown(result, report)

    portfolio_config = PortfolioConfig(
        starting_balance=args.starting_balance,
        position_size_pct=args.position_size,
        allow_short=args.allow_short,
        cost_bps_per_side=cost_bps,
    )
    portfolio_report = portfolio_mod.simulate(result, portfolio_config)
    portfolio_md = portfolio_mod.to_markdown(portfolio_report)
    markdown += "\n" + portfolio_md

    settings = getattr(args, "_settings", None) or Settings.from_env()
    payload = {
        "result": result.model_dump(mode="json"),
        "report": report.model_dump(mode="json"),
        "portfolio": portfolio_report.model_dump(mode="json"),
    }

    if settings.storage_backend == "supabase":
        store = build_store(settings)
        try:
            artifact_id = store.save_backtest_artifact(
                mode="api",
                tickers=sorted({trial.ticker for trial in result.trials}),
                payload=payload,
                markdown=markdown,
                metadata={"output": args.output, "cost_bps_per_side": cost_bps},
            )
        finally:
            close = getattr(store, "close", None)
            if close:
                close()
        print()
        print(markdown)
        print(f"Cloud artifact: {artifact_id}")
    else:
        out_json = Path(f"{args.output}.json")
        out_md = Path(f"{args.output}.md")
        out_json.write_text(
            '{"result": '
            + result.model_dump_json(indent=2)
            + ', "report": '
            + report.model_dump_json(indent=2)
            + ', "portfolio": '
            + portfolio_report.model_dump_json(indent=2)
            + "}"
        )
        out_md.write_text(markdown)
        print()
        print(markdown)
        print(f"Raw results: {out_json}")
        print(f"Report:      {out_md}")

    print()

    if getattr(args, "record_outcomes", False):
        outcome_store = build_outcome_store(settings)
        try:
            written = outcome_store.append(records_from_backtest(result))
            for ticker in sorted({t.ticker for t in result.trials}):
                outcome_store.save_calibration(ticker)
        finally:
            close = getattr(outcome_store, "close", None)
            if close:
                close()
        destination = "Supabase" if settings.storage_backend == "supabase" else f"{args.data_dir}/<TICKER>/outcomes.jsonl"
        print(f"Outcomes:    +{written} record(s) into {destination}")


def _run_factor_and_write(ticker: str, start: date, end: date, args) -> None:
    config = FactorConfig(
        lookback_bars=args.factor_lookback_bars,
        holding_bars=args.factor_holding_bars,
        initial_train_bars=args.walk_forward_train_bars,
        test_window_bars=args.walk_forward_test_bars,
        cost_bps_per_side=args.cost_bps,
    )
    settings = Settings.from_env()
    store = build_store(settings)
    if settings.storage_backend == "supabase":
        price_history = pd.DataFrame(
            [bar.model_dump(mode="json") for bar in store.load_price_history(ticker)]
        )
    else:
        price_path = Path(args.data_dir) / ticker / "price_history.csv"
        price_history = load_price_history(price_path)
    report = run_factor_backtest(
        ticker,
        price_history,
        start=start,
        end=end,
        config=config,
    )
    markdown = factor_to_markdown(report)
    output_prefix = args.output if args.output != "backtest_report" else "factor_report"
    try:
        if settings.storage_backend == "supabase":
            artifact_id = store.save_backtest_artifact(
                mode="factor",
                tickers=[ticker],
                payload={"report": report.model_dump(mode="json")},
                markdown=markdown,
                metadata={"output": output_prefix},
            )
            print(markdown)
            print(f"Cloud artifact: {artifact_id}")
        else:
            out_json = Path(f"{output_prefix}.json")
            out_md = Path(f"{output_prefix}.md")
            out_json.write_text(report.model_dump_json(indent=2))
            out_md.write_text(markdown)
            print(markdown)
            print(f"Raw results: {out_json}")
            print(f"Report:      {out_md}")
    finally:
        close = getattr(store, "close", None)
        if close:
            close()


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _build_dates(start: date, end: date, interval: str) -> list[date]:
    step = {
        "weekly": 7,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 91,
    }[interval]
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=step)
    return dates


if __name__ == "__main__":
    cli()
