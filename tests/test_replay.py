import json
from datetime import date, datetime
from unittest.mock import patch

import pytest

from stock_analysis.backtest.replay import (
    historical_news_source,
    load_fundamentals_replay,
    load_macro_replay,
    load_news_replay,
)
from stock_analysis.backtest.session import prepare_session_bundle, score_session_bundle
from stock_analysis.models.market_data import Market, PriceBar, TickerData, TickerInfo


def test_session_prepare_rejects_duplicate_tickers_before_fetch(tmp_path):
    with (
        patch("stock_analysis.backtest.session.BacktestFetcher.fetch") as fetch,
        pytest.raises(ValueError, match="Duplicate ticker"),
    ):
        prepare_session_bundle(
            tickers=["TEST", "test"],
            as_of_dates=[date(2025, 7, 30)],
            output_dir=tmp_path / "session",
        )
    fetch.assert_not_called()


def test_session_score_rejects_predictions_outside_manifest_before_fetch(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "manifest.json").write_text(
        json.dumps(
            {
                "market": "US",
                "tickers": ["TEST"],
                "as_of_dates": ["2025-07-30"],
                "horizon_days": 30,
                "lookback_days": 365,
                "created_at": "2025-07-30",
                "trials": [
                    {
                        "ticker": "TEST",
                        "as_of_date": "2025-07-30",
                        "packet": "packets/TEST/2025-07-30.json",
                        "prediction": "predictions/TEST/2025-07-30.json",
                    }
                ],
            }
        )
    )
    (session / "predictions.json").write_text(
        json.dumps(
            [
                {
                    "ticker": ticker,
                    "as_of_date": "2025-07-30",
                    "overall_signal": "neutral",
                    "conviction_score": 0,
                    "signal_convergence": 0,
                }
                for ticker in ("TEST", "EXTRA")
            ]
        )
    )
    with (
        patch("stock_analysis.backtest.session.Backtester") as backtester,
        pytest.raises(ValueError, match="Unexpected session predictions"),
    ):
        score_session_bundle(session)
    backtester.assert_not_called()


def test_session_score_rejects_incomplete_manifest_grid_before_fetch(tmp_path):
    session = tmp_path / "session"
    session.mkdir()
    (session / "manifest.json").write_text(
        json.dumps(
            {
                "market": "US",
                "tickers": ["TEST"],
                "as_of_dates": ["2025-07-30", "2025-08-30"],
                "horizon_days": 30,
                "lookback_days": 365,
                "created_at": "2025-07-30",
                "trials": [
                    {
                        "ticker": "TEST",
                        "as_of_date": "2025-07-30",
                        "packet": "packets/TEST/2025-07-30.json",
                        "prediction": "predictions/TEST/2025-07-30.json",
                    }
                ],
            }
        )
    )
    (session / "predictions.json").write_text(
        json.dumps(
            [
                {
                    "ticker": "TEST",
                    "as_of_date": "2025-07-30",
                    "overall_signal": "neutral",
                    "conviction_score": 0,
                    "signal_convergence": 0,
                }
            ]
        )
    )
    with (
        patch("stock_analysis.backtest.session.Backtester") as backtester,
        pytest.raises(ValueError, match="manifest trial grid"),
    ):
        score_session_bundle(session)
    backtester.assert_not_called()


def test_session_score_rejects_mismatched_packet_before_price_fetch(tmp_path):
    session = tmp_path / "session"
    packet_dir = session / "packets" / "TEST"
    packet_dir.mkdir(parents=True)
    (session / "manifest.json").write_text(
        json.dumps(
            {
                "market": "US",
                "tickers": ["TEST"],
                "as_of_dates": ["2025-07-30"],
                "horizon_days": 30,
                "lookback_days": 365,
                "created_at": "2025-07-30",
                "trials": [
                    {
                        "ticker": "TEST",
                        "as_of_date": "2025-07-30",
                        "packet": "packets/TEST/2025-07-30.json",
                        "prediction": "predictions/TEST/2025-07-30.json",
                    }
                ],
            }
        )
    )
    (session / "predictions.json").write_text(
        json.dumps(
            [
                {
                    "ticker": "TEST",
                    "as_of_date": "2025-07-30",
                    "overall_signal": "neutral",
                    "conviction_score": 0,
                    "signal_convergence": 0,
                }
            ]
        )
    )
    (packet_dir / "2025-07-30.json").write_text(
        json.dumps(
            {
                "ticker": "OTHER",
                "market": "US",
                "as_of_date": "2025-07-30",
                "ticker_data": {"price_history": [{"date": "2025-07-31"}]},
            }
        )
    )
    with (
        patch("stock_analysis.backtest.session.Backtester") as backtester,
        pytest.raises(ValueError, match="packet identity mismatch"),
    ):
        score_session_bundle(session)
    backtester.assert_not_called()


def test_news_replay_requires_matching_ticker_and_embargo(tmp_path):
    news_dir = tmp_path / "news"
    news_dir.mkdir()
    (news_dir / "AAPL.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "ticker": "AAPL",
                    "title": "Known",
                    "published_at": "2026-09-01T00:00:00Z",
                    "available_as_of": "2026-09-01",
                },
                {
                    "ticker": "AAPL",
                    "title": "Not yet available",
                    "published_at": "2026-09-01T00:00:00Z",
                    "available_as_of": "2026-09-03",
                },
                {
                    "ticker": "MSFT",
                    "title": "Wrong ticker",
                    "published_at": "2026-09-01T00:00:00Z",
                    "available_as_of": "2026-09-01",
                },
            ]
        )
        + "\n"
    )

    records = load_news_replay(news_dir, "AAPL", date(2026, 9, 2))

    assert [record["title"] for record in records] == ["Known"]


