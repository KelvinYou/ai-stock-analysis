"""Split filing text into labelled sections, then into retrieval chunks.

Section labels are form-aware: "Item 2" is Properties in a 10-K but MD&A in a
10-Q, and a 10-Q's Part II restarts the item numbering. A chunk that carries
the wrong section label would make the agent cite the wrong part of the filing,
so the label is derived from (form, part, item) rather than the item alone.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

TEN_K_ITEMS = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Common Equity",
    "6": "Reserved",
    "7": "MD&A",
    "7A": "Market Risk",
    "8": "Financial Statements",
    "9": "Changes in Accountants",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Foreign Jurisdiction Inspections",
    "10": "Directors and Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Relationships and Transactions",
    "14": "Accountant Fees",
    # Official title. Several filers (NVDA among them) put the audited statements
    # and notes here rather than under Item 8, so "Exhibits" alone would make the
    # agent cite revenue-recognition text as if it came from an exhibit list.
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}
TEN_Q_ITEMS = {
    ("I", "1"): "Financial Statements",
    ("I", "2"): "MD&A",
    ("I", "3"): "Market Risk",
    ("I", "4"): "Controls and Procedures",
    ("II", "1"): "Legal Proceedings",
    ("II", "1A"): "Risk Factors",
    ("II", "2"): "Unregistered Sales and Repurchases",
    ("II", "3"): "Defaults",
    ("II", "4"): "Mine Safety Disclosures",
    ("II", "5"): "Other Information",
    ("II", "6"): "Exhibits",
}

_PART = re.compile(r"^part\s+(i{1,2}|iv|iii)\b", re.IGNORECASE)
_ITEM = re.compile(r"^item\s+(\d{1,2}[a-c]?)\s*[.:\-—–]?", re.IGNORECASE)
# A table-of-contents entry is a heading line followed almost immediately by the
# next heading; anything shorter than this is treated as navigation, not prose.
MIN_SECTION_CHARS = 400


@dataclass(frozen=True)
class Section:
    label: str
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    ticker: str
    form: str
    filing_date: str  # ISO date; kept as text so the JSONL round-trips exactly
    accession: str
    section: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def section_label(form: str, part: str | None, item: str) -> str:
    item = item.upper()
    if form == "10-Q":
        return TEN_Q_ITEMS.get((part or "I", item), f"Item {item}")
    return TEN_K_ITEMS.get(item, f"Item {item}")


def split_sections(text: str, form: str) -> list[Section]:
    sections: list[Section] = []
    part: str | None = None
    label = "Cover"
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if len(body) >= MIN_SECTION_CHARS:
            sections.append(Section(label=label, text=body))

    for line in text.splitlines():
        part_match = _PART.match(line)
        if part_match:
            part = part_match.group(1).upper()
            continue
        item_match = _ITEM.match(line)
        if item_match:
            flush()
            buffer = []
            label = section_label(form, part, item_match.group(1))
            rest = line[item_match.end() :].strip()
            if rest:
                buffer.append(rest)
            continue
        buffer.append(line)
    flush()
    return sections


def pack_paragraphs(text: str, max_chars: int = 1500) -> list[str]:
    """Greedy paragraph packing; a paragraph longer than the budget is cut on
    sentence boundaries, and a single over-long sentence is hard-cut."""
    pieces: list[str] = []
    for paragraph in text.split("\n"):
        if len(paragraph) <= max_chars:
            pieces.append(paragraph)
            continue
        sentence_buf = ""
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
            while len(sentence) > max_chars:
                pieces.append(sentence[:max_chars])
                sentence = sentence[max_chars:]
            if len(sentence_buf) + len(sentence) + 1 > max_chars and sentence_buf:
                pieces.append(sentence_buf)
                sentence_buf = ""
            sentence_buf = f"{sentence_buf} {sentence}".strip()
        if sentence_buf:
            pieces.append(sentence_buf)

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) + 1 > max_chars:
            chunks.append(current)
            current = ""
        current = f"{current}\n{piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def chunk_filing(
    text: str,
    *,
    ticker: str,
    form: str,
    filing_date: str,
    accession: str,
    max_chars: int = 1500,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in split_sections(text, form):
        for body in pack_paragraphs(section.text, max_chars=max_chars):
            chunks.append(
                Chunk(
                    chunk_id=f"{accession}:{len(chunks)}",
                    ticker=ticker,
                    form=form,
                    filing_date=filing_date,
                    accession=accession,
                    section=section.label,
                    text=body,
                )
            )
    return chunks
