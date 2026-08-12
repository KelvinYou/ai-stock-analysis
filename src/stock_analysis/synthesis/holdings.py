"""Read-only view of real holdings, for portfolio-level gating only.

Scope boundary: `personal-os`'s `make wealth` remains the owner of net-worth
and allocation reporting. This module exists because Layer 5 cannot decide
whether one more position is safe without knowing what is already held, and it
reads only what it needs for that: holding facts from `portfolio.yaml`,
concentration caps from `policy.yaml`, the FX rate from `fx.yaml`, and prices
from this repo's own `data/<TICKER>/technicals.json` product.

Two rules inherited from `policy.yaml`, both load-bearing:

1. A `null` policy target takes the "cannot compute" path. It never falls back
   to a default cap, because a made-up cap produces a confident verdict about a
   constraint the user never set.
2. An unpriced holding is reported as unpriced, never dropped. Dropping it
   would shrink the denominator and make every exposure percentage look safer
   than it is.

Every field is optional: with no `data/` submodule checked out (the public
clone case) the snapshot loads as unavailable and the gate degrades to WATCH
rather than inventing an approval.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_ENV_FINANCE_DIR = "STOCK_ANALYSIS_FINANCE_DIR"
_ENV_MARKET_DIR = "STOCK_ANALYSIS_MARKET_DIR"

# How far up from the repo root to look for the personal-os private data dir.
_MAX_PARENT_WALK = 4


class Holding(BaseModel):
    """One real position. `value_myr` is None when the position is unpriced."""

    symbol: str
    code: str | None = None
    market: str
    currency: str
    shares: float
    avg_cost: float | None = None
    price: float | None = None
    price_as_of: date | None = None
    sector: str | None = None
    value_myr: float | None = None

    @property
    def data_key(self) -> str:
        """Directory name this holding's price/sector data lives under."""
        return self.code or self.symbol.upper()


class ConcentrationPolicy(BaseModel):
    """Caps from `policy.yaml`. All optional — null means "user has not set it"."""

    max_single_position_pct_of_equity: float | None = None
    max_sector_pct_of_equity: float | None = None
    max_usd_pct_of_tracked_investable_assets: float | None = None
    source: str = "unavailable"

    @property
    def available(self) -> bool:
        return self.source != "unavailable"


class HoldingsSnapshot(BaseModel):
    """Priced holdings plus the caveats needed to read the percentages honestly."""

    holdings: list[Holding] = Field(default_factory=list)
    source: str = "unavailable"
    usd_myr: float | None = None
    fx_as_of: date | None = None
    unpriced: list[str] = Field(default_factory=list)
    missing_sector: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.source != "unavailable"

    @property
    def equity_value_myr(self) -> float | None:
        """Total priced equity value. None when nothing could be priced."""
        values = [h.value_myr for h in self.holdings if h.value_myr is not None]
        if not values:
            return None
        return round(sum(values), 2)

    @property
    def fully_priced(self) -> bool:
        """Derived from the holdings themselves, not from the `unpriced` list.

        `unpriced` is only populated by `load_holdings`; a snapshot built any
        other way would report itself fully priced while holding None values.
        """
        return self.available and all(h.value_myr is not None for h in self.holdings)

    def find(self, ticker: str) -> Holding | None:
        """Match an analyzed ticker against holdings by symbol or Bursa code."""
        wanted = _normalise_keys(ticker)
        for holding in self.holdings:
            keys = _normalise_keys(holding.symbol) | _normalise_keys(holding.code or "")
            if wanted & keys:
                return holding
        return None

    def sector_value_myr(self, sector: str) -> float | None:
        """Priced value in one sector, or None when no holding maps to it."""
        target = sector.strip().lower()
        values = [
            h.value_myr
            for h in self.holdings
            if h.value_myr is not None and (h.sector or "").strip().lower() == target
        ]
        if not values:
            return None
        return round(sum(values), 2)


def _normalise_keys(raw: str) -> set[str]:
    """Return the set of forms a ticker may be written in (`1155`, `1155.KL`)."""
    token = raw.strip().upper()
    if not token:
        return set()
    keys = {token}
    if token.endswith(".KL"):
        keys.add(token[:-3])
    else:
        keys.add(f"{token}.KL")
    try:
        from stock_analysis.data.my_market import BURSA_ALIASES

        if token in BURSA_ALIASES:
            code = BURSA_ALIASES[token]
            keys |= {code, f"{code}.KL"}
        for alias, code in BURSA_ALIASES.items():
            if token in (code, f"{code}.KL"):
                keys.add(alias)
    except ImportError:  # pragma: no cover - my_market is always present
        pass
    return keys


