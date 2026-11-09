"""The ``search_filings`` payload, kept apart from the agent so it is testable
without the Claude Agent SDK and so the fail-closed branches are explicit."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from stock_analysis.models.market_data import Market, TickerData

from .index import Embedder, FilingIndex, index_dir, load_default_embedder

TOOL_TOP_K = 4
PASSAGE_CHARS = 1200


@lru_cache(maxsize=1)
def _embedder() -> Embedder | None:
    # One ONNX session per process; the four analyst agents run concurrently
    # and only Fundamentals queries, so a single cached instance is enough.
    return load_default_embedder()


@lru_cache(maxsize=32)
def _load_index(directory: str, mtime: float) -> FilingIndex | None:
    # Keyed on the manifest mtime so a rebuilt index is picked up mid-process.
    return FilingIndex.load(Path(directory))


def search_filings_payload(
    ticker_data: TickerData,
    query: str,
    data_dir: str,
    *,
    embedder: Embedder | None = None,
) -> dict:
    symbol = ticker_data.info.symbol
    if ticker_data.info.market != Market.US:
        return {"available": False, "reason": "SEC filings cover US listings only"}
    if not query.strip():
        return {"available": False, "reason": "empty query"}

    directory = index_dir(data_dir, symbol)
    manifest = directory / "manifest.json"
    if not manifest.exists():
        return {"available": False, "reason": f"no filing index for {symbol}"}
    index = _load_index(str(directory), manifest.stat().st_mtime)
    if index is None:
        return {"available": False, "reason": f"filing index for {symbol} is incomplete"}

    as_of = ticker_data.fetched_at.date()
    result = index.search(query, as_of=as_of, embedder=embedder or _embedder(), k=TOOL_TOP_K)
    if not result.hits:
        return {
            "available": True,
            "as_of": as_of,
            "mode": result.mode,
            "passages": [],
            "reason": "no filing filed before the cutoff matched the query",
        }
    return {
        "available": True,
        "as_of": as_of,
        "mode": result.mode,
        "notes": result.notes,
        "passages": [
            {
                "form": hit.chunk.form,
                "filing_date": hit.chunk.filing_date,
                "section": hit.chunk.section,
                "accession": hit.chunk.accession,
                "retrieved_by": list(hit.retrievers),
                "text": hit.chunk.text[:PASSAGE_CHARS],
            }
            for hit in result.hits
        ],
    }
