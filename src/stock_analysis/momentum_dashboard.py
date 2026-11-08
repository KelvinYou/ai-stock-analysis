"""AI-free current and completed-month momentum views over one public price panel."""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

import pandas as pd

from stock_analysis.allocation_snapshot import build_current_momentum
from stock_analysis.momentum_calendar import build_session_calendar
from stock_analysis.momentum_context import build_momentum_context


def validate_price_evidence(evidence: dict, universe: list[str]) -> dict:
    """Allowlist public provenance; absent metadata remains unknown on old snapshots."""

    def source(value, *, optional=False):
        if value is None and optional:
            return None
        if not isinstance(value, dict) or set(value) != {"name", "url"}:
            raise ValueError("Invalid price source")
        if (
            not isinstance(value["name"], str)
            or not value["name"].strip()
            or len(value["name"]) > 160
        ):
            raise ValueError("Invalid price source name")
        url = value["url"]
        if url is not None:
            if not isinstance(url, str):
                raise ValueError("Invalid price source URL")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Invalid price source URL")
        return dict(value)

    if not isinstance(evidence, dict) or set(evidence) != {
        "primary_source",
        "supplemental_source",
        "missing_sessions",
        "supplemented_sessions",
    }:
        raise ValueError("Invalid price evidence")
    result = {
        "primary_source": source(evidence["primary_source"]),
        "supplemental_source": source(evidence["supplemental_source"], optional=True),
    }
    for field in ("missing_sessions", "supplemented_sessions"):
        sessions = evidence[field]
        if not isinstance(sessions, list):
            raise ValueError("Invalid price evidence sessions")
        clean = []
        for item in sessions:
            if not isinstance(item, dict) or set(item) != {"date", "tickers"}:
                raise ValueError("Invalid price evidence session")
            session, tickers = item["date"], item["tickers"]
            if not isinstance(session, str) or date.fromisoformat(session).isoformat() != session:
                raise ValueError("Invalid price evidence date")
            if (
                not isinstance(tickers, list)
                or not tickers
                or any(not isinstance(t, str) or t not in universe for t in tickers)
                or len(set(tickers)) != len(tickers)
            ):
                raise ValueError("Invalid price evidence tickers")
            if any(row["date"] == session for row in clean):
                raise ValueError("Duplicate price evidence date")
            clean.append({"date": session, "tickers": sorted(tickers)})
        result[field] = sorted(clean, key=lambda row: row["date"])
    missing = {row["date"]: set(row["tickers"]) for row in result["missing_sessions"]}
    if result["supplemented_sessions"] and result["supplemental_source"] is None:
        raise ValueError("Supplemented sessions require a source")
    for row in result["supplemented_sessions"]:
        if not set(row["tickers"]) <= missing.get(row["date"], set()):
            raise ValueError("Supplemented sessions must identify a primary-source gap")
    return result


