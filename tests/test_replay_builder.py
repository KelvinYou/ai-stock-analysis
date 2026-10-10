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


def _fact(value, *, start="2025-04-01", end="2025-06-30", filed="2025-08-01"):
    row = {"val": value, "end": end, "filed": filed, "form": "10-Q", "accn": "fixture"}
    if start is not None:
        row["start"] = start
    return row


def test_snapshot_never_divides_quarter_income_by_ytd_revenue_or_cashflow():
    payload = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [_fact(100), _fact(200, start="2025-01-01")]}},
        "NetIncomeLoss": {"units": {"USD": [_fact(20)]}},
        "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [_fact(50, start="2025-01-01")]}},
        "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [_fact(10, start="2025-01-01")]}},
    }}}
    snapshot = replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 2))
    assert snapshot["period_kind"] == "quarter"
    assert snapshot["net_margin"] == 0.2
    assert snapshot["free_cash_flow"] is None


def test_snapshot_does_not_mix_monetary_currencies():
    payload = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [_fact(100)]}},
        "NetIncomeLoss": {"units": {"EUR": [_fact(20)]}},
    }}}
    snapshot = replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 2))
    assert snapshot["currency"] == "USD"
    assert snapshot["net_income"] is None
    assert snapshot["net_margin"] is None


def test_eps_shares_and_debt_components_preserve_units_and_partial_scope():
    payload = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [_fact(100)]}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": [_fact(2)]}},
        "CommonStockSharesOutstanding": {"units": {"shares": [_fact(50, start=None)]}},
        "LongTermDebtCurrent": {"units": {"USD": [_fact(10, start=None)]}},
        "LongTermDebtNoncurrent": {"units": {"USD": [_fact(90, start=None)]}},
    }}}
    snapshot = replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 2))
    assert snapshot["diluted_eps"] == 2
    assert snapshot["shares_outstanding"] == 50
    assert snapshot["total_debt"] == 100
    assert snapshot["debt_scope"] == "matched_long_term_subtotal"
    assert snapshot["share_basis"] is None
    assert snapshot["fact_provenance"]["diluted_eps"]["unit"] == "USD/shares"


def test_companyfacts_date_only_clock_does_not_use_same_day_filings():
    payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [_fact(100)]}}}}}
    assert replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 1)) is None
    assert replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 2)) is not None


def test_builder_retains_old_comparative_periods_and_distinct_durations(monkeypatch):
    payload = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            _fact(80, start="2024-04-01", end="2024-06-30", filed="2024-08-01"),
            _fact(100), _fact(200, start="2025-01-01"),
        ]}},
    }}}
    monkeypatch.setattr(replay_builder, "_ticker_ciks", lambda *a, **kw: {"TEST": (1, "TEST")})
    monkeypatch.setattr(replay_builder, "_fetch_json", lambda *a, **kw: payload)
    records, _ = replay_builder.build_sec_fundamentals(
        ["TEST"], start=date(2025, 8, 1), end=date(2025, 8, 2), user_agent="fixture",
    )
    identities = {(r["fiscal_period_start"], r["fiscal_period_end"]) for r in records["TEST"]}
    assert ("2024-04-01", "2024-06-30") in identities
    assert ("2025-04-01", "2025-06-30") in identities
    assert ("2025-01-01", "2025-06-30") in identities


def test_same_clock_conflicting_facts_fail_closed():
    payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [_fact(100), _fact(999)]}}}}}
    with pytest.raises(ValueError, match="Conflicting SEC facts"):
        replay_builder._fundamental_snapshot(payload, available_as_of=date(2025, 8, 2))