def test_news_source_requires_explicit_provider_versioning(tmp_path):
    assert historical_news_source(tmp_path) == "historical_replay"
    (tmp_path / "manifest.json").write_text(
        json.dumps({"news": {"source": {"kind": "provider_versioned"}}})
    )
    assert historical_news_source(tmp_path) == "historical_provider"


def test_macro_replay_selects_latest_snapshot_known_at_as_of(tmp_path):
    path = tmp_path / "macro.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "as_of_date": "2026-08-01",
                    "available_as_of": "2026-08-02",
                    "source": "test",
                    "fed_funds_rate": 4.5,
                },
                {
                    "as_of_date": "2026-09-01",
                    "available_as_of": "2026-09-03",
                    "source": "test",
                    "fed_funds_rate": 4.25,
                },
                {
                    "as_of_date": "2026-09-02",
                    "available_as_of": "2026-09-04",
                    "source": "test",
                    "fed_funds_rate": 4.0,
                },
            ]
        )
        + "\n"
    )

    snapshot = load_macro_replay(path, date(2026, 9, 3))

    assert snapshot is not None
    assert snapshot.as_of_date == date(2026, 9, 1)
    assert snapshot.fed_funds_rate == 4.25


def test_invalid_macro_replay_fails_closed_with_context(tmp_path):
    path = tmp_path / "macro.json"
    path.write_text(json.dumps({"source": "missing dates"}))

    with pytest.raises(ValueError, match="Invalid macro replay record"):
        load_macro_replay(path, date(2026, 9, 3))


def test_fundamentals_replay_selects_latest_usable_sec_snapshot(tmp_path):
    fundamentals_dir = tmp_path / "fundamentals"
    fundamentals_dir.mkdir()
    (fundamentals_dir / "TEST.jsonl").write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {
                    "ticker": "TEST",
                    "fiscal_period_end": "2025-03-31",
                    "available_as_of": "2025-05-01",
                    "availability_source": "sec_companyfacts",
                    "revenue": 100.0,
                },
                {
                    "ticker": "TEST",
                    "fiscal_period_end": "2025-06-30",
                    "available_as_of": "2025-08-01",
                    "availability_source": "sec_companyfacts",
                    "revenue": 120.0,
                },
            ]
        )
        + "\n"
    )

    financials = load_fundamentals_replay(tmp_path, "TEST", date(2025, 8, 2))

    assert financials is not None
    assert financials.revenue == 120.0
    assert financials.available_as_of == date(2025, 8, 1)


def test_fundamentals_replay_rejects_future_period_or_filing(tmp_path):
    fundamentals_dir = tmp_path / "fundamentals"
    fundamentals_dir.mkdir()
    (fundamentals_dir / "TEST.jsonl").write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "fiscal_period_end": "2025-09-30",
                "available_as_of": "2025-11-01",
                "availability_source": "sec_companyfacts",
                "revenue": 140.0,
            }
        )
        + "\n"
    )

    assert load_fundamentals_replay(tmp_path, "TEST", date(2025, 10, 31)) is None


def test_session_prepare_wires_only_point_in_time_replay_evidence(tmp_path):
    replay_dir = tmp_path / "replay"
    news_dir = replay_dir / "news"
    news_dir.mkdir(parents=True)
    (news_dir / "TEST.jsonl").write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "title": "Replay-safe headline",
                "published_at": "2025-07-29T00:00:00Z",
                "available_as_of": "2025-07-30",
            }
        )
        + "\n"
    )
    (replay_dir / "macro.jsonl").write_text(
        json.dumps(
            {
                "as_of_date": "2025-07-29",
                "available_as_of": "2025-07-30",
                "source": "test",
                "fed_funds_rate": 4.5,
            }
        )
        + "\n"
    )
    fundamentals_dir = replay_dir / "fundamentals"
    fundamentals_dir.mkdir()
    (fundamentals_dir / "TEST.jsonl").write_text(
        json.dumps(
            {
                "ticker": "TEST",
                "fiscal_period_end": "2025-06-30",
                "available_as_of": "2025-07-29",
                "availability_source": "sec_companyfacts",
                "revenue": 120.0,
            }
        )
        + "\n"
    )
    ticker_data = TickerData(
        info=TickerInfo(
            symbol="TEST",
            name="Test Co",
            market=Market.US,
            currency="USD",
        ),
        price_history=[
            PriceBar(
                date=date(2025, 7, 30),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1_000,
            )
        ],
        fetched_at=datetime(2025, 7, 30, 12, 0, 0),
    )

    with patch(
        "stock_analysis.backtest.session.BacktestFetcher.fetch",
        return_value=ticker_data,
    ):
        prepare_session_bundle(
            tickers=["TEST"],
            as_of_dates=[date(2025, 7, 30)],
            output_dir=tmp_path / "session",
            replay_dir=replay_dir,
        )

    packet = json.loads(
        (tmp_path / "session/packets/TEST/2025-07-30.json").read_text()
    )
    assert packet["evidence_availability"]["sentiment"] is True
    assert packet["evidence_availability"]["macro"] is True
    assert packet["evidence_availability"]["fundamentals"] is True
    assert packet["evidence_availability"]["fundamentals_source"] == "sec_companyfacts"
    assert packet["ticker_data"]["macro_snapshot"]["fed_funds_rate"] == 4.5
    assert packet["ticker_data"]["financials"]["revenue"] == 120.0
    assert packet["ticker_data"]["news_headlines"][0]["title"] == "Replay-safe headline"
