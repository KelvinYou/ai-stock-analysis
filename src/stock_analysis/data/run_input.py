"""Canonical durable input identity, independent of provider and persistence."""

import json
from datetime import date
from hashlib import sha256

from stock_analysis.models.market_data import TickerData


def input_digest(payload: dict, as_of: date) -> str:
    encoded = json.dumps(
        {"as_of_date": as_of.isoformat(), "ticker_data": payload},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(encoded.encode()).hexdigest()


def validate_input(data: TickerData, as_of: date) -> None:
    if data.fetched_at.date() > as_of or any(b.date > as_of for b in data.price_history):
        raise ValueError(
            "Input capture or price bar exceeds run cutoff; current provider cannot initialize a historical run"
        )
