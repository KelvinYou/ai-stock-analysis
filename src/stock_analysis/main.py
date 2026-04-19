from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from stock_analysis import __version__
from stock_analysis.config import Settings
from stock_analysis.orchestrator import AnalysisPipeline


def cli():
    parser = argparse.ArgumentParser(
        description="AI Stock Analysis — multi-agent investment research"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "ticker", help="Stock ticker symbol (e.g., AAPL, MSFT, MAYBANK, 1155)"
    )
    parser.add_argument(
        "--market",
        choices=["US", "MY"],
        default="US",
        help="Market: US (default) or MY (Bursa Malaysia)",
    )
    parser.add_argument(
        "--rounds", type=int, default=3, help="Number of debate rounds (default: 3)"
    )
    parser.add_argument(
        "--model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Model for analyst agents (default: haiku)",
    )
    parser.add_argument(
        "--debate-model",
        choices=["haiku", "sonnet", "opus"],
        default="opus",
        help="Model for debate agents (default: opus)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    settings = Settings(
        quick_think_model=args.model,
        deep_think_model=args.debate_model,
        debate_rounds=args.rounds,
    )

    pipeline = AnalysisPipeline(settings, market=args.market)
    briefing = asyncio.run(pipeline.run(args.ticker.upper()))

    print(briefing.model_dump_json(indent=2))


if __name__ == "__main__":
    cli()
