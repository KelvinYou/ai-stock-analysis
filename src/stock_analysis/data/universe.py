"""Ticker universe loaders — pull constituent lists from public sources.

Each loader returns yfinance-ready symbols:
- US tickers with dots normalized to dashes (BRK.B → BRK-B)
- MY (Bursa) tickers zero-padded to 4 digits with .KL suffix (1155 → 1155.KL)

Results are cached in-process to avoid repeat HTTP during one fetch run.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

import httpx
import pandas as pd

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ100_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
FBMKLCI_URL = "https://en.wikipedia.org/wiki/FTSE_Bursa_Malaysia_KLCI"

_HEADERS = {"User-Agent": "Mozilla/5.0 (ai-stock-analysis; daily-fetch)"}


def _read_tables(url: str) -> list[pd.DataFrame]:
    resp = httpx.get(url, headers=_HEADERS, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    return pd.read_html(resp.text)


def _find_table_with_column(tables: list[pd.DataFrame], column: str) -> pd.DataFrame:
    for df in tables:
        cols = [c for c in df.columns if isinstance(c, str)]
        if column in cols:
            return df
    raise ValueError(f"no table with column {column!r} on page")


@lru_cache(maxsize=1)
def get_sp500() -> list[str]:
    df = _read_tables(SP500_URL)[0]
    symbols = df["Symbol"].astype(str).str.replace(".", "-", regex=False)
    return sorted(set(symbols.tolist()))


@lru_cache(maxsize=1)
def get_nasdaq100() -> list[str]:
    tables = _read_tables(NASDAQ100_URL)
    df = _find_table_with_column(tables, "Ticker")
    return sorted(set(df["Ticker"].astype(str).tolist()))


@lru_cache(maxsize=1)
def get_us_major() -> list[str]:
    return sorted(set(get_sp500()) | set(get_nasdaq100()))


@lru_cache(maxsize=1)
def get_fbmklci() -> list[str]:
    tables = _read_tables(FBMKLCI_URL)
    df = _find_table_with_column(tables, "Stock Code")
    codes = df["Stock Code"].astype(str).str.extract(r"(\d+)", expand=False).dropna()
    return sorted({code.zfill(4) for code in codes.tolist()})


UNIVERSE_LOADERS: dict[str, tuple[str, Callable[[], list[str]]]] = {
    "sp500": ("US", get_sp500),
    "nasdaq100": ("US", get_nasdaq100),
    "us-major": ("US", get_us_major),
    "my-klci": ("MY", get_fbmklci),
}


def resolve_universe(name: str) -> list[tuple[str, str]]:
    """Expand a universe name to a list of (ticker, market) pairs."""
    key = name.lower().lstrip("@")
    if key not in UNIVERSE_LOADERS:
        raise ValueError(
            f"unknown universe {name!r}; known: {sorted(UNIVERSE_LOADERS)}"
        )
    market, loader = UNIVERSE_LOADERS[key]
    return [(t, market) for t in loader()]
