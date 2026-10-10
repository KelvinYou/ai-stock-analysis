"""Build source-neutral point-in-time replay evidence from public sources.

The replay loader deliberately accepts provider-neutral records, while this
module owns one reproducible public-source adapter:

* SEC EDGAR filings provide dated company events.  A filing's acceptance time
  is used for both publication and first-available time.
* SEC XBRL CompanyFacts preserves fiscal durations, units and filing vintages.
  Date-only filing availability is delayed by one day; later restatements are
  not visible before their own availability clock.
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
import math
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
    "diluted_eps": ("EarningsPerShareDiluted", "DilutedEarningsLossPerShare"),
    "shares_outstanding": ("CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"),
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
    for namespace in ("us-gaap", "ifrs-full", "dei"):
        namespace_facts = facts.get(namespace, {})
        if not isinstance(namespace_facts, dict):
            continue
        for priority, tag in enumerate(tags):
            fact = namespace_facts.get(tag)
            if not isinstance(fact, dict):
                continue
            units = fact.get("units", {})
            if not isinstance(units, dict):
                continue
            # Preserve every unit; snapshots choose one reporting currency
            # and require matching units/durations for all derived values.
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
                    if not math.isfinite(value) or filed < end:
                        continue
                    start = None
                    if row.get("start"):
                        try:
                            start = date.fromisoformat(str(row["start"]))
                        except ValueError:
                            continue
                    form = str(row.get("form") or "")
                    if form and form.removesuffix("/A") not in FUNDAMENTAL_FORMS:
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
                            "tag_priority": priority,
                            "accession": str(row.get("accn") or ""),
                            "namespace": namespace,
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
    period_start: date | None = None,
    exact_duration: bool = False,
    unit: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        entry
        for entry in entries
        if entry["end"] == period_end
        and entry["filed"] + timedelta(days=1) <= available_as_of
        and (not exact_duration or entry["start"] == period_start)
        and (unit is None or entry["unit"] == unit)
    ]
    if not candidates:
        return None
    def rank(entry):
        return (entry["filed"], -_fact_duration_rank(entry), -entry.get("tag_priority", 0))
    selected = max(candidates, key=rank)
    tied = [entry for entry in candidates if rank(entry) == rank(selected)]
    if len({entry["value"] for entry in tied}) > 1:
        raise ValueError(f"Conflicting SEC facts for {period_end} at {selected['filed']}")
    return selected


def _fundamental_snapshot(
    payload: dict[str, Any],
    *,
    available_as_of: date,
    period_end: date | None = None,
    period_start: date | None = None,
    currency: str | None = None,
    grouped: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any] | None:
    grouped = grouped or {name: _fact_entries(payload, tags) for name, tags in _FACT_TAGS.items()}
    anchors = [e for e in grouped["revenue"] + grouped["net_income"]
               if e["filed"] + timedelta(days=1) <= available_as_of
               and e["end"] <= available_as_of and e["start"] is not None
               and e["start"] <= e["end"]
               and "/" not in e["unit"] and e["unit"] != "shares"]
    if period_end is not None:
        anchors = [e for e in anchors if e["end"] == period_end
                   and e["start"] == period_start and e["unit"] == currency]
    if not anchors:
        return None
    # Preserve one issuer currency; never blend two unit systems in a ratio.
    anchor = max(anchors, key=lambda e: (e["end"], -_fact_duration_rank(e),
                                        e["unit"] == "USD", e["filed"]))
    period_end, period_start, currency = anchor["end"], anchor["start"], anchor["unit"]
    balance_fields = {"total_debt", "total_equity", "shares_outstanding"}
    selected: dict[str, dict[str, Any]] = {}
    for name, entries in grouped.items():
        unit = "shares" if name == "shares_outstanding" else (
            f"{currency}/shares" if name == "diluted_eps" else currency
        )
        fact = _fact_for_period(entries, period_end=period_end, available_as_of=available_as_of,
                                period_start=None if name in balance_fields else period_start,
                                exact_duration=True, unit=unit)
        if fact is not None:
            selected[name] = fact

    def value(name: str) -> float | None:
        fact = selected.get(name)
        return fact["value"] if fact else None

    revenue, net_income = value("revenue"), value("net_income")
    debt_entries = grouped["total_debt"]
    direct = _fact_for_period(
        [e for e in debt_entries if e["tag"] in {"LongTermDebtAndFinanceLeaseObligations", "Borrowings"}],
        period_end=period_end, available_as_of=available_as_of,
        period_start=None, exact_duration=True, unit=currency,
    )
    total_debt = direct["value"] if direct else None
    debt_parts = []
    if direct is None:
        for current, noncurrent in (
            ("LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent"),
            ("LongTermDebtCurrent", "LongTermDebtNoncurrent"),
        ):
            pair = [_fact_for_period([e for e in debt_entries if e["tag"] == tag],
                                    period_end=period_end, available_as_of=available_as_of,
                                    period_start=None, exact_duration=True, unit=currency)
                    for tag in (current, noncurrent)]
            if all(p is not None for p in pair):
                # This is a matched long-term debt subtotal, not evidence that
                # every short-term borrowing category has also been reported.
                total_debt = sum(p["value"] for p in pair)
                debt_parts = pair
                break
    selected.pop("total_debt", None)
    if direct is not None:
        selected["total_debt"] = direct
    for index, part in enumerate(debt_parts):
        selected[f"debt_component_{index}"] = part
    ocf, capex = value("operating_cash_flow"), value("capital_expenditure")
    free_cash_flow = None
    if ocf is not None and capex is not None:
        free_cash_flow = ocf + capex if capex < 0 else ocf - capex
    days = (period_end - period_start).days + 1
    kind = "quarter" if 60 <= days <= 121 else "annual" if 300 <= days <= 400 else "other"
    provenance = {name: {"tag": e["tag"], "namespace": e["namespace"],
                         "unit": e["unit"], "start": str(e["start"]) if e["start"] else None,
                         "end": e["end"].isoformat(), "filed": e["filed"].isoformat(),
                         "accession": e["accession"]} for name, e in selected.items()}
    snapshot = {
        "fiscal_period_start": period_start.isoformat(),
        "fiscal_period_end": period_end.isoformat(),
        "available_as_of": max(e["filed"] + timedelta(days=1) for e in selected.values()).isoformat(),
        "availability_source": "sec_companyfacts", "currency": currency, "period_kind": kind,
        "revenue": revenue, "net_income": net_income, "total_debt": total_debt,
        "total_equity": value("total_equity"), "free_cash_flow": free_cash_flow,
        "gross_margin": value("gross_profit") / revenue if value("gross_profit") is not None and revenue else None,
        "operating_margin": value("operating_income") / revenue if value("operating_income") is not None and revenue else None,
        "net_margin": net_income / revenue if net_income is not None and revenue else None,
        "diluted_eps": value("diluted_eps"), "shares_outstanding": value("shares_outstanding"),
        "share_basis": None, "fact_provenance": provenance,
        "units": sorted({e["unit"] for e in selected.values()}),
        "debt_scope": "reported_total" if direct and direct["tag"] == "Borrowings" else "matched_long_term_subtotal" if direct or debt_parts else "unavailable",
    }
    # Finite source observations can still overflow during derived arithmetic.
    # Preserve their provenance, but do not emit unusable derived values.
    for key, value in snapshot.items():
        if isinstance(value, float) and not math.isfinite(value):
            snapshot[key] = None
    if snapshot["shares_outstanding"] is not None and snapshot["shares_outstanding"] <= 0:
        snapshot["shares_outstanding"] = None
    return snapshot


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
        facts = {name: _fact_entries(payload, tags) for name, tags in _FACT_TAGS.items()}
        available_dates = {entry["filed"] + timedelta(days=1)
                           for entries in facts.values() for entry in entries
                           if lower <= entry["filed"] + timedelta(days=1) <= end}
        # A new filing can carry comparative facts for older periods. Preserve
        # those periods and vintages instead of only the newest fiscal end.
        seen: set[str] = set()
        for available_date in sorted(available_dates):
            anchors = facts["revenue"] + facts["net_income"]
            periods = {(e["start"], e["end"], e["unit"]) for e in anchors
                       if e["start"] is not None and e["start"] <= e["end"]
                       and e["filed"] + timedelta(days=1) <= available_date}
            for period_start, period_end, currency in sorted(periods):
                snapshot = _fundamental_snapshot(
                    payload, available_as_of=available_date, period_start=period_start,
                    period_end=period_end, currency=currency, grouped=facts,
                )
                if snapshot is not None:
                    snapshot["ticker"] = ticker
                    identity = json.dumps(snapshot, sort_keys=True)
                    if identity not in seen:
                        seen.add(identity)
                        grouped[ticker].append(snapshot)
        grouped[ticker].sort(
            key=lambda item: (item["available_as_of"], item["fiscal_period_end"])
        )

    return grouped, {
        "name": "SEC XBRL CompanyFacts",
        "url": SEC_COMPANY_FACTS_URL,
        "availability_rule": "fact filed date + one calendar day (date-only clock)",
        "coverage_note": (
            "Point-in-time financial facts from SEC filings; later restatements "
            "are excluded until the day after their filed date. All fiscal "
            "durations and known revisions are retained; share basis remains "
            "unverified and valuation requires a separate dated price replay."
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
