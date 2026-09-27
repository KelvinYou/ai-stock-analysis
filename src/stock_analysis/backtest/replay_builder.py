"""Build source-neutral point-in-time replay evidence from public sources.

The replay loader deliberately accepts provider-neutral records, while this
module owns one reproducible public-source adapter:

* SEC EDGAR filings provide dated company events.  A filing's acceptance time
  is used for both publication and first-available time.
* SEC XBRL CompanyFacts provides point-in-time financial snapshots keyed by
  each fact's filed date; later restatements are not visible before filing.
* FRED's daily effective federal funds rate (DFF) provides a dated macro
  observation.  Availability is conservatively delayed by one calendar day;
  the builder never treats the observation date as proof of same-day access.

SEC filings are not a complete news feed.  They are a primary-source event
  layer that is safer than injecting today's provider-current headlines into a
  historical packet.  The output manifest records that limitation explicitly.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FRED_DFF_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF"
DEFAULT_FORMS = frozenset({"6-K", "8-K", "10-K", "10-Q", "20-F", "40-F"})
FUNDAMENTAL_FORMS = frozenset({"6-K", "10-K", "10-Q", "20-F", "40-F"})

_FACT_TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "Revenue",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "total_debt": (
        "LongTermDebtAndFinanceLeaseObligations",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "ShortTermBorrowings",
        "DebtCurrent",
        "Borrowings",
    ),
    "total_equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "Equity",
    ),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "CashFlowsFromUsedInOperatingActivities",
    ),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
    ),
}


def _fetch_bytes(url: str, *, user_agent: str) -> bytes:
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Unable to fetch replay source {url}: {exc}") from exc


def _fetch_json(url: str, *, user_agent: str) -> Any:
    try:
        return json.loads(_fetch_bytes(url, user_agent=user_agent))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Replay source returned invalid JSON: {url}") from exc


def _parse_acceptance(value: str | None, fallback: date) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    return datetime.combine(fallback, datetime.min.time(), tzinfo=UTC)


def _ticker_ciks(
    tickers: list[str],
    *,
    user_agent: str,
) -> dict[str, tuple[int, str]]:
    payload = _fetch_json(SEC_TICKERS_URL, user_agent=user_agent)
    wanted = {ticker.upper() for ticker in tickers}
    found: dict[str, tuple[int, str]] = {}
    for item in payload.values() if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker", "")).upper()
        if ticker in wanted:
            found[ticker] = (int(item["cik_str"]), str(item.get("title", ticker)))
    missing = sorted(wanted - found.keys())
    if missing:
        raise ValueError(f"SEC company ticker map has no CIK for: {', '.join(missing)}")
    return found


def _recent_filings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    keys = (
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
        "primaryDocDescription",
    )
    length = max((len(recent.get(key, [])) for key in keys), default=0)
    return [
        {key: recent.get(key, [None] * length)[index] for key in keys}
        for index in range(length)
    ]


def _filing_record(
    ticker: str,
    cik: int,
    filing: dict[str, Any],
) -> dict[str, str] | None:
    filing_date_raw = filing.get("filingDate")
    if not filing_date_raw:
        return None
    try:
        filing_date = date.fromisoformat(str(filing_date_raw))
    except ValueError:
        return None
    accepted = _parse_acceptance(filing.get("acceptanceDateTime"), filing_date)
    form = str(filing.get("form") or "filing")
    accession = str(filing.get("accessionNumber") or "")
    document = str(filing.get("primaryDocument") or "")
    if not accession or not document:
        return None
    accession_path = accession.replace("-", "")
    link = (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_path}/{document}"
    )
    description = str(filing.get("primaryDocDescription") or document)
    return {
        "ticker": ticker,
        "title": f"SEC {form} filing: {description}",
        "link": link,
        "publisher": "SEC EDGAR",
        "published_at": accepted.isoformat().replace("+00:00", "Z"),
        "available_as_of": accepted.date().isoformat(),
        "source_id": accession,
    }


def _fact_entries(payload: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    """Extract dated SEC XBRL fact observations for the requested tags.

    CompanyFacts contains both annual and year-to-date facts.  We keep the
    source metadata on every row and select a period only after applying the
    point-in-time filing cutoff.  This prevents a current restatement from
    silently replacing the value that was knowable during an old trial.
    """

    facts = payload.get("facts", {})
    entries: list[dict[str, Any]] = []
    for namespace in ("us-gaap", "ifrs-full"):
        namespace_facts = facts.get(namespace, {})
        if not isinstance(namespace_facts, dict):
            continue
        for tag in tags:
            fact = namespace_facts.get(tag)
            if not isinstance(fact, dict):
                continue
            units = fact.get("units", {})
            if not isinstance(units, dict):
                continue
            # Monetary values are normally USD for the selected US issuers;
            # accepting the first unit also keeps IFRS issuers replayable. The
            # source/unit remain visible in the generated manifest and packet.
            for unit, rows in units.items():
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    try:
                        value = float(row["val"])
                        end = date.fromisoformat(str(row["end"]))
                        filed = date.fromisoformat(str(row["filed"]))
                    except (KeyError, TypeError, ValueError):
                        continue
                    if not end or not filed:
                        continue
                    start = None
                    if row.get("start"):
                        try:
                            start = date.fromisoformat(str(row["start"]))
                        except ValueError:
                            continue
                    form = str(row.get("form") or "")
                    if form and form not in FUNDAMENTAL_FORMS:
                        continue
                    entries.append(
                        {
                            "value": value,
                            "end": end,
                            "start": start,
                            "filed": filed,
                            "form": form,
                            "unit": str(unit),
                            "tag": tag,
                        }
                    )
    return entries


def _fact_duration_rank(entry: dict[str, Any]) -> int:
    """Prefer a single-quarter fact over a YTD or annual duplicate."""

    start = entry.get("start")
    end = entry["end"]
    if start is None:
        return 2
    days = (end - start).days
    if 60 <= days <= 120:
        return 0
    if 300 <= days <= 400:
        return 1
    return 2


def _fact_for_period(
    entries: list[dict[str, Any]],
    *,
    period_end: date,
    available_as_of: date,
) -> dict[str, Any] | None:
    candidates = [
        entry
        for entry in entries
        if entry["end"] == period_end and entry["filed"] <= available_as_of
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda entry: (
            entry["filed"],
            -_fact_duration_rank(entry),
            entry["tag"],
        ),
    )


def _fundamental_snapshot(
    payload: dict[str, Any],
    *,
    available_as_of: date,
) -> dict[str, Any] | None:
    grouped = {
        name: _fact_entries(payload, tags)
        for name, tags in _FACT_TAGS.items()
    }
    anchor_entries = grouped["revenue"] + grouped["net_income"]
    period_ends = {
        entry["end"]
        for entry in anchor_entries
        if entry["filed"] <= available_as_of and entry["end"] <= available_as_of
    }
    if not period_ends:
        return None
    period_end = max(period_ends)

    selected: dict[str, dict[str, Any]] = {}
    for name, entries in grouped.items():
        fact = _fact_for_period(
            entries,
            period_end=period_end,
            available_as_of=available_as_of,
        )
        if fact is not None:
            selected[name] = fact

    def value(name: str) -> float | None:
        fact = selected.get(name)
        return fact["value"] if fact else None

    revenue = value("revenue")
    net_income = value("net_income")
    gross_profit = value("gross_profit")
    operating_income = value("operating_income")

    # CompanyFacts frequently exposes debt as current/non-current components
    # rather than a total. Prefer a direct total; otherwise sum the components
    # that share the selected period and filing cutoff.
    debt_fact = selected.get("total_debt")
    total_debt = debt_fact["value"] if debt_fact else None

    operating_cash_flow = value("operating_cash_flow")
    capital_expenditure = value("capital_expenditure")
    free_cash_flow = None
    if operating_cash_flow is not None and capital_expenditure is not None:
        # SEC cash outflows are usually negative; tolerate positive encodings.
        free_cash_flow = (
            operating_cash_flow + capital_expenditure
            if capital_expenditure < 0
            else operating_cash_flow - capital_expenditure
        )

    numeric_values = (
        revenue,
        net_income,
        total_debt,
        value("total_equity"),
        free_cash_flow,
        gross_profit,
        operating_income,
    )
    if not any(item is not None for item in numeric_values):
        return None

    return {
        "fiscal_period_end": period_end.isoformat(),
        "available_as_of": available_as_of.isoformat(),
        "availability_source": "sec_companyfacts",
        "revenue": revenue,
        "net_income": net_income,
        "total_debt": total_debt,
        "total_equity": value("total_equity"),
        "free_cash_flow": free_cash_flow,
        "gross_margin": gross_profit / revenue if gross_profit is not None and revenue else None,
        "operating_margin": (
            operating_income / revenue if operating_income is not None and revenue else None
        ),
        "net_margin": net_income / revenue if net_income is not None and revenue else None,
        "units": sorted({fact["unit"] for fact in selected.values()}),
    }


def build_sec_fundamentals(
    tickers: list[str],
    *,
    start: date,
    end: date,
    user_agent: str,
    lookback_days: int = 365,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Build point-in-time financial snapshots from SEC CompanyFacts."""

    ciks = _ticker_ciks(tickers, user_agent=user_agent)
    lower = start - timedelta(days=lookback_days)
    grouped: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in ciks}
    for ticker, (cik, _title) in ciks.items():
        payload = _fetch_json(
            SEC_COMPANY_FACTS_URL.format(cik=cik),
            user_agent=user_agent,
        )
        all_filed_dates = {
            entry["filed"]
            for tags in _FACT_TAGS.values()
            for entry in _fact_entries(payload, tags)
            if lower <= entry["filed"] <= end
        }
        for filed_date in sorted(all_filed_dates):
            snapshot = _fundamental_snapshot(
                payload,
                available_as_of=filed_date,
            )
            if snapshot is not None:
                snapshot["ticker"] = ticker
                grouped[ticker].append(snapshot)
        grouped[ticker].sort(
            key=lambda item: (item["available_as_of"], item["fiscal_period_end"])
        )

    return grouped, {
        "name": "SEC XBRL CompanyFacts",
        "url": SEC_COMPANY_FACTS_URL,
        "availability_rule": "fact filed date",
        "coverage_note": (
            "Point-in-time financial facts from SEC filings; later restatements "
            "are excluded until their filed date."
        ),
    }


