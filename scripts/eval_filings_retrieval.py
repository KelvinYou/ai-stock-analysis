"""Compare BM25, dense and hybrid retrieval on the filing index.

Usage (after ``stock-filings AAPL MSFT NVDA``):

    python scripts/eval_filings_retrieval.py AAPL MSFT NVDA [--as-of 2026-11-08]

Reports hit@k (any relevant section in the top k) and MRR per mode, pooled
over tickers x queries, with a Wilson interval on hit@k — the same rule as the
backtests: a point estimate on 30 queries does not ship alone.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from stock_analysis.backtest.stats import wilson_interval
from stock_analysis.filings.index import FilingIndex, index_dir, load_default_embedder

MODES = ("bm25", "dense", "hybrid")


def evaluate(tickers, as_of, config, data_dir="data"):
    embedder = load_default_embedder()
    if embedder is None:
        raise SystemExit("fastembed unavailable: pip install -e '.[rag]'")
    k = config["k"]
    rows = []
    for ticker in tickers:
        index = FilingIndex.load(index_dir(data_dir, ticker))
        if index is None:
            raise SystemExit(f"No index for {ticker}: run stock-filings {ticker}")
        for item in config["queries"]:
            relevant = set(item["relevant"])
            for mode in MODES:
                result = index.search(item["q"], as_of=as_of, k=k, embedder=embedder, mode=mode)
                if result.mode != mode:
                    raise SystemExit(f"{ticker}: asked for {mode}, ran {result.mode}")
                ranks = [i for i, hit in enumerate(result.hits, 1) if hit.chunk.section in relevant]
                rows.append(
                    {
                        "ticker": ticker,
                        "query": item["q"],
                        "mode": mode,
                        "hit": bool(ranks),
                        "rr": 1 / ranks[0] if ranks else 0.0,
                        "top_sections": [hit.chunk.section for hit in result.hits],
                    }
                )
    return rows


def summarize(rows, k):
    lines = [f"| mode | hit@{k} | 95% Wilson | MRR | n |", "| --- | --- | --- | --- | --- |"]
    summary = {}
    for mode in MODES:
        sub = [r for r in rows if r["mode"] == mode]
        hits = sum(r["hit"] for r in sub)
        low, high = wilson_interval(hits, len(sub))
        mrr = sum(r["rr"] for r in sub) / len(sub)
        summary[mode] = {"hits": hits, "n": len(sub), "wilson": [low, high], "mrr": mrr}
        lines.append(
            f"| {mode} | {hits / len(sub):.2f} | {low:.2f}–{high:.2f} | {mrr:.2f} | {len(sub)} |"
        )
    return "\n".join(lines), summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--config", default="config/filings_retrieval_eval.json")
    parser.add_argument("--out", help="Write rows + summary JSON here")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text())
    tickers = [t.upper() for t in args.tickers]
    rows = evaluate(tickers, args.as_of, config)
    table, summary = summarize(rows, config["k"])
    print(table)
    if args.out:
        out = {"as_of": args.as_of.isoformat(), "tickers": tickers, "summary": summary,
               "rows": rows}
        Path(args.out).write_text(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    main()
