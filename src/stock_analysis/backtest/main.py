from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from stock_analysis.config import Settings

from . import portfolio as portfolio_mod
from .portfolio import PortfolioConfig
from .runner import Backtester
from .scorer import Scorer

logger = logging.getLogger(__name__)


def cli():
    parser = argparse.ArgumentParser(
        description="Backtest the AI stock analysis pipeline against historical prices."
    )
    parser.add_argument(
        "--tickers",
        required=True,
        help="Comma-separated list of tickers (e.g., AAPL,NVDA,MSFT).",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD.")
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
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

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

    settings = Settings(
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

    print(
        f"Running {len(tickers)} tickers × {len(dates)} dates = "
        f"{len(tickers) * len(dates)} trials. Horizon: {args.horizon}d."
    )

    result = asyncio.run(
        backtester.run(tickers, dates, resume=not args.no_resume)
    )
    report = Scorer.score(result)
    markdown = Scorer.to_markdown(result, report)

    portfolio_config = PortfolioConfig(
        starting_balance=args.starting_balance,
        position_size_pct=args.position_size,
        allow_short=args.allow_short,
    )
    portfolio_report = portfolio_mod.simulate(result, portfolio_config)
    portfolio_md = portfolio_mod.to_markdown(portfolio_report)
    markdown += "\n" + portfolio_md

    out_json = Path(f"{args.output}.json")
    out_md = Path(f"{args.output}.md")
    out_json.write_text(
        (
            '{"result": '
            + result.model_dump_json(indent=2)
            + ', "report": '
            + report.model_dump_json(indent=2)
            + ', "portfolio": '
            + portfolio_report.model_dump_json(indent=2)
            + "}"
        )
    )
    out_md.write_text(markdown)

    print()
    print(markdown)
    print(f"Raw results: {out_json}")
    print(f"Report:      {out_md}")


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
