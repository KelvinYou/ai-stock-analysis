"""Point-in-time evidence hygiene shared by live and replay fetchers.

Market evidence has two different clocks: when the event happened and when a
consumer could first have observed it. A replay must respect both. The
normaliser also keeps the live pipeline from presenting undated news as if it
were auditable evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from stock_analysis.models.market_data import FinancialStatements, MacroSnapshot

_PUBLISHED_KEYS = ("published_at", "publishedAt", "providerPublishTime", "pubDate")
_AVAILABLE_KEYS = (
    "available_as_of",
    "availableAt",
    "embargo_until",
    "embargoUntil",
)


def macro_snapshot_is_usable(
    snapshot: MacroSnapshot | None,
    as_of: date,
) -> bool:
    """Return whether a macro observation is both dated and knowable."""

    if snapshot is None:
        return False
    if snapshot.as_of_date > as_of or snapshot.available_as_of > as_of:
        return False
    return any(
        value is not None
        for value in (
            snapshot.fed_funds_rate,
            snapshot.inflation,
            snapshot.bnm_opr,
            snapshot.usd_myr,
        )
    ) or bool(snapshot.sector_factors or snapshot.geopolitical_risks)


def financials_have_evidence(financials: FinancialStatements | None) -> bool:
    """Return whether a statement object contains at least one measured value."""

    return financials is not None and any(
        value is not None
        for value in (
            financials.revenue,
            financials.net_income,
            financials.total_debt,
            financials.total_equity,
            financials.free_cash_flow,
            financials.gross_margin,
            financials.operating_margin,
            financials.net_margin,
            financials.diluted_eps,
            financials.shares_outstanding,
        )
    )


def financials_are_usable(
    financials: FinancialStatements | None,
    as_of: date,
) -> bool:
    """Return whether financial values could have been known on ``as_of``.

    A fiscal period ending after the cutoff is invalid even when a provider
    forgot to populate its filing date. When provenance is present, the filing
    date is the stronger availability clock.
    """

    if not financials_have_evidence(financials):
        return False
    assert financials is not None
    if financials.fiscal_period_end is not None and financials.fiscal_period_end > as_of:
        return False
    return not (
        financials.available_as_of is not None
        and financials.available_as_of > as_of
    )


def current_metadata_are_usable(data) -> bool:
    """An explicitly captured provider snapshot remains valid at its original cutoff."""
    return data.provider_capture == "current" or (
        data.provider_capture is None and data.fetched_at.date() >= date.today()
    )


def current_recommendations_are_usable(
    recommendations: Iterable[Mapping[str, Any]] | None,
    as_of: date,
    *,
    provider_capture: str | None = None,
) -> bool:
    """Current capture is evidence at its cutoff, even when a retry crosses midnight.

    Historical fetchers must omit provider-current tables. Legacy undated source
    packets retain the conservative current-day-only behavior.
    """
    return bool(recommendations) and (
        provider_capture == "current" or (provider_capture is None and as_of >= date.today())
    )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.fromtimestamp(float(text), tz=UTC)
            except (TypeError, ValueError, OverflowError, OSError):
                return None
    else:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_value(item: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if item.get(key) is not None:
            return item[key]
    return None


def normalize_news_item(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Convert common provider news shapes into a dated, auditable record."""
    if not isinstance(item, Mapping):
        return None
    content = item.get("content")
    nested = content if isinstance(content, Mapping) else {}

    title = item.get("title") or nested.get("title")
    if not title:
        return None

    published = _parse_datetime(
        _first_value(item, _PUBLISHED_KEYS)
        or _first_value(nested, _PUBLISHED_KEYS)
    )
    if published is None:
        return None

    provider = item.get("publisher") or nested.get("provider")
    if isinstance(provider, Mapping):
        provider = provider.get("displayName") or provider.get("name")

    link = item.get("link")
    if not link:
        for key in ("canonicalUrl", "clickThroughUrl"):
            candidate = nested.get(key)
            if isinstance(candidate, Mapping):
                link = candidate.get("url")
            elif candidate:
                link = candidate
            if link:
                break

    available = _first_value(item, _AVAILABLE_KEYS) or _first_value(nested, _AVAILABLE_KEYS)
    available_date = None
    if available is not None:
        available_dt = _parse_datetime(available)
        if available_dt is not None:
            available_date = available_dt.date()
        elif isinstance(available, str):
            try:
                available_date = date.fromisoformat(available.strip())
            except ValueError:
                return None

    normalized: dict[str, Any] = {
        "title": str(title),
        "link": str(link or ""),
        "publisher": str(provider or ""),
        "published_at": published.isoformat(),
    }
    if available_date is not None:
        normalized["available_as_of"] = available_date.isoformat()
    return normalized


def filter_point_in_time_news(
    headlines: Iterable[Mapping[str, Any]] | None,
    *,
    as_of: date,
    require_embargo: bool = False,
    max_age_days: int | None = None,
) -> list[dict[str, Any]]:
    """Keep only news knowable on ``as_of``.

    ``max_age_days`` bounds age at the analysis cutoff; None preserves raw archive
    compatibility. Signal consumers supply the configured recent window.
    ``require_embargo`` is for historical replay files. Live provider feeds
    can use publication time as their minimum provenance, while a replay must
    carry an explicit first-available/embargo date so publication time cannot
    be mistaken for data availability.
    """
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw in headlines or []:
        normalized = normalize_news_item(raw)
        if normalized is None:
            continue
        published_date = datetime.fromisoformat(normalized["published_at"]).date()
        if max_age_days is not None and (as_of - published_date).days > max_age_days:
            continue
        if published_date > as_of:
            continue

        available_as_of = normalized.get("available_as_of")
        if require_embargo and available_as_of is None:
            continue
        if available_as_of is not None and date.fromisoformat(available_as_of) > as_of:
            continue

        identity = (
            normalized["link"] or normalized["title"],
            normalized["published_at"],
        )
        if identity in seen:
            continue
        seen.add(identity)
        kept.append(normalized)
    return kept


def independent_sentiment_news(headlines, *, as_of, max_age_days):
    """Issuer earnings releases duplicate statement evidence, not independent sentiment."""
    news = filter_point_in_time_news(headlines, as_of=as_of, max_age_days=max_age_days)
    return [item for item in news if not (
        item["publisher"].casefold().endswith(" issuer") and
        any(term in item["title"].casefold() for term in ("financial results", "earnings results"))
    )]
