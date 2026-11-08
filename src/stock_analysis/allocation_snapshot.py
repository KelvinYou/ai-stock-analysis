"""Dated price-only momentum previews, separate from sealed portfolio plans."""

import math
import re
from datetime import date, datetime

import pandas as pd


def build_current_momentum(
    histories: dict[str, pd.DataFrame], *, today: date, month_end_anchor: bool = False
) -> dict:
    """Rank a complete synchronized panel; reject missing evidence without partial weights."""

    def unavailable(reason):
        return {"status": "unavailable", "reason": reason}

    if len(histories) < 3:
        return unavailable("At least three complete symbols are required.")
    frames = {}
    for ticker, original in histories.items():
        if not ticker or original.empty or not {"date", "close"} <= set(original.columns):
            return unavailable("Missing price history.")
        frame = original[["date", "close"]].copy()
        try:
            # Provider-local session labels must not be converted across midnight.
            frame["date"] = frame["date"].map(lambda x: pd.Timestamp(x).date())
            frame["close"] = pd.to_numeric(frame["close"], errors="raise")
        except (ValueError, TypeError):
            return unavailable("Invalid price or date.")
        if (
            frame.date.duplicated().any()
            or frame.date.isna().any()
            or not all(math.isfinite(x) and x > 0 for x in frame.close)
        ):
            return unavailable("Duplicate dates or invalid close prices.")
        frames[ticker] = frame.sort_values("date")
    tails = {frame.date.iloc[-1] for frame in frames.values()}
    if len(tails) != 1:
        return unavailable("All symbols must share one completed session.")
    as_of = next(iter(tails))
    if as_of >= today or (today - as_of).days > 4:
        return unavailable("Require a prior completed date no older than four calendar days.")
    cutoff = (pd.Timestamp(as_of) - pd.DateOffset(months=12)).date()
    if month_end_anchor:
        # Monthly backtests compare the last common close in the same calendar
        # month one year earlier, which can fall after as_of.day (e.g. Oct 31
        # versus Oct 30). Daily previews retain the trailing-date convention.
        cutoff = (
            pd.Timestamp(as_of).replace(day=1) - pd.DateOffset(years=1) + pd.offsets.MonthEnd(0)
        ).date()
        common_dates = set.intersection(*(set(frame.date) for frame in frames.values()))
        frames = {ticker: frame[frame.date.isin(common_dates)] for ticker, frame in frames.items()}
    ranking = []
    for ticker, frame in frames.items():
        prior = frame[frame.date <= cutoff]
        if prior.empty or (cutoff - prior.date.iloc[-1]).days > 7:
            return unavailable(f"Missing 12-month price anchor: {ticker}.")
        ranking.append(
            {
                "ticker": ticker,
                "score": float(frame.close.iloc[-1] / prior.close.iloc[-1] - 1),
                "lookback_date": prior.date.iloc[-1].isoformat(),
                "target_weight": 0.0,
            }
        )
    ranking.sort(key=lambda row: (-row["score"], row["ticker"]))
    for row in ranking[:3]:
        row["target_weight"] = 1 / 3
    return {
        "status": "available",
        "scope": "indicative_price_only",
        "as_of": as_of.isoformat(),
        "lookback_months": 12,
        "top_n": 3,
        "universe": sorted(histories),
        "ranking": ranking,
    }


def public_current_momentum(
    raw: dict, *, universe: list[str], source_hash: str, today: date
) -> dict:
    """Allowlist a pinned public artifact; an expired snapshot never gains fresh weights."""
    if raw.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "reason": "Complete current price evidence is unavailable.",
        }
    if (
        raw.get("status") != "available"
        or raw.get("scope") != "indicative_price_only"
        or raw.get("lookback_months") != 12
        or raw.get("top_n") != 3
        or sorted(raw.get("universe", [])) != sorted(universe)
        or len(set(universe)) != len(universe)
        or not re.fullmatch(r"[a-f0-9]{64}", source_hash)
    ):
        raise ValueError("Invalid current momentum contract")
    as_of = date.fromisoformat(raw["as_of"])
    captured = datetime.fromisoformat(raw["captured_at_utc"])
    if captured.tzinfo is None or captured.date() < as_of or captured.date() > today:
        raise ValueError("Invalid current momentum capture clock")
    if as_of >= today or (today - as_of).days > 4:
        return {
            "status": "unavailable",
            "reason": "Current ranking expired; refresh the complete price panel.",
        }
    ranking = raw.get("ranking", [])
    if len(ranking) != len(universe) or sorted(r.get("ticker", "") for r in ranking) != sorted(
        universe
    ):
        raise ValueError("Current ranking requires complete universe coverage")
    clean = []
    for index, row in enumerate(ranking):
        score = row.get("score")
        anchor = date.fromisoformat(row["lookback_date"])
        cutoff = (pd.Timestamp(as_of) - pd.DateOffset(months=12)).date()
        expected_weight = 1 / 3 if index < 3 else 0
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or score <= -1
            or not 0 <= (cutoff - anchor).days <= 7
            or row.get("target_weight") != expected_weight
        ):
            raise ValueError("Invalid current momentum row")
        clean.append(
            {
                "ticker": row["ticker"],
                "score": score,
                "lookback_date": anchor.isoformat(),
                "target_weight": expected_weight,
            }
        )
    if clean != sorted(clean, key=lambda row: (-row["score"], row["ticker"])):
        raise ValueError("Current momentum ranking is not ordered")
    return {
        "status": "available",
        "scope": "indicative_price_only",
        "as_of": as_of.isoformat(),
        "captured_at_utc": captured.isoformat(),
        "source_sha256": source_hash,
        "lookback_months": 12,
        "top_n": 3,
        "universe": sorted(universe),
        "ranking": clean,
    }
