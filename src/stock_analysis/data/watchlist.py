"""Parse hand-curated ticker and theme markers from ``tickers.txt``.

The file is shared with ``web/lib/watchlist.ts``. Both parsers keep the
``#theme:`` marker semantics aligned; ``#group:`` comments are intentionally
ignored as legacy comments.

``@universe`` directives are skipped here for the same reason the TS parser
skips them: expanding one needs a network call, and universe members are not
hand-curated watchlist entries.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

THEME_MARKER = re.compile(r"^#\s*theme:\s*(.+?)\s*$", re.IGNORECASE)


class WatchlistEntry(BaseModel):
    symbol: str
    market: str
    theme: str | None = None


def parse_watchlist(text: str) -> list[WatchlistEntry]:
    """Return hand-listed entries with their current theme context.

    Theme markers persist until the next theme marker. The symbol is the
    display symbol (``MY:1155`` -> ``1155``), which is what ``TickerInfo.symbol``
    and therefore ``tickers.symbol`` carry.
    """
    entries: list[WatchlistEntry] = []
    seen: set[str] = set()
    theme: str | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = THEME_MARKER.match(line)
            if match:
                theme = match.group(1)
            continue
        if line.startswith("@"):
            continue

        is_my = line.upper().startswith("MY:")
        symbol = (line[3:] if is_my else line).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        entries.append(
            WatchlistEntry(
                symbol=symbol,
                market="MY" if is_my else "US",
                theme=theme,
            )
        )
    return entries


def load_watchlist_map(path: Path | str) -> dict[str, WatchlistEntry]:
    """Return ``{symbol: entry}``, empty when the file is absent.

    A missing watchlist is not an error: universe-driven fetches
    (``@us-major``) legitimately run without a hand-curated file.
    """
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return {entry.symbol: entry for entry in parse_watchlist(file_path.read_text())}
