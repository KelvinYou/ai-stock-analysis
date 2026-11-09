"""``stock-filings``: build the per-ticker filing index (Layer 1, no LLM).

Kept out of the analysis run on purpose: retrieval during a run only reads a
local index, so an analysis (or a backtest replay) never depends on EDGAR being
reachable, and the same index gives the same hits every time.
"""

from __future__ import annotations

import argparse
import os
import sys

from stock_analysis.config import load_env

from .chunking import chunk_filing
from .edgar import fetch_filing_text, list_filings
from .index import FilingIndex, index_dir, load_default_embedder


def build_ticker_index(
    ticker: str,
    *,
    user_agent: str,
    data_dir: str,
    limit: int,
    dense: bool = True,
) -> FilingIndex:
    refs = list_filings(ticker, user_agent=user_agent, limit=limit)
    if not refs:
        raise RuntimeError(f"No 10-K/10-Q filings found on EDGAR for {ticker}")
    chunks = []
    for ref in refs:
        text = fetch_filing_text(ref, user_agent=user_agent)
        filing_chunks = chunk_filing(
            text,
            ticker=ref.ticker,
            form=ref.form,
            filing_date=ref.filing_date.isoformat(),
            accession=ref.accession,
        )
        print(f"  {ref.form} {ref.filing_date} → {len(filing_chunks)} chunks", file=sys.stderr)
        chunks.extend(filing_chunks)

    embedder = load_default_embedder() if dense else None
    if dense and embedder is None:
        print(
            "  fastembed not installed (pip install -e '.[rag]'): BM25-only index", file=sys.stderr
        )
    index = FilingIndex.build(chunks, embedder)
    filings = [
        {
            "form": r.form,
            "filing_date": r.filing_date.isoformat(),
            "accession": r.accession,
            "url": r.url,
        }
        for r in refs
    ]
    index.save(index_dir(data_dir, ticker), filings)
    return index


def cli() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Build the SEC filing RAG index (US tickers).")
    parser.add_argument("tickers", nargs="+", help="US ticker symbols, e.g. AAPL MSFT")
    parser.add_argument("--limit", type=int, default=6, help="Newest N 10-K/10-Q filings")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--no-dense", action="store_true", help="Skip embeddings (BM25 only)")
    parser.add_argument(
        "--user-agent",
        default=os.environ.get("SEC_USER_AGENT"),
        help="SEC-required identifying user-agent with a contact address "
        "(default: $SEC_USER_AGENT)",
    )
    args = parser.parse_args()
    if not args.user_agent:
        parser.error(
            "SEC requires an identifying user-agent: pass --user-agent or set SEC_USER_AGENT"
        )

    failed = []
    for ticker in args.tickers:
        print(f"{ticker.upper()}:", file=sys.stderr)
        try:
            index = build_ticker_index(
                ticker,
                user_agent=args.user_agent,
                data_dir=args.data_dir,
                limit=args.limit,
                dense=not args.no_dense,
            )
        except (RuntimeError, ValueError) as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            failed.append(ticker)
            continue
        mode = "hybrid" if index.vectors is not None else "bm25-only"
        print(f"  indexed {len(index.chunks)} chunks ({mode})", file=sys.stderr)
    sys.exit(1 if failed else 0)
