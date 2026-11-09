"""Point-in-time retrieval over SEC 10-K / 10-Q text (hybrid BM25 + dense).

Layer 1 owns ingestion (``stock-filings`` builds the index, no LLM); the
Fundamentals agent only reads it through the ``search_filings`` MCP tool.
See docs/design/filings-rag.md for the invariants.
"""
