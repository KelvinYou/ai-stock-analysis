"""Fetch 10-K / 10-Q primary documents from SEC EDGAR and reduce them to text.

Deterministic, no LLM. Reuses the SEC request helpers from the replay builder
so there is one place that knows how EDGAR wants to be called.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from lxml import html as lxml_html

from stock_analysis.backtest.replay_builder import (
    SEC_SUBMISSIONS_URL,
    _fetch_bytes,
    _fetch_json,
    _recent_filings,
    _ticker_ciks,
)

ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
SUPPORTED_FORMS = ("10-K", "10-Q")


@dataclass(frozen=True)
class FilingRef:
    ticker: str
    cik: int
    form: str
    filing_date: date
    accession: str
    document: str

    @property
    def url(self) -> str:
        return ARCHIVE_URL.format(
            cik=self.cik, accession=self.accession.replace("-", ""), document=self.document
        )


def list_filings(
    ticker: str,
    *,
    user_agent: str,
    forms: tuple[str, ...] = SUPPORTED_FORMS,
    limit: int = 6,
) -> list[FilingRef]:
    """Newest-first original 10-K/10-Q filings. Amendments (10-K/A) are skipped:
    they restate fragments, and indexing them beside the original would let a
    partial document outrank the complete one."""
    cik, _name = _ticker_ciks([ticker], user_agent=user_agent)[ticker.upper()]
    payload = _fetch_json(SEC_SUBMISSIONS_URL.format(cik=cik), user_agent=user_agent)
    refs: list[FilingRef] = []
    for item in _recent_filings(payload):
        form = str(item.get("form") or "")
        if form not in forms or not item.get("accessionNumber") or not item.get("primaryDocument"):
            continue
        try:
            filed = date.fromisoformat(str(item["filingDate"]))
        except (KeyError, ValueError):
            continue
        refs.append(
            FilingRef(
                ticker=ticker.upper(),
                cik=cik,
                form=form,
                filing_date=filed,
                accession=str(item["accessionNumber"]),
                document=str(item["primaryDocument"]),
            )
        )
    refs.sort(key=lambda ref: ref.filing_date, reverse=True)
    return refs[:limit]


_BLOCK_TAGS = ("p", "div", "tr", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table")


def html_to_text(raw: bytes) -> str:
    """Visible text with one line per block element.

    Inline-XBRL filings carry a hidden ``ix:header`` with thousands of tagged
    facts; it is dropped with every other ``display:none`` node so the index
    holds what a reader of the filing sees, not the machine-readable shadow.
    """
    tree = lxml_html.fromstring(raw)
    hidden = "//script|//style|//*[local-name()='ix:header' or local-name()='header']"
    for node in tree.xpath(hidden):
        node.drop_tree()
    for node in tree.xpath("//*[@style]"):
        style = node.get("style", "").replace(" ", "").lower()
        if "display:none" in style:
            node.drop_tree()
    for node in tree.iter(*_BLOCK_TAGS):
        node.tail = "\n" + (node.tail or "")
    text = tree.text_content().replace("\xa0", " ")
    lines = (re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def fetch_filing_text(ref: FilingRef, *, user_agent: str) -> str:
    return html_to_text(_fetch_bytes(ref.url, user_agent=user_agent))