def _load_yaml(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML is not installed; cannot read %s", path)
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not parse %s: %s", path, exc)
        return None
    return raw if isinstance(raw, dict) else None


def _repo_root() -> Path:
    # src/stock_analysis/synthesis/holdings.py -> repo root
    return Path(__file__).resolve().parents[3]


def find_finance_dir(explicit: Path | None = None) -> Path | None:
    """Locate `data/finance/`, or None when the private submodule is absent."""
    if explicit is not None:
        return explicit if (explicit / "portfolio.yaml").is_file() else None
    env = os.environ.get(_ENV_FINANCE_DIR)
    if env:
        candidate = Path(env).expanduser()
        return candidate if (candidate / "portfolio.yaml").is_file() else None
    base = _repo_root()
    for parent in [base, *base.parents[:_MAX_PARENT_WALK]]:
        candidate = parent / "data" / "finance"
        if (candidate / "portfolio.yaml").is_file():
            return candidate
    return None


def find_market_dir() -> Path | None:
    """Locate personal-os `market/` (public FX observations)."""
    env = os.environ.get(_ENV_MARKET_DIR)
    if env:
        candidate = Path(env).expanduser()
        return candidate if candidate.is_dir() else None
    base = _repo_root()
    for parent in [base, *base.parents[:_MAX_PARENT_WALK]]:
        candidate = parent / "market"
        if (candidate / "fx.yaml").is_file():
            return candidate
    return None


def load_concentration_policy(finance_dir: Path | None = None) -> ConcentrationPolicy:
    """Read concentration caps. Absent or null keys stay None by design."""
    directory = find_finance_dir(finance_dir)
    if directory is None:
        return ConcentrationPolicy()
    path = directory / "policy.yaml"
    raw = _load_yaml(path)
    if raw is None:
        return ConcentrationPolicy()
    block = raw.get("concentration") or {}
    return ConcentrationPolicy(
        max_single_position_pct_of_equity=_as_float(
            block.get("max_single_position_pct_of_equity")
        ),
        max_sector_pct_of_equity=_as_float(block.get("max_sector_pct_of_equity")),
        max_usd_pct_of_tracked_investable_assets=_as_float(
            block.get("max_usd_pct_of_tracked_investable_assets")
        ),
        source=str(path),
    )


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _load_fx(market_dir: Path | None) -> tuple[float | None, date | None, str | None]:
    """Return the USD/MYR rate, its as-of date, and a warning when unusable."""
    if market_dir is None:
        return None, None, "USD/MYR rate unavailable — USD holdings cannot be valued in MYR."
    raw = _load_yaml(market_dir / "fx.yaml")
    pair = ((raw or {}).get("pairs") or {}).get("USD_MYR") or {}
    rate = _as_float(pair.get("rate"))
    as_of = pair.get("as_of")
    if isinstance(as_of, str):
        try:
            as_of = date.fromisoformat(as_of)
        except ValueError:
            as_of = None
    if not isinstance(as_of, date):
        as_of = None
    if rate is None:
        return None, as_of, "USD/MYR rate missing from fx.yaml — USD holdings unpriced."
    return rate, as_of, None


def _pipeline_price(data_dir: Path, key: str) -> tuple[float, date] | None:
    """Read close + as_of_date from this repo's technicals product."""
    path = data_dir / key / "technicals.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return float(raw["close"]), date.fromisoformat(raw["as_of_date"])
    except (ValueError, KeyError, TypeError, OSError):
        return None


def _pipeline_sector(data_dir: Path, key: str) -> str | None:
    path = data_dir / key / "fundamentals.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    info = raw.get("info") if isinstance(raw, dict) else None
    sector = (info or {}).get("sector") if isinstance(info, dict) else None
    return str(sector) if sector else None


def load_holdings(
    data_dir: str | Path = "data",
    finance_dir: Path | None = None,
    market_dir: Path | None = None,
) -> HoldingsSnapshot:
    """Load real holdings priced with this repo's own technicals snapshots.

    Prices deliberately come from the pipeline rather than a live quote: the
    gate must reason about the same price the rest of the briefing quotes.
    """
    directory = find_finance_dir(finance_dir)
    if directory is None:
        return HoldingsSnapshot(
            warnings=[
                ("personal-os data/finance/portfolio.yaml not found — "
                "portfolio-level exposure cannot be checked.")
            ]
        )

    path = directory / "portfolio.yaml"
    raw = _load_yaml(path)
    if raw is None:
        return HoldingsSnapshot(
            warnings=[f"Could not read {path} — portfolio-level exposure unchecked."]
        )

    prices_dir = Path(data_dir)
    fx_rate, fx_as_of, fx_warning = _load_fx(
        market_dir if market_dir is not None else find_market_dir()
    )

    holdings: list[Holding] = []
    unpriced: list[str] = []
    missing_sector: list[str] = []
    warnings: list[str] = []
    if fx_warning:
        warnings.append(fx_warning)

    for market, currency, key in (("US", "USD", "us_holdings"), ("MY", "MYR", "my_holdings")):
        for entry in raw.get(key) or []:
            if not isinstance(entry, dict):
                continue
            symbol = str(entry.get("symbol") or "").strip().upper()
            shares = _as_float(entry.get("shares"))
            if not symbol or not shares:
                continue
            code = entry.get("code")
            code = str(code).strip() if code else None
            data_key = code or symbol

            priced = _pipeline_price(prices_dir, data_key)
            price = priced[0] if priced else None
            price_as_of = priced[1] if priced else None

            if price is None:
                value_myr = None
            elif currency == "USD":
                value_myr = round(shares * price * fx_rate, 2) if fx_rate else None
            else:
                value_myr = round(shares * price, 2)

            if value_myr is None:
                unpriced.append(symbol)

            sector = _pipeline_sector(prices_dir, data_key)
            if sector is None:
                missing_sector.append(symbol)

            holdings.append(
                Holding(
                    symbol=symbol,
                    code=code,
                    market=market,
                    currency=currency,
                    shares=shares,
                    avg_cost=_as_float(entry.get("avg_cost_usd") or entry.get("avg_cost")),
                    price=price,
                    price_as_of=price_as_of,
                    sector=sector,
                    value_myr=value_myr,
                )
            )

    if unpriced:
        warnings.append(
            f"{len(unpriced)} holding(s) unpriced ({', '.join(sorted(set(unpriced)))}) — "
            "exposure percentages understate true concentration."
        )
    if missing_sector:
        warnings.append(
            f"No sector on file for {', '.join(sorted(set(missing_sector)))} — "
            "sector exposure is partial."
        )

    return HoldingsSnapshot(
        holdings=holdings,
        source=str(path),
        usd_myr=fx_rate,
        fx_as_of=fx_as_of,
        unpriced=sorted(set(unpriced)),
        missing_sector=sorted(set(missing_sector)),
        warnings=warnings,
    )