def build_momentum_dashboard(
    histories: dict[str, pd.DataFrame],
    config: dict,
    *,
    now: datetime,
    price_evidence: dict | None = None,
    reference: pd.DataFrame | None = None,
    reference_evidence: dict | None = None,
    comparisons: dict[str, pd.DataFrame] | None = None,
    comparison_evidence: dict | None = None,
) -> dict:
    if now.tzinfo is None:
        raise ValueError("An explicit capture timezone is required")
    now = now.astimezone(UTC)
    universe = config.get("universe", [])
    if (
        config.get("lookback_months") != 12
        or config.get("top_n") != 3
        or not isinstance(config.get("id"), str)
        or not config["id"]
        or not isinstance(universe, list)
        or len(universe) < 3
        or len(set(universe)) != len(universe)
        or any(not isinstance(n, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]*", n) for n in universe)
        or set(histories) != set(universe)
    ):
        raise ValueError("Require the complete configured 12-month/top-three universe")
    reference_config = config.get(
        "reference", {"ticker": "SPY", "label": "SPY · S&P 500", "cost_bps_per_side": 20}
    )
    if (
        not isinstance(reference_config, dict)
        or not re.fullmatch(r"[A-Z][A-Z0-9.-]*", str(reference_config.get("ticker", "")))
        or not isinstance(reference_config.get("label"), str)
        or not reference_config["label"]
        or isinstance(reference_config.get("cost_bps_per_side"), bool)
        or not isinstance(reference_config.get("cost_bps_per_side"), (float, int))
        or not 0 <= reference_config["cost_bps_per_side"] < 10000
    ):
        raise ValueError("Invalid reference configuration")
    comparison_config = config.get("comparison_references", [])
    if (
        not isinstance(comparison_config, list)
        or any(
            not isinstance(row, dict)
            or set(row) != {"ticker", "label"}
            or not re.fullmatch(r"[A-Z][A-Z0-9.-]*", str(row.get("ticker", "")))
            or not isinstance(row.get("label"), str)
            or not row["label"]
            or row["ticker"] == reference_config["ticker"]
            for row in comparison_config
        )
        or len({row["ticker"] for row in comparison_config}) != len(comparison_config)
    ):
        raise ValueError("Invalid comparison reference configuration")
    config = {"id": config["id"], "lookback_months": 12, "top_n": 3, "universe": sorted(universe)}
    month_start = now.date().replace(day=1)

    def view(panel, reference, *, monthly=False):
        result = build_current_momentum(panel, today=reference, month_end_anchor=monthly)
        if result["status"] == "available":
            identity = {n: panel[n][["date", "close"]].to_dict("records") for n in sorted(panel)}
            result.update(
                captured_at_utc=now.isoformat(),
                source_sha256=hashlib.sha256(
                    json.dumps(identity, sort_keys=True, default=str, allow_nan=False).encode()
                ).hexdigest(),
            )
        return result

    preview = view(histories, now.date())
    if preview["status"] == "available":
        monthly_panel = {}
        for ticker, frame in histories.items():
            dates = frame["date"].map(lambda value: pd.Timestamp(value).date())
            monthly_panel[ticker] = frame[dates < month_start].copy()
        monthly = view(monthly_panel, month_start, monthly=True)
    else:
        monthly = {
            "status": "unavailable",
            "reason": "Complete current price evidence is unavailable.",
        }
    result = {
        "session_calendar": build_session_calendar(now),
        "version": 1,
        "generated_at_utc": now.isoformat(),
        "cycle_month": str(month_start)[:7],
        "strategy": config,
        "ai_required": False,
        "promotion_ready": False,
        "preview": preview,
        "monthly": monthly,
    }
    if price_evidence is not None:
        evidence = validate_price_evidence(price_evidence, universe)
        for field in ("missing_sessions", "supplemented_sessions"):
            if any(date.fromisoformat(row["date"]) >= now.date() for row in evidence[field]):
                raise ValueError("Price evidence must refer to prior sessions")
        for row in evidence["supplemented_sessions"]:
            for ticker in row["tickers"]:
                dates = {str(pd.Timestamp(d).date()) for d in histories[ticker]["date"]}
                if row["date"] not in dates:
                    raise ValueError("Supplemented evidence is absent from the input panel")
        result["price_evidence"] = evidence
    result["context"] = build_momentum_context(
        histories,
        preview,
        monthly,
        today=now.date(),
        reference=reference,
        reference_config=reference_config,
        comparisons=comparisons,
        comparison_config=comparison_config,
    )
    if reference_evidence is not None:
        checked = validate_price_evidence(reference_evidence, [reference_config["ticker"]])
        for field in ("missing_sessions", "supplemented_sessions"):
            if any(date.fromisoformat(row["date"]) >= now.date() for row in checked[field]):
                raise ValueError("Reference evidence must refer to prior sessions")
        for row in checked["supplemented_sessions"]:
            if reference is None or not {"date", "close"} <= set(reference.columns):
                raise ValueError("Supplemented reference evidence is absent")
            dates = reference["date"].map(lambda d: str(pd.Timestamp(d).date()))
            values = reference.loc[dates == row["date"], "close"]
            if len(values) != 1 or not pd.notna(values.iloc[0]) or values.iloc[0] <= 0:
                raise ValueError("Supplemented reference evidence did not survive sanitization")
        result["reference_evidence"] = checked
    if comparison_evidence is not None:
        allowed = {r["ticker"] for r in comparison_config}
        if not isinstance(comparison_evidence, dict) or not set(comparison_evidence) <= allowed:
            raise ValueError("Unknown comparison evidence")
        result["comparison_evidence"] = {}
        for ticker, raw in comparison_evidence.items():
            checked = validate_price_evidence(raw, [ticker])
            for field in ("missing_sessions", "supplemented_sessions"):
                if any(date.fromisoformat(row["date"]) >= now.date() for row in checked[field]):
                    raise ValueError("Comparison evidence must refer to prior sessions")
            frame = (comparisons or {}).get(ticker)
            for row in checked["supplemented_sessions"]:
                if frame is None or not {"date", "close"} <= set(frame.columns):
                    raise ValueError("Supplemented comparison evidence is absent")
                values = frame.loc[
                    frame["date"].map(lambda d: str(pd.Timestamp(d).date())) == row["date"], "close"
                ]
                if len(values) != 1 or not pd.notna(values.iloc[0]) or values.iloc[0] <= 0:
                    raise ValueError("Supplemented comparison did not survive sanitization")
            result["comparison_evidence"][ticker] = checked

    def last_session(frame):
        if frame is None or frame.empty or not {"date", "close"} <= set(frame.columns):
            return None
        valid = frame[pd.to_numeric(frame["close"], errors="coerce").gt(0)]
        return max(str(pd.Timestamp(d).date()) for d in valid["date"]) if not valid.empty else None

    context = result["context"]
    context_comparisons = {r["ticker"]: r for r in context.get("comparisons", [])}
    result["data_sessions"] = {
        "stocks_date": preview.get("as_of"),
        "stocks_count": len(preview.get("ranking", [])),
        "references": [
            {
                "ticker": reference_config["ticker"],
                "date": last_session(reference),
                "complete": context.get("market", {}).get("status") == "available",
            }
        ]
        + [
            {
                "ticker": r["ticker"],
                "date": last_session((comparisons or {}).get(r["ticker"])),
                "complete": context_comparisons.get(r["ticker"], {}).get("status") == "available",
            }
            for r in comparison_config
        ],
    }
    return result
