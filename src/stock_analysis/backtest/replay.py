"""Load source-neutral, point-in-time replay evidence for session packets."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path

from pydantic import ValidationError

from stock_analysis.data.evidence import filter_point_in_time_news, financials_are_usable
from stock_analysis.data.fundamentals import select_financial_history
from stock_analysis.models.market_data import (
    FinancialStatements,
    HistoricalValuationPrice,
    MacroSnapshot,
)


def _read_records(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        records = [
            json.loads(line)
            for line in path.read_text().splitlines()
            if line.strip()
        ]
    else:
        raw = json.loads(path.read_text())
        records = raw if isinstance(raw, list) else [raw]
    return [dict(record) for record in records if isinstance(record, Mapping)]


def _find_file(directory: Path | None, stem: str) -> Path | None:
    if directory is None:
        return None
    for suffix in (".jsonl", ".json"):
        path = directory / f"{stem}{suffix}"
        if path.exists():
            return path
    return None


def historical_news_source(replay_dir: Path | None) -> str:
    """Return the declared replay class without upgrading an ambiguous source."""

    if replay_dir is None:
        return "not_configured"
    manifest_path = replay_dir / "manifest.json"
    if not manifest_path.exists():
        return "historical_replay"
    try:
        manifest = json.loads(manifest_path.read_text())
        source = manifest.get("news", {}).get("source", {})
    except (json.JSONDecodeError, OSError, AttributeError):
        return "historical_replay"
    if isinstance(source, Mapping) and source.get("kind") == "provider_versioned":
        return "historical_provider"
    return "historical_replay"


def load_news_replay(
    replay_dir: Path | None,
    ticker: str,
    as_of: date,
) -> list[dict]:
    """Load only news with publication and first-available dates before as-of."""
    path = _find_file(replay_dir, ticker.upper())
    records = _read_records(path)
    matching = [
        record
        for record in records
        if not record.get("ticker")
        or str(record["ticker"]).upper() == ticker.upper()
    ]
    return filter_point_in_time_news(
        matching,
        as_of=as_of,
        require_embargo=True,
    )


def load_macro_replay(path: Path | None, as_of: date) -> MacroSnapshot | None:
    """Return the latest macro snapshot knowable on ``as_of``."""
    candidates: list[MacroSnapshot] = []
    for index, record in enumerate(_read_records(path), start=1):
        try:
            snapshot = MacroSnapshot.model_validate(record)
        except ValidationError as exc:
            source = path or Path("<macro replay>")
            raise ValueError(f"Invalid macro replay record {source}:{index}") from exc
        if snapshot.as_of_date <= as_of and snapshot.available_as_of <= as_of:
            candidates.append(snapshot)
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.as_of_date, item.available_as_of))


def load_cash_rate_replay(
    path: Path,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[MacroSnapshot]:
    """Load dated FRED DFF observations for cash-yield diagnostics.

    Accepts the official FRED CSV or the point-in-time JSON/JSONL replay
    representation. Raw CSV observations use the existing conservative
    observation-date-plus-one-day availability rule.
    """
    if not path.is_file():
        raise ValueError(f"Cash-rate replay does not exist: {path}")
    lower = start_date - timedelta(days=7) if start_date else None
    observations: list[MacroSnapshot] = []
    if path.suffix.lower() == ".csv":
        for row in csv.DictReader(path.read_text().splitlines()):
            try:
                observed = date.fromisoformat(str(row["observation_date"]))
                rate = float(row["DFF"])
            except (KeyError, TypeError, ValueError):
                continue
            if lower is not None and observed < lower:
                continue
            if end_date is not None and observed > end_date:
                continue
            observations.append(
                MacroSnapshot(
                    as_of_date=observed,
                    available_as_of=observed + timedelta(days=1),
                    source="FRED:DFF",
                    fed_funds_rate=rate,
                )
            )
    else:
        records = _read_records(path)
        for index, record in enumerate(records, start=1):
            try:
                snapshot = MacroSnapshot.model_validate(record)
            except ValidationError as exc:
                raise ValueError(f"Invalid cash-rate record {path}:{index}") from exc
            if lower is not None and snapshot.as_of_date < lower:
                continue
            if end_date is not None and snapshot.as_of_date > end_date:
                continue
            observations.append(snapshot)

    if not observations:
        raise ValueError(f"Cash-rate replay is empty: {path}")
    seen_dates: set[date] = set()
    validated: list[MacroSnapshot] = []
    for index, snapshot in enumerate(observations, start=1):
        rate = snapshot.fed_funds_rate
        if snapshot.source != "FRED:DFF":
            raise ValueError(
                f"Cash-rate replay must contain only FRED:DFF records; "
                f"found {snapshot.source!r} at {path}:{index}"
            )
        if (
            rate is None
            or not math.isfinite(rate)
            or rate < 0
            or snapshot.available_as_of < snapshot.as_of_date
        ):
            raise ValueError(f"Invalid dated FRED:DFF value at {path}:{index}")
        if snapshot.as_of_date in seen_dates:
            raise ValueError(
                f"Duplicate FRED:DFF observation date {snapshot.as_of_date} in {path}"
            )
        seen_dates.add(snapshot.as_of_date)
        validated.append(snapshot)

    return sorted(
        validated,
        key=lambda item: (item.available_as_of, item.as_of_date),
    )


def load_fundamentals_replay(
    replay_dir: Path | None,
    ticker: str,
    as_of: date,
) -> FinancialStatements | None:
    """Return the latest SEC point-in-time financial snapshot knowable at as-of."""

    history = load_fundamentals_history_replay(replay_dir, ticker, as_of)
    return history[-1] if history else None


def load_fundamentals_history_replay(
    replay_dir: Path | None, ticker: str, as_of: date,
) -> list[FinancialStatements]:
    """Return each fiscal duration's latest vintage knowable at the cutoff."""
    path = _find_file(replay_dir / "fundamentals" if replay_dir else None, ticker.upper())
    candidates: list[FinancialStatements] = []
    for index, record in enumerate(_read_records(path), start=1):
        if record.get("ticker") and str(record["ticker"]).upper() != ticker.upper():
            continue
        try:
            financials = FinancialStatements.model_validate(record)
        except ValidationError as exc:
            source = path or Path("<fundamentals replay>")
            raise ValueError(f"Invalid fundamentals replay record {source}:{index}") from exc
        if financials_are_usable(financials, as_of):
            candidates.append(financials)
    return select_financial_history(candidates, as_of)


def load_valuation_price_replay(
    replay_dir: Path | None, ticker: str, as_of: date,
) -> HistoricalValuationPrice | None:
    """Load a separate dated price with a declared corporate-action basis."""
    path = _find_file(replay_dir / "valuation" if replay_dir else None, ticker.upper())
    candidates: dict[tuple[date, date], HistoricalValuationPrice] = {}
    for index, record in enumerate(_read_records(path), start=1):
        if record.get("ticker") and str(record["ticker"]).upper() != ticker.upper():
            continue
        try:
            price = HistoricalValuationPrice.model_validate(record)
        except ValidationError as exc:
            raise ValueError(f"Invalid valuation price replay record {path}:{index}") from exc
        if price.price_date > price.available_as_of or price.available_as_of > as_of:
            continue
        key = (price.price_date, price.available_as_of)
        if key in candidates and candidates[key] != price:
            raise ValueError(f"Conflicting valuation price vintages at {path}:{index}")
        candidates[key] = price
    return max(candidates.values(), key=lambda p: (p.price_date, p.available_as_of), default=None)
