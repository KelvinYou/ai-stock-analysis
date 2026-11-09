from datetime import date, datetime

import numpy as np
import pytest

from stock_analysis.agents.fundamentals import FundamentalsAgent
from stock_analysis.config import Settings
from stock_analysis.filings.bm25 import BM25
from stock_analysis.filings.chunking import Chunk, chunk_filing, pack_paragraphs, split_sections
from stock_analysis.filings.edgar import html_to_text
from stock_analysis.filings.index import FilingIndex, index_dir, rrf_fuse
from stock_analysis.filings.tool import search_filings_payload
from stock_analysis.models.market_data import Market, TickerData, TickerInfo

PROSE = " ".join(["The company describes its operations in detail."] * 12)


def chunk(cid, filed, text, section="Risk Factors", form="10-K"):
    return Chunk(cid, "TEST", form, filed, f"acc-{cid}", section, text)


class FakeEmbedder:
    """Maps a tiny synonym vocabulary onto shared axes, so 'lawsuit' and
    'litigation' are close while sharing no token — the case BM25 misses."""

    AXES = {
        "litigation": 0, "lawsuit": 0, "court": 0,
        "liquidity": 1, "cash": 1,
        "supply": 2, "suppliers": 2,
    }

    def __init__(self, model_name="fake-model"):
        self.model_name = model_name

    def _vec(self, text):
        vec = np.zeros(4, dtype=np.float32)
        for word in text.lower().split():
            vec[self.AXES.get(word.strip(".,"), 3)] += 1
        return vec / (np.linalg.norm(vec) or 1)

    def embed_passages(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def embed_query(self, text):
        return self._vec(text)


# --- chunking -----------------------------------------------------------------


def test_10k_sections_skip_table_of_contents_and_label_items():
    text = "\n".join([
        "Item 1. Business", "Item 1A. Risk Factors", "Item 7. MD&A",  # table of contents
        "Item 1. Business", PROSE,
        "Item 1A. Risk Factors", PROSE,
        "Item 7. Management's Discussion", PROSE,
    ])
    labels = [s.label for s in split_sections(text, "10-K")]
    assert labels == ["Business", "Risk Factors", "MD&A"]


def test_10q_part_ii_restarts_item_numbering():
    text = "\n".join([
        "PART I", "Item 2. Management's Discussion", PROSE,
        "PART II", "Item 1. Legal Proceedings", PROSE, "Item 1A. Risk Factors", PROSE,
    ])
    labels = [s.label for s in split_sections(text, "10-Q")]
    assert labels == ["MD&A", "Legal Proceedings", "Risk Factors"]


def test_pack_paragraphs_never_exceeds_budget():
    text = "\n".join(["short para."] * 50 + ["x" * 4000, "Long sentence. " * 300])
    assert all(len(piece) <= 500 for piece in pack_paragraphs(text, max_chars=500))


def test_chunk_ids_are_unique_and_carry_provenance():
    text = "\n".join(["Item 1A. Risk Factors", PROSE, PROSE])
    chunks = chunk_filing(text, ticker="TEST", form="10-K", filing_date="2025-01-30",
                          accession="0001", max_chars=300)
    assert len({c.chunk_id for c in chunks}) == len(chunks) > 1
    assert {c.section for c in chunks} == {"Risk Factors"}


def test_html_to_text_drops_hidden_xbrl_and_scripts():
    raw = (b"<html><body><div style='display: none'><ix:header>FACT 123</ix:header></div>"
           b"<script>var x=1;</script><p>Item 1A. Risk Factors</p><p>Visible text.</p></body></html>")
    text = html_to_text(raw)
    assert "FACT 123" not in text and "var x" not in text
    assert text.splitlines() == ["Item 1A. Risk Factors", "Visible text."]


# --- retrieval ----------------------------------------------------------------


def corpus():
    return [
        chunk("old", "2023-01-01", "litigation risk from old years"),
        chunk("a", "2025-01-30", "We face litigation in several court cases."),
        chunk("b", "2025-04-30", "Liquidity: cash and equivalents were adequate.", "MD&A", "10-Q"),
        chunk("c", "2025-07-30", "We depend on a small number of suppliers.", form="10-Q"),
        chunk("future", "2025-10-30", "A new lawsuit litigation filed after the cutoff."),
    ]


def test_filing_on_or_after_analysis_date_is_invisible():
    index = FilingIndex(corpus())
    result = index.search("litigation", as_of=date(2025, 10, 30), mode="bm25")
    ids = [hit.chunk.chunk_id for hit in result.hits]
    assert "future" not in ids and "a" in ids
    assert result.hidden_future_chunks == 1


def test_max_age_drops_stale_filings():
    result = FilingIndex(corpus()).search("litigation", as_of=date(2025, 8, 1), mode="bm25")
    assert "old" not in [hit.chunk.chunk_id for hit in result.hits]


def test_future_documents_do_not_change_bm25_scores():
    docs = [c.text for c in corpus()]
    with_future = BM25(docs).scores("litigation court", [1, 2, 3])
    without_future = BM25(docs[:4]).scores("litigation court", [1, 2, 3])
    assert with_future == pytest.approx(without_future)


def test_rrf_rewards_agreement_between_retrievers():
    fused = rrf_fuse({"bm25": [1, 2, 3], "dense": [2, 4]})
    assert fused[0][0] == 2 and fused[0][2] == ("bm25", "dense")


def test_hybrid_finds_synonym_match_that_bm25_misses():
    index = FilingIndex.build(corpus(), FakeEmbedder())
    as_of = date(2025, 8, 1)
    lexical = index.search("lawsuit", as_of=as_of, mode="bm25")
    assert lexical.hits == []
    hybrid = index.search("lawsuit", as_of=as_of, embedder=FakeEmbedder())
    assert hybrid.mode == "hybrid"
    assert hybrid.hits[0].chunk.chunk_id == "a"
    assert "dense" in hybrid.hits[0].retrievers


def test_restated_risk_factor_keeps_only_newest_copy():
    repeated = "We face intense competition from rivals with greater resources in every market."
    chunks = [
        chunk("y1", "2024-11-01", repeated),
        chunk("y2", "2025-07-01", repeated + " Rivals"),
        chunk("other", "2025-03-01", "Competition for talent is intense."),
    ]
    result = FilingIndex(chunks).search("competition rivals", as_of=date(2025, 8, 1), mode="bm25")
    ids = [hit.chunk.chunk_id for hit in result.hits]
    assert "y2" in ids and "y1" not in ids and "other" in ids


def test_mismatched_embedding_model_falls_back_to_bm25_with_note():
    index = FilingIndex.build(corpus(), FakeEmbedder("model-a"))
    result = index.search("litigation", as_of=date(2025, 8, 1), embedder=FakeEmbedder("model-b"))
    assert result.mode == "bm25"
    assert any("mixing embedding spaces" in note for note in result.notes)


def test_save_load_round_trip_and_stale_vectors_removed(tmp_path):
    index = FilingIndex.build(corpus(), FakeEmbedder())
    index.save(tmp_path, filings=[])
    loaded = FilingIndex.load(tmp_path)
    assert loaded.chunks == index.chunks
    assert np.allclose(loaded.vectors, index.vectors) and loaded.embed_model == "fake-model"

    FilingIndex(corpus()).save(tmp_path, filings=[])
    assert not (tmp_path / "vectors.npy").exists()
    assert FilingIndex.load(tmp_path).vectors is None


# --- agent tool -----------------------------------------------------------------


def ticker_data(market=Market.US, cutoff=datetime(2025, 8, 1)):
    return TickerData(
        info=TickerInfo(symbol="TEST", name="Test Co", market=market, currency="USD"),
        fetched_at=cutoff,
        price_history=[],
    )


def test_tool_fails_closed_without_index_or_outside_us(tmp_path):
    assert search_filings_payload(ticker_data(), "risk", str(tmp_path))["available"] is False
    my = search_filings_payload(ticker_data(Market.MY), "risk", str(tmp_path))
    assert my == {"available": False, "reason": "SEC filings cover US listings only"}


def test_tool_returns_cited_point_in_time_passages(tmp_path):
    FilingIndex.build(corpus(), FakeEmbedder()).save(index_dir(tmp_path, "TEST"), filings=[])
    payload = search_filings_payload(
        ticker_data(), "lawsuit", str(tmp_path), embedder=FakeEmbedder()
    )
    assert payload["available"] is True and payload["mode"] == "hybrid"
    first = payload["passages"][0]
    assert (first["form"], first["filing_date"], first["section"]) == (
        "10-K", "2025-01-30", "Risk Factors"
    )
    assert all(p["filing_date"] < "2025-08-01" for p in payload["passages"])


def test_fundamentals_agent_exposes_search_filings(tmp_path):
    agent = FundamentalsAgent(Settings(data_dir=str(tmp_path)))
    names = {t.name for t in agent.build_tools(ticker_data())}
    assert "search_filings" in names