def build_sec_news(
    tickers: list[str],
    *,
    start: date,
    end: date,
    user_agent: str,
    forms: frozenset[str] = DEFAULT_FORMS,
    lookback_days: int = 365,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    """Return SEC filing events grouped by ticker plus source metadata."""

    ciks = _ticker_ciks(tickers, user_agent=user_agent)
    lower = start - timedelta(days=lookback_days)
    grouped: dict[str, list[dict[str, str]]] = {ticker: [] for ticker in ciks}
    for ticker, (cik, _title) in ciks.items():
        payload = _fetch_json(
            SEC_SUBMISSIONS_URL.format(cik=cik),
            user_agent=user_agent,
        )
        for filing in _recent_filings(payload):
            form = str(filing.get("form") or "")
            filing_date_raw = filing.get("filingDate")
            try:
                filing_date = date.fromisoformat(str(filing_date_raw))
            except (TypeError, ValueError):
                continue
            if form not in forms or not lower <= filing_date <= end:
                continue
            record = _filing_record(ticker, cik, filing)
            if record is not None:
                grouped[ticker].append(record)
        grouped[ticker].sort(key=lambda item: (item["published_at"], item["source_id"]))

    return grouped, {
        "name": "SEC EDGAR filing events",
        "kind": "primary_event_layer",
        "url": SEC_TICKERS_URL,
        "submissions_url": SEC_SUBMISSIONS_URL,
        "company_titles": {ticker: title for ticker, (_, title) in ciks.items()},
        "forms": sorted(forms),
        "availability_rule": "SEC acceptanceDateTime date",
        "coverage_note": "Primary filing events, not a complete provider news feed.",
    }


def build_fred_macro(
    *,
    start: date,
    end: date,
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build conservative daily Fed funds snapshots from FRED's DFF series."""

    text = _fetch_bytes(FRED_DFF_URL, user_agent=user_agent).decode("utf-8")
    records: list[dict[str, Any]] = []
    lower = start - timedelta(days=7)
    for row in csv.DictReader(text.splitlines()):
        try:
            observed = date.fromisoformat(str(row["observation_date"]))
            value = float(row["DFF"])
        except (KeyError, TypeError, ValueError):
            continue
        if not lower <= observed <= end:
            continue
        records.append(
            {
                "as_of_date": observed.isoformat(),
                "available_as_of": (observed + timedelta(days=1)).isoformat(),
                "source": "FRED:DFF",
                "fed_funds_rate": value,
            }
        )
    records.sort(key=lambda item: item["as_of_date"])
    if not records:
        raise ValueError("FRED DFF returned no observations in the requested range")
    return records, {
        "name": "FRED daily effective federal funds rate",
        "url": FRED_DFF_URL,
        "series": "DFF",
        "availability_rule": "observation date + 1 calendar day (conservative)",
        "coverage_note": "Fed funds only; inflation, FX, and sector/geopolitical fields remain unavailable.",
    }


def build_replay_directory(
    *,
    tickers: list[str],
    start: date,
    end: date,
    output_dir: Path,
    user_agent: str,
    lookback_days: int = 365,
) -> dict[str, Any]:
    """Build a replay directory and return its manifest."""

    if end < start:
        raise ValueError("end must be on or after start")
    if not tickers:
        raise ValueError("tickers must not be empty")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty replay directory: {output_dir}")

    news, sec_source = build_sec_news(
        tickers,
        start=start,
        end=end,
        user_agent=user_agent,
        lookback_days=lookback_days,
    )
    fundamentals, fundamentals_source = build_sec_fundamentals(
        tickers,
        start=start,
        end=end,
        user_agent=user_agent,
        lookback_days=lookback_days,
    )
    macro, fred_source = build_fred_macro(start=start, end=end, user_agent=user_agent)

    news_dir = output_dir / "news"
    news_dir.mkdir(parents=True, exist_ok=True)
    for ticker, records in news.items():
        path = news_dir / f"{ticker}.jsonl"
        path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    fundamentals_dir = output_dir / "fundamentals"
    fundamentals_dir.mkdir(parents=True, exist_ok=True)
    for ticker, records in fundamentals.items():
        path = fundamentals_dir / f"{ticker}.jsonl"
        path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
    (output_dir / "macro.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in macro)
    )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "tickers": [ticker.upper() for ticker in tickers],
        "news": {
            "records": sum(len(records) for records in news.values()),
            "by_ticker": {ticker: len(records) for ticker, records in news.items()},
            "source": sec_source,
        },
        "fundamentals": {
            "records": sum(len(records) for records in fundamentals.values()),
            "by_ticker": {ticker: len(records) for ticker, records in fundamentals.items()},
            "source": fundamentals_source,
        },
        "macro": {"records": len(macro), "source": fred_source},
        "limitations": [
            "SEC filings are event evidence, not a complete historical news feed.",
            "FRED replay covers only fed_funds_rate; other macro fields are unavailable.",
            "Ticker universe membership and execution costs are not established by this builder.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def cli() -> None:
    parser = argparse.ArgumentParser(description="Build point-in-time SEC/FRED replay evidence.")
    parser.add_argument("--tickers", required=True, help="Comma-separated US tickers")
    parser.add_argument("--start", required=True, help="First as-of date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Last as-of date YYYY-MM-DD")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--user-agent",
        required=True,
        help="Identifying SEC user-agent, including a contact address",
    )
    parser.add_argument("--news-lookback-days", type=int, default=365)
    args = parser.parse_args()
    tickers = [item.strip().upper() for item in args.tickers.split(",") if item.strip()]
    manifest = build_replay_directory(
        tickers=tickers,
        start=date.fromisoformat(args.start),
        end=date.fromisoformat(args.end),
        output_dir=args.output,
        user_agent=args.user_agent,
        lookback_days=args.news_lookback_days,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    cli()
