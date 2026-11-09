# Filing RAG retrieval eval — 2026-11-08

Index: newest 6 10-K/10-Q filings per ticker from EDGAR, built 2026-11-08
(AAPL 588, MSFT 1,311, NVDA 850 chunks). Embedder: `BAAI/bge-small-en-v1.5`.
Cutoff `--as-of 2026-11-08`, max filing age 455 days, k = 5.

| mode | hit@5 | 95% Wilson | MRR | n |
| --- | --- | --- | --- | --- |
| bm25 | 0.83 | 0.66–0.93 | 0.74 | 30 |
| dense | 0.90 | 0.74–0.97 | 0.84 | 30 |
| hybrid | 0.93 | 0.79–0.98 | 0.85 | 30 |

## What this shows and what it does not

- **Measured:** hybrid matched or beat both single retrievers on all 30 rows.
  No row was found by BM25 or dense alone and then lost by fusion.
- **Not shown:** that hybrid beats dense. The intervals overlap almost entirely,
  and the 30 rows are 10 questions × 3 tickers, so same-question rows are
  correlated and the intervals are optimistic.
- **Both misses** are "Is the company being sued…" for AAPL and MSFT. Hybrid
  returned Risk Factors passages about litigation exposure, which are on-topic
  for a reader. Under the section labels, though, they count as misses: the
  labels were fixed before this run and are not relaxed after it.
- **Not measured at all:** whether the Fundamentals desk makes better calls with
  the tool. That needs a with/without backtest ablation.

Rows, top-5 sections per query, and the summary: `results.json`.
Reproduce: `python scripts/eval_filings_retrieval.py AAPL MSFT NVDA --as-of 2026-11-08`
(after `stock-filings AAPL MSFT NVDA`). EDGAR adds filings over time, so a later
rebuild indexes different documents.
