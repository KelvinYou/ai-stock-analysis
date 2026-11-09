"""Okapi BM25 in plain Python — the lexical half of hybrid retrieval.

Implemented here rather than imported for the same reason ``backtest/stats``
is: the corpus is a few thousand chunks per ticker, and a dependency would buy
nothing but a version to pin.

Corpus statistics (document frequency, average length) are computed over the
*candidate* set on every query, not over the whole index. The candidates are
the filings visible on the analysis date, so a filing published later cannot
shift the IDF of a term and re-rank what a backtest was allowed to see.
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+(?:[.'][a-z0-9]+)*")
# Short, closed list: filings repeat these on every line, so they carry no
# ranking signal, but domain words ("risk", "revenue") stay searchable.
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "which",
        "with",
        "our",
        "we",
        "us",
    }
)


def tokenize(text: str) -> list[str]:
    return [tok for tok in _TOKEN.findall(text.lower()) if tok not in STOPWORDS]


class BM25:
    def __init__(self, documents: list[str], *, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.term_freqs = [Counter(tokenize(doc)) for doc in documents]
        self.lengths = [sum(tf.values()) for tf in self.term_freqs]

    def scores(self, query: str, candidates: list[int]) -> dict[int, float]:
        terms = set(tokenize(query))
        if not terms or not candidates:
            return {}
        n = len(candidates)
        avg_length = sum(self.lengths[idx] for idx in candidates) / n or 1.0
        idf = {}
        for term in terms:
            df = sum(1 for idx in candidates if term in self.term_freqs[idx])
            idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))

        result: dict[int, float] = {}
        for idx in candidates:
            tf = self.term_freqs[idx]
            norm = self.k1 * (1 - self.b + self.b * self.lengths[idx] / avg_length)
            score = sum(
                idf[term] * tf[term] * (self.k1 + 1) / (tf[term] + norm)
                for term in terms
                if term in tf
            )
            if score > 0:
                result[idx] = score
        return result
