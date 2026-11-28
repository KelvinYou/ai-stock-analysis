"""Run the point-in-time strategy comparison on local price CSVs and freeze the result."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from stock_analysis.backtest.factor import load_price_history
from stock_analysis.backtest.strategy_comparison import (
    StrategyComparisonConfig,
    run_strategy_comparison,
    to_markdown,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tickers", required=True, help="Comma-separated, e.g. AVGO,COST,MSFT")
    ap.add_argument("--name", required=True, help="Output stem, e.g. primary8")
    ap.add_argument("--start", type=date.fromisoformat)
    ap.add_argument("--end", type=date.fromisoformat)
    ap.add_argument("--fundamentals-dir", type=Path, help="Point-in-time SEC replay folder")
    ap.add_argument("--cost-bps", type=float, default=20.0)
    ap.add_argument("--top-n", type=int, default=3)
    ap.add_argument("--output", type=Path, default=ROOT / "reports/analysis/2026-11-11-strategy-comparison")
    args = ap.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    histories = {t: load_price_history(ROOT / "data" / t / "price_history.csv") for t in tickers}
    report = run_strategy_comparison(
        histories, start=args.start, end=args.end, fundamentals_dir=args.fundamentals_dir,
        config=StrategyComparisonConfig(cost_bps_per_side=args.cost_bps, top_n=args.top_n),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"{args.name}-{args.cost_bps:g}bps"
    (args.output / f"{stem}.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, allow_nan=False) + "\n"
    )
    (args.output / f"{stem}.md").write_text(to_markdown(report))
    print(to_markdown(report))


if __name__ == "__main__":
    main()
