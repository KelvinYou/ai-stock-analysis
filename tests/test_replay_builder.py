import json
from datetime import date

import pytest

from stock_analysis.backtest import replay_builder


def test_filing_record_uses_acceptance_time_for_both_clocks():
    record = replay_builder._filing_record(
        "AAPL",
        320193,
        {
            "filingDate": "2026-01-05",
            "acceptanceDateTime": "2026-01-05T21:30:00.000Z",
            "form": "8-K",
            "accessionNumber": "0000320193-26-000001",
            "primaryDocument": "aapl-20260105.htm",
            "primaryDocDescription": "Current report",
        },
    )

    assert record is not None
    assert record["published_at"] == "2026-01-05T21:30:00Z"
    assert record["available_as_of"] == "2026-01-05"
    assert record["link"].endswith("/000032019326000001/aapl-20260105.htm")


def test_fred_macro_builder_requires_a_one_day_availability_lag(monkeypatch):
    monkeypatch.setattr(
        replay_builder,
        "_fetch_bytes",
        lambda *args, **kwargs: b"observation_date,DFF\n2026-01-05,4.33\n",
    )

    records, source = replay_builder.build_fred_macro(
        start=date(2026, 1, 5),
        end=date(2026, 1, 5),
        user_agent="test",
    )

    assert records == [
        {
            "as_of_date": "2026-01-05",
            "available_as_of": "2026-01-06",
            "source": "FRED:DFF",
            "fed_funds_rate": 4.33,
        }
    ]
    assert source["series"] == "DFF"


def test_companyfacts_snapshot_respects_filing_cutoff_and_derives_margins():
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 100.0,
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "filed": "2025-05-01",
                                "form": "10-Q",
                            },
                            {
                                "val": 110.0,
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "filed": "2025-06-01",
                                "form": "10-Q",
                            },
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 20.0,
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "filed": "2025-05-01",
                                "form": "10-Q",
                            }
                        ]
                    }
                },
                "GrossProfit": {
                    "units": {
                        "USD": [
                            {
                                "val": 50.0,
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "filed": "2025-05-01",
                                "form": "10-Q",
                            }
                        ]
                    }
                },
            }
        }
    }

    before_restatement = replay_builder._fundamental_snapshot(
        payload,
        available_as_of=date(2025, 5, 2),
    )
    after_restatement = replay_builder._fundamental_snapshot(
        payload,
        available_as_of=date(2025, 6, 2),
    )

    assert before_restatement is not None
    assert before_restatement["revenue"] == 100.0
    assert before_restatement["gross_margin"] == 0.5
    assert after_restatement is not None
    assert after_restatement["revenue"] == 110.0


def test_replay_builder_refuses_to_overwrite_existing_directory(tmp_path):
    output = tmp_path / "replay"
    output.mkdir()
    (output / "existing").write_text("keep")

    with pytest.raises(FileExistsError):
        replay_builder.build_replay_directory(
            tickers=["AAPL"],
            start=date(2026, 1, 1),
            end=date(2026, 1, 2),
            output_dir=output,
            user_agent="test",
        )


def test_manifest_is_json_serialisable(tmp_path, monkeypatch):
    monkeypatch.setattr(
        replay_builder,
        "build_sec_news",
        lambda *args, **kwargs: ({"AAPL": []}, {"name": "SEC"}),
    )
    monkeypatch.setattr(
        replay_builder,
        "build_fred_macro",
        lambda *args, **kwargs: (
            [
                {
                    "as_of_date": "2026-01-01",
                    "available_as_of": "2026-01-02",
                    "source": "FRED:DFF",
                    "fed_funds_rate": 4.33,
                }
            ],
            {"name": "FRED"},
        ),
    )
    monkeypatch.setattr(
        replay_builder,
        "build_sec_fundamentals",
        lambda *args, **kwargs: ({"AAPL": []}, {"name": "SEC CompanyFacts"}),
    )

    manifest = replay_builder.build_replay_directory(
        tickers=["AAPL"],
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        output_dir=tmp_path / "replay",
        user_agent="test",
    )

    loaded = json.loads((tmp_path / "replay/manifest.json").read_text())
    assert loaded["news"]["records"] == 0
    assert loaded["fundamentals"]["records"] == 0
    assert loaded["macro"]["records"] == 1
    assert manifest["tickers"] == ["AAPL"]
