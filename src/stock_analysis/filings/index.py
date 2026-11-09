"""Hybrid (BM25 + dense) retrieval over filing chunks, with a point-in-time gate.

Two invariants:

- **Visibility is filing date, strictly before the analysis date.** The same
  rule as ``OutcomeRecord.visible_on``: a filing dated on the analysis day may
  have been accepted after the close, so it is not admitted. A backtest that
  could retrieve a later 10-K would be grading the model on the future.
- **The mode is reported, never silently degraded.** Without the embedding
  model (optional ``[rag]`` extra) or with vectors built by a different model,
  search falls back to BM25 and says so in ``SearchResult.mode``; it never
  mixes vectors from two embedding spaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

import numpy as np

from .bm25 import BM25
from .chunking import Chunk

DEFAULT_EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RRF_K = 60  # Cormack et al.'s constant; rank fusion is insensitive to it near 60
CANDIDATE_POOL = 50
# One annual cycle plus a quarter: the latest 10-K and the 10-Qs after it.
# Older text is still in the index but would compete with current disclosures.
DEFAULT_MAX_AGE_DAYS = 455
# Token-set Jaccard at which two chunks count as the same disclosure restated.
DUPLICATE_JACCARD = 0.8


class Embedder(Protocol):
    model_name: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    """Local ONNX embeddings: no API key, and identical vectors on every run,
    which is what lets a backtest replay the same retrieval."""

    def __init__(self, model_name: str = DEFAULT_EMBED_MODEL):
        from fastembed import TextEmbedding  # optional dependency: pip install .[rag]

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return _normalize(np.array(list(self._model.passage_embed(texts)), dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalize(np.array(list(self._model.query_embed(text)), dtype=np.float32))[0]


def load_default_embedder() -> Embedder | None:
    """None when the extra is missing or the model cannot load (e.g. offline
    first run); callers fall back to BM25 and report the mode."""
    try:
        return FastEmbedEmbedder()
    except Exception:  # ImportError, or a model download/ONNX failure
        return None


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float
    retrievers: tuple[str, ...]


@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]
    mode: str  # "hybrid" | "bm25" | "dense"
    visible_chunks: int
    hidden_future_chunks: int
    notes: list[str] = field(default_factory=list)


def rrf_fuse(rankings: dict[str, list[int]], k: int = RRF_K) -> list[tuple[int, float, tuple]]:
    """Reciprocal rank fusion: each retriever votes 1/(k + rank)."""
    scores: dict[int, float] = {}
    sources: dict[int, list[str]] = {}
    for name, ranking in rankings.items():
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
            sources.setdefault(idx, []).append(name)
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    return [(idx, score, tuple(sources[idx])) for idx, score in ordered]


class FilingIndex:
    def __init__(
        self,
        chunks: list[Chunk],
        vectors: np.ndarray | None = None,
        embed_model: str | None = None,
    ):
        if vectors is not None and len(vectors) != len(chunks):
            raise ValueError("vector count does not match chunk count")
        self.chunks = chunks
        self.vectors = vectors
        self.embed_model = embed_model
        self._bm25 = BM25([chunk.text for chunk in chunks])
        self._dates = [date.fromisoformat(chunk.filing_date) for chunk in chunks]

    @classmethod
    def build(cls, chunks: list[Chunk], embedder: Embedder | None) -> FilingIndex:
        if embedder is None or not chunks:
            return cls(chunks)
        vectors = embedder.embed_passages([chunk.text for chunk in chunks])
        return cls(chunks, vectors, embedder.model_name)

    def visible(self, as_of: date, max_age_days: int) -> tuple[list[int], int]:
        oldest = as_of - timedelta(days=max_age_days)
        visible = [i for i, filed in enumerate(self._dates) if oldest <= filed < as_of]
        future = sum(1 for filed in self._dates if filed >= as_of)
        return visible, future

    def search(
        self,
        query: str,
        *,
        as_of: date,
        k: int = 5,
        embedder: Embedder | None = None,
        max_age_days: int = DEFAULT_MAX_AGE_DAYS,
        mode: str = "hybrid",
    ) -> SearchResult:
        candidates, future = self.visible(as_of, max_age_days)
        notes: list[str] = []
        rankings: dict[str, list[int]] = {}

        if mode in ("hybrid", "bm25"):
            lexical = self._bm25.scores(query, candidates)
            rankings["bm25"] = sorted(lexical, key=lambda i: (-lexical[i], i))[:CANDIDATE_POOL]

        if mode in ("hybrid", "dense"):
            if self.vectors is None:
                notes.append("index has no vectors; dense retrieval skipped")
            elif embedder is None:
                notes.append("embedding model unavailable (install .[rag]); dense skipped")
            elif embedder.model_name != self.embed_model:
                notes.append(
                    f"query model {embedder.model_name} != index model {self.embed_model}; "
                    "dense skipped rather than mixing embedding spaces"
                )
            elif candidates:
                sims = self.vectors[candidates] @ embedder.embed_query(query)
                order = np.argsort(-sims, kind="stable")[:CANDIDATE_POOL]
                rankings["dense"] = [candidates[int(i)] for i in order]

        used = "hybrid" if len(rankings) == 2 else next(iter(rankings), "none")
        fused = self._collapse_restatements(rrf_fuse(rankings)[: k * 3])[:k]
        hits = [SearchHit(self.chunks[i], score, src) for i, score, src in fused]
        return SearchResult(hits, used, len(candidates), future, notes)

    def _collapse_restatements(self, fused: list[tuple[int, float, tuple]]) -> list:
        """Keep one copy of text a company repeats filing after filing.

        Risk-factor language is carried forward almost verbatim, so last year's
        10-K and this year's both rank and fill the top k with one passage. The
        newest copy is kept (in the better-ranked slot): it is the one the
        company currently stands behind.
        """
        kept: list[list] = []
        for idx, score, sources in fused:
            tokens = self._bm25.term_freqs[idx].keys()
            for entry in kept:
                other = self._bm25.term_freqs[entry[0]].keys()
                overlap = len(tokens & other) / (len(tokens | other) or 1)
                if overlap >= DUPLICATE_JACCARD:
                    if self._dates[idx] > self._dates[entry[0]]:
                        entry[0] = idx
                    break
            else:
                kept.append([idx, score, sources])
        return [tuple(entry) for entry in kept]

    # --- persistence: data/<TICKER>/filings/{chunks.jsonl, vectors.npy, manifest.json}

    def save(self, directory: Path, filings: list[dict]) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "chunks.jsonl").open("w") as handle:
            for chunk in self.chunks:
                handle.write(json.dumps(chunk.to_dict()) + "\n")
        vectors_path = directory / "vectors.npy"
        if self.vectors is not None:
            np.save(vectors_path, self.vectors)
        elif vectors_path.exists():
            vectors_path.unlink()  # stale vectors from an older build must not survive
        manifest = {
            "built_at": datetime.now(UTC).isoformat(),
            "embed_model": self.embed_model,
            "chunk_count": len(self.chunks),
            "filings": filings,
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    @classmethod
    def load(cls, directory: Path) -> FilingIndex | None:
        chunks_path = directory / "chunks.jsonl"
        manifest_path = directory / "manifest.json"
        if not chunks_path.exists() or not manifest_path.exists():
            return None
        manifest = json.loads(manifest_path.read_text())
        with chunks_path.open() as handle:
            chunks = [Chunk(**json.loads(line)) for line in handle if line.strip()]
        vectors_path = directory / "vectors.npy"
        vectors = np.load(vectors_path) if vectors_path.exists() else None
        return cls(chunks, vectors, manifest.get("embed_model") if vectors is not None else None)


def index_dir(data_dir: str | Path, ticker: str) -> Path:
    return Path(data_dir) / ticker.upper() / "filings"
