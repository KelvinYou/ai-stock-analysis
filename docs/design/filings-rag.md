# Filing RAG — point-in-time retrieval over SEC 10-K / 10-Q text

**Status:** shipped 2026-11-08 · **Owner module:** `src/stock_analysis/filings/`

## Why

The Fundamentals desk saw only numbers: statements, ratios, analyst targets. The
reasons behind those numbers live in prose (risk factors, MD&A, legal
proceedings, liquidity), and the desk had no way to read them. `search_filings`
gives it the company's own text, with citations, under the same point-in-time
rule as every other input.

## Shape

```text
stock-filings AAPL ──► EDGAR submissions ──► primary 10-K/10-Q HTML
   (Layer 1, no LLM)        │
                            ▼
              html_to_text (drops hidden iXBRL header)
                            ▼
              split_sections (form-aware Item labels)
                            ▼
              pack_paragraphs (≤1500 chars) ──► chunks.jsonl
                            ▼
              bge-small-en-v1.5 via fastembed ──► vectors.npy (+ manifest.json)

FundamentalsAgent ── search_filings(query) ──► visible(as_of) ──► BM25 ┐
                                                              └► dense ┴► RRF ──► collapse restatements ──► top 4
```

## Invariants

1. **Visibility = filing date strictly before the analysis date.** Same rule as
   `OutcomeRecord.visible_on`. Filings dated on the cutoff day can be accepted
   after the close, so they are excluded.
2. **BM25 statistics come from the visible set only.** IDF and average length are
   computed per query over the candidates, so a later filing cannot re-rank what
   a backtest was allowed to see (`test_future_documents_do_not_change_bm25_scores`).
3. **The mode is reported, never silently degraded.** Without the `[rag]` extra,
   or with vectors from a different model, search runs BM25-only and returns
   `mode="bm25"` plus a note. Vectors from two embedding spaces are never mixed.
4. **The analysis run never calls EDGAR.** The index is built ahead of time by
   `stock-filings`. A run without an index gets `available: false` and proceeds
   on statements alone. MY tickers always get `available: false`.
5. **Restated text collapses to the newest copy.** Risk factors carry forward
   almost verbatim; token-set Jaccard ≥ 0.8 is treated as one disclosure, and
   the latest filing's copy is kept.

## Choices and the alternatives rejected

| Choice | Rejected | Why |
| --- | --- | --- |
| Local ONNX embeddings (fastembed, bge-small) | Voyage API | Same vectors on every run, so backtests replay; no key, no per-call cost |
| BM25 + dense fused by RRF | Dense only | Lexical matches exact terms (product names, "repurchase") that small embedders blur; RRF needs no score calibration |
| Per-ticker files under `data/<T>/filings/` | Supabase pgvector | Matches the flat DataStore layout; no network in the analysis path. Derived data, so it is git-ignored |
| Section labels from (form, part, item) | Item number alone | "Item 2" is Properties in a 10-K and MD&A in a 10-Q |

## Evaluation

`scripts/eval_filings_retrieval.py` scores section-level relevance on 10
investor-phrased questions (`config/filings_retrieval_eval.json`) per ticker.
Results for 2026-11-08 are in `reports/analysis/2026-11-08-filings-rag-eval/`.

Limits of that eval, stated up front:

- Relevance is section-level and the labels come from the same parser, so it
  measures ranking, not parsing.
- 30 rows are 10 questions × 3 tickers. Same-question rows are correlated, so
  the Wilson intervals are optimistic.
- It does not measure whether retrieval improves the agent's calls. That needs a
  backtest ablation with and without the tool, which has not been run.

## Operating

```bash
pip install -e '.[rag]'                       # dense half; omit for BM25-only
SEC_USER_AGENT="Name email@example.com" stock-filings AAPL MSFT NVDA
python scripts/eval_filings_retrieval.py AAPL MSFT NVDA --out results.json
```
