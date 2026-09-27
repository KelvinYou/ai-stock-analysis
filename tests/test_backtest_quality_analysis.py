from stock_analysis.backtest.quality_analysis import analyze_backtest, quality_to_markdown


def test_pipeline_loss_reports_selection_and_sample_without_auto_tuning():
    analysis = analyze_backtest(
        mode="session-score",
        portfolio={
            "promotion_ready": False,
            "strategies": [
                {
                    "strategy": "overall",
                    "excess_return_pct": -9.44,
                    "matched_exposure_excess_pct": -0.47,
                    "effective_n": 6.0,
                    "strict_hold_log_excess_ci_95": [-0.003, 0.001],
                },
                {"strategy": "buy_and_hold", "total_return_pct": 8.04},
            ],
        },
        score={"errored_trials": 0},
        result={
            "settings": {
                "pipeline_mode": "in-session",
                "evidence_coverage": {
                    "total_trials": 88,
                    "available": {"technical": 88, "sentiment": 0},
                },
            }
        },
    )

    codes = {finding["code"] for finding in analysis["findings"]}
    assert {"strict_hold_loss", "matched_exposure_loss", "small_effective_sample", "evidence_gap", "provider_unverified", "promotion_gate_failed"} <= codes
    assert analysis["verdict"] == "research_only"
    assert analysis["auto_tuning_performed"] is False
    assert "before increasing position size" in quality_to_markdown(analysis)


def test_standalone_historical_win_never_becomes_promotion():
    analysis = analyze_backtest(
        mode="cross-sectional",
        report={
            "net_compound_return": 0.14,
            "buy_and_hold_return": 0.11,
            "matched_passive_excess_return": 0.01,
            "strict_hold_log_excess_ci_95": [-0.01, 0.03],
            "periods": 7,
            "price_basis": "provided_open_close_not_dividend_verified",
        },
        ledger={"ledger": {"same_input_outcome_changed": True}},
    )
    codes = {finding["code"] for finding in analysis["findings"]}
    assert {"historical_win_only", "excess_uncertain", "small_period_sample", "return_basis_unverified"} <= codes
    assert "frozen_input_result_changed" in codes
    assert analysis["verdict"] == "research_only"


def test_same_frozen_input_can_reproduce_without_becoming_new_evidence():
    analysis = analyze_backtest(
        mode="factor",
        report={"net_compound_return": 0.1, "buy_and_hold_return": 0.2},
        ledger={
            "ledger": {
                "runs_before": 1,
                "new_evaluation_arms_in_run": 0,
                "same_input_previous_run_id": "prior",
                "same_input_outcome_changed": False,
            }
        },
    )
    codes = {finding["code"] for finding in analysis["findings"]}
    assert "frozen_input_reproduced" in codes
    assert "repeated_evaluation" in codes
    assert analysis["verdict"] == "research_only"
