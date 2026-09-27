import hashlib
import json
from pathlib import Path

from stock_analysis.backtest.external_validation import validate_session_bundle


def _write_minimal_bundle(tmp_path: Path) -> Path:
    session = tmp_path / "session"
    packet_dir = session / "packets" / "TEST"
    packet_dir.mkdir(parents=True)
    packet = {
        "pipeline_mode": "in-session",
        "ticker": "TEST",
        "market": "US",
        "as_of_date": "2025-07-30",
        "do_not_use_future_prices": True,
        "ticker_data": {
            "price_history": [{"date": "2025-07-30"}],
        },
        "evidence_availability": {
            "technical": True,
            "fundamentals": True,
            "fundamentals_source": "sec_companyfacts",
            "sentiment": True,
            "sentiment_source": "historical_replay",
            "macro": True,
            "macro_source": "FRED:DFF",
        },
    }
    packet_path = packet_dir / "2025-07-30.json"
    packet_path.write_text(json.dumps(packet))
    manifest = {
        "pipeline_mode": "in-session",
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
            }
        ],
    }
    (session / "manifest.json").write_text(json.dumps(manifest))
    return session


def test_packet_integrity_rejects_incomplete_manifest_grid_and_mismatched_packet(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    manifest_path = session / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["as_of_dates"].append("2025-08-30")
    manifest_path.write_text(json.dumps(manifest))
    report = validate_session_bundle(session, min_effective_n=1)
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["point-in-time packet integrity"] == "FAIL"

    manifest["as_of_dates"] = ["2025-07-30"]
    manifest_path.write_text(json.dumps(manifest))
    packet_path = session / "packets/TEST/2025-07-30.json"
    packet = json.loads(packet_path.read_text())
    packet["ticker"] = "OTHER"
    packet_path.write_text(json.dumps(packet))
    report = validate_session_bundle(session, min_effective_n=1)
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["point-in-time packet integrity"] == "FAIL"


def test_packet_integrity_fails_closed_on_malformed_bar_and_escaping_path(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    packet_path = session / "packets/TEST/2025-07-30.json"
    packet = json.loads(packet_path.read_text())
    packet["ticker_data"]["price_history"][0]["date"] = "not-a-date"
    packet_path.write_text(json.dumps(packet))
    report = validate_session_bundle(session, min_effective_n=1)
    assert {gate.name: gate.status for gate in report.gates}[
        "point-in-time packet integrity"
    ] == "FAIL"

    manifest_path = session / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["trials"][0]["packet"] = "../outside.json"
    manifest_path.write_text(json.dumps(manifest))
    report = validate_session_bundle(session, min_effective_n=1)
    assert {gate.name: gate.status for gate in report.gates}[
        "point-in-time packet integrity"
    ] == "FAIL"


def test_external_validation_fails_closed_on_malformed_manifest_json(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    (session / "manifest.json").write_text("{broken")
    report = validate_session_bundle(session, min_effective_n=1)
    assert report.status == "FAIL"
    assert report.gates[0].name == "session manifest"


def test_metadata_gate_rejects_unversioned_current_company_name(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    packet_path = session / "packets/TEST/2025-07-30.json"
    packet = json.loads(packet_path.read_text())
    packet["ticker_data"]["info"] = {
        "symbol": "TEST", "name": "Future Rebrand", "currency": "USD",
        "sector": None, "industry": None,
    }
    packet["evidence_availability"]["metadata_source"] = (
        "fail_closed_current_provider_metadata_omitted"
    )
    packet_path.write_text(json.dumps(packet))
    report = validate_session_bundle(session, min_effective_n=1)
    assert {gate.name: gate.status for gate in report.gates}[
        "point-in-time metadata"
    ] == "FAIL"


def _write_complete_universe(session: Path) -> dict:
    membership_records = [
        {
            "ticker": "TEST",
            "as_of_date": "2025-07-30",
            "security_id": "PERMNO-1",
            "member": True,
        }
    ]
    membership_bytes = json.dumps(
        membership_records,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return_treatment = {
        "source": "CRSP US Stock & Indexes",
        "field": "DlyRet",
        "data_sha256": hashlib.sha256(b"total-return-export").hexdigest(),
        "includes_distributions": True,
        "includes_delisting_returns": True,
        "includes_merger_consideration": True,
        "missing_return_policy": "fail_closed",
    }
    universe = {
        "schema_version": 1,
        "universe_id": "fixture-pit-universe",
        "membership_source": "CRSP US Stock & Indexes",
        "membership_source_url": "https://www.crsp.org/research/",
        "membership_as_of_policy": "membership effective on the trial date",
        "security_id_scheme": "CRSP PERMNO",
        "selection_policy": "fixture selection policy frozen before the trial",
        "survivorship_bias_control": True,
        "source_extract_sha256": hashlib.sha256(b"membership-export").hexdigest(),
        "tickers": ["TEST"],
        "membership_records": membership_records,
        "membership_records_sha256": hashlib.sha256(membership_bytes).hexdigest(),
        "return_treatment": return_treatment,
    }
    (session / "universe.json").write_text(json.dumps(universe))
    return universe


def test_external_validation_blocks_unpaired_and_assumed_inputs(tmp_path):
    report = validate_session_bundle(_write_minimal_bundle(tmp_path), min_effective_n=1)

    assert report.status == "BLOCKED"
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["point-in-time packet integrity"] == "PASS"
    assert gates["production provider run"] == "BLOCKED"
    assert gates["survivorship-safe universe"] == "BLOCKED"
    assert gates["scored terminal-return provenance"] == "BLOCKED"
    assert gates["execution cost calibration"] == "BLOCKED"
    assert gates["effective sample"] == "BLOCKED"
    assert gates["strict long-hold benchmark"] == "BLOCKED"


def test_universe_gate_requires_hashed_per_trial_membership_and_terminal_policy(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    universe = _write_complete_universe(session)

    report = validate_session_bundle(session, min_effective_n=1)
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["survivorship-safe universe"] == "PASS"
    assert gates["scored terminal-return provenance"] == "BLOCKED"

    score_path = session / "score.json"
    score_path.write_text(
        json.dumps(
            {"result": {"settings": {"terminal_return_provenance": universe["return_treatment"]}}}
        )
    )
    report = validate_session_bundle(session, min_effective_n=1)
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["scored terminal-return provenance"] == "PASS"

    universe["membership_records"][0]["as_of_date"] = "2025-07-29"
    records_bytes = json.dumps(
        universe["membership_records"],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    universe["membership_records_sha256"] = hashlib.sha256(records_bytes).hexdigest()
    (session / "universe.json").write_text(json.dumps(universe))
    report = validate_session_bundle(session, min_effective_n=1)
    gates = {gate.name: gate.status for gate in report.gates}
    assert gates["survivorship-safe universe"] == "FAIL"


def test_terminal_return_gate_rejects_score_using_a_different_return_source(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    universe = _write_complete_universe(session)
    scored_treatment = dict(universe["return_treatment"])
    scored_treatment["data_sha256"] = hashlib.sha256(b"different-export").hexdigest()
    (session / "score.json").write_text(
        json.dumps({"result": {"settings": {"terminal_return_provenance": scored_treatment}}})
    )

    report = validate_session_bundle(session, min_effective_n=1)
    gate = next(gate for gate in report.gates if gate.name == "scored terminal-return provenance")
    assert gate.status == "FAIL"

    (session / "score.json").write_text(
        json.dumps({"result": {"settings": {"terminal_return_provenance": {}}}})
    )
    report = validate_session_bundle(session, min_effective_n=1)
    gate = next(gate for gate in report.gates if gate.name == "scored terminal-return provenance")
    assert gate.status == "FAIL"


def test_provider_gate_does_not_authenticate_self_declared_metadata(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    manifest_path = session / "manifest.json"
    (session / "provider_run.json").write_text(
        json.dumps(
            {
                "provider": "anthropic",
                "model": "claude-sonnet",
                "run_id": "run-1",
                "packet_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "prediction_count": 1,
            }
        )
    )

    report = validate_session_bundle(session, min_effective_n=1)
    provider_gate = next(gate for gate in report.gates if gate.name == "production provider run")

    assert provider_gate.status == "BLOCKED"
    assert "provider invocation is unverified" in provider_gate.observed

    metadata = json.loads((session / "provider_run.json").read_text())
    metadata["packet_manifest_sha256"] = "0" * 64
    (session / "provider_run.json").write_text(json.dumps(metadata))
    report = validate_session_bundle(session, min_effective_n=1)
    provider_gate = next(gate for gate in report.gates if gate.name == "production provider run")
    assert provider_gate.status == "FAIL"


def test_scored_panel_gate_requires_every_manifest_trial_and_valid_outcome(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    score_path = session / "score.json"
    trial = {
        "ticker": "TEST",
        "as_of_date": "2025-07-30",
        "entry_date": "2025-07-31",
        "exit_date": "2025-08-29",
        "entry_price": 100.0,
        "exit_price": 105.0,
        "realized_return": 0.05,
        "error": None,
    }

    def gate_for(trials):
        score_path.write_text(json.dumps({"result": {"trials": trials}}))
        report = validate_session_bundle(session, score_report=score_path, min_effective_n=1)
        return next(gate for gate in report.gates if gate.name == "scored panel completeness")

    assert gate_for([trial]).status == "PASS"
    assert gate_for([]).status == "FAIL"
    assert gate_for([trial, trial]).status == "FAIL"
    assert gate_for([{**trial, "error": "model failed"}]).status == "FAIL"
    assert gate_for([{**trial, "realized_return": None}]).status == "FAIL"


def test_paired_strict_hold_alpha_gate_requires_positive_valid_interval(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    score_path = session / "score.json"

    for interval, expected in (
        ([-0.01, 0.04], "FAIL"),
        ([0.01, 0.04], "PASS"),
        (None, "BLOCKED"),
    ):
        score_path.write_text(
            json.dumps(
                {
                    "report": {"effective_n": 30},
                    "portfolio": {
                        "benchmark_strategy": "buy_and_hold",
                        "benchmark_beaten": True,
                        "promotion_ready": True,
                        "strategies": [
                            {
                                "strategy": "overall",
                                "strict_hold_log_excess_ci_95": interval,
                            }
                        ],
                    },
                }
            )
        )
        report = validate_session_bundle(session, min_effective_n=1)
        paired_gate = next(
            gate for gate in report.gates if gate.name == "paired strict-hold alpha interval"
        )
        assert paired_gate.status == expected


def test_effective_sample_gate_uses_clustered_portfolio_n_not_trial_n(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    score_path = session / "score.json"
    score_path.write_text(
        json.dumps(
            {
                "report": {"effective_n": 120},
                "portfolio": {
                    "strategies": [
                        {
                            "strategy": "overall",
                            "effective_n": 2.0,
                            "effective_n_basis": "portfolio_overlap_clustered_v1",
                        },
                    ]
                },
            }
        )
    )

    report = validate_session_bundle(session, score_report=score_path, min_effective_n=3)
    sample_gate = next(gate for gate in report.gates if gate.name == "effective sample")

    assert sample_gate.status == "FAIL"
    assert "effective n=2.00" in sample_gate.observed

    score_path.write_text(
        json.dumps(
            {
                "report": {"effective_n": 120},
                "portfolio": {
                    "strategies": [
                        {
                            "strategy": "overall",
                            "effective_n": 3.0,
                            "effective_n_basis": "portfolio_overlap_clustered_v1",
                        },
                    ]
                },
            }
        )
    )
    report = validate_session_bundle(session, score_report=score_path, min_effective_n=3)
    sample_gate = next(gate for gate in report.gates if gate.name == "effective sample")
    assert sample_gate.status == "PASS"


def test_effective_sample_gate_blocks_legacy_unclustered_score(tmp_path):
    session = _write_minimal_bundle(tmp_path)
    score_path = session / "score.json"
    score_path.write_text(
        json.dumps(
            {
                "report": {"effective_n": 120},
                "portfolio": {
                    "strategies": [
                        {"strategy": "overall", "effective_n": 120.0},
                    ]
                },
            }
        )
    )

    report = validate_session_bundle(session, score_report=score_path, min_effective_n=30)
    sample_gate = next(gate for gate in report.gates if gate.name == "effective sample")

    assert sample_gate.status == "BLOCKED"
    assert "effective_n_basis" in sample_gate.observed
