"""Deterministic post-run diagnosis; never changes a tested strategy."""

from __future__ import annotations

from typing import Any


def analyze_backtest(
    *,
    mode: str,
    report: dict[str, Any] | None = None,
    portfolio: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    signal_ablation: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain the observed result and return bounded research actions.

    This is an audit of one run, not a model fit or an automatic parameter
    search. In particular an observed benchmark win never becomes a promotion
    verdict without independent data and the existing external gate.
    """

    findings: list[dict[str, str]] = []
    next_checks: list[str] = []

    def add(status: str, code: str, detail: str) -> None:
        findings.append({"status": status, "code": code, "detail": detail})

    if mode in {"factor", "cross-sectional"}:
        if report is None:
            raise ValueError("standalone quality analysis requires a report")
        candidate = report.get("net_compound_return")
        benchmark = report.get("buy_and_hold_return")
        if candidate is None or benchmark is None:
            add("Critical", "benchmark_unavailable", "Candidate or strict-hold return is unavailable.")
        elif candidate <= benchmark:
            add("Warning", "strict_hold_loss", "Net candidate return did not beat strict hold on this window.")
            next_checks.append("Inspect exposure, selection, and the dated trade log before proposing a new rule.")
        else:
            add("Warning", "historical_win_only", "The observed net return beat strict hold on this inspected window; this is not independent validation.")

        if mode == "cross-sectional":
            interval = report.get("strict_hold_log_excess_ci_95")
            if interval is None or interval[0] <= 0:
                add("Warning", "excess_uncertain", "The paired 95% excess-return interval is unavailable or includes zero.")
            passive_excess = report.get("matched_passive_excess_return")
            if passive_excess is not None and passive_excess <= 0:
                add("Warning", "matched_passive_loss", "The allocator did not beat the same-schedule passive allocation.")
            if report.get("periods", 0) < 30:
                add("Warning", "small_period_sample", "Fewer than 30 monthly periods were observed.")
            if report.get("price_basis") == "provided_open_close_not_dividend_verified":
                add("Warning", "return_basis_unverified", "Dividend and terminal-return treatment is not verified for the price input.")
        else:
            add("Warning", "paired_excess_interval_unavailable", "The factor report has no paired excess-return interval against strict hold.")
            add("Warning", "return_basis_unverified", "Dividend and terminal-return treatment is not verified for the price input.")
        next_checks.append("Freeze the rule and data snapshot; use an untouched forward period for confirmation.")
    else:
        if portfolio is None:
            raise ValueError("pipeline quality analysis requires a portfolio")
        strategies = {row.get("strategy"): row for row in portfolio.get("strategies", [])}
        overall = strategies.get("overall", {})
        hold = strategies.get("buy_and_hold", {})
        if not overall or not hold:
            add("Critical", "benchmark_unavailable", "Overall or strict-hold portfolio row is missing.")
        else:
            excess = overall.get("excess_return_pct")
            if excess is None or excess <= 0:
                add("Critical", "strict_hold_loss", "The overall pipeline did not beat strict hold after costs.")
            else:
                add("Warning", "historical_win_only", "The overall pipeline beat strict hold in this run, subject to validation gates.")
            matched = overall.get("matched_exposure_excess_pct")
            if matched is not None and matched <= 0:
                add("Warning", "matched_exposure_loss", "The signal did not beat a passive portfolio at the same dates and dollar stakes.")
                next_checks.append("Audit dated evidence and selection before increasing position size.")
            if (overall.get("effective_n") or 0) < 30:
                add("Warning", "small_effective_sample", "Portfolio effective sample size is below the promotion threshold of 30.")
            interval = overall.get("strict_hold_log_excess_ci_95")
            if interval is None or interval[0] <= 0:
                add("Warning", "excess_uncertain", "The paired 95% excess-return interval is unavailable or includes zero.")
        if portfolio.get("promotion_ready") is not True:
            add("Critical", "promotion_gate_failed", "The numerical portfolio promotion gate did not pass.")
        if score is not None and score.get("errored_trials", 0):
            add("Warning", "incomplete_trials", "Some trials errored; inspect coverage before interpreting the portfolio.")
        coverage = (result or {}).get("settings", {}).get("evidence_coverage", {})
        total = coverage.get("total_trials") or 0
        for analyst, available in sorted(coverage.get("available", {}).items()):
            if total and available < total:
                add("Warning", "evidence_gap", f"{analyst} evidence was present for {available}/{total} trials.")
        if (result or {}).get("settings", {}).get("pipeline_mode") == "in-session":
            add("Warning", "provider_unverified", "In-session historical predictions are not authenticated production-provider forecasts.")
        if signal_ablation is not None:
            hybrid = signal_ablation.get("hybrid") or {}
            if hybrid.get("excess_return") is not None and hybrid["excess_return"] <= 0:
                add("Warning", "ai_overlay_loss", "The AI filter did not add return over its exposure-matched momentum reference.")
        next_checks.append("Resolve provider, point-in-time data, total-return, and calibrated-cost gates before promotion.")

    if ledger is not None:
        ledger_meta = ledger.get("ledger", {})
        count = ledger_meta.get("unique_candidate_count_after")
        if count is not None:
            add("Warning", "search_count", f"Ledger has {count} unique recorded candidate arms; earlier/manual searches are not reconstructed.")
        if ledger_meta.get("runs_before", 0) and ledger_meta.get("new_evaluation_arms_in_run") == 0:
            add("Warning", "repeated_evaluation", "All candidate evaluations in this run were already recorded; this adds reproducibility evidence, not a fresh sample.")
        if ledger_meta.get("same_input_outcome_changed") is True:
            add("Critical", "frozen_input_result_changed", "The same frozen input and run configuration produced different recorded strategy metrics; review code and accounting changes before interpreting this run.")
        elif ledger_meta.get("same_input_previous_run_id"):
            add("OK", "frozen_input_reproduced", "The same frozen input and run configuration reproduced the recorded strategy metrics.")

    return {
        "schema_version": 1,
        "mode": mode,
        "verdict": "research_only",
        "findings": findings,
        "next_checks": next_checks,
        "auto_tuning_performed": False,
    }


def quality_to_markdown(analysis: dict[str, Any]) -> str:
    lines = [
        "## Automatic Quality Analysis",
        "",
        "> [Status: Warning] Research-only diagnosis. No strategy parameters or predictions were changed.",
        "",
    ]
    for finding in analysis["findings"]:
        lines.append(f"- [Status: {finding['status']}] `{finding['code']}` — {finding['detail']}")
    lines.extend(["", "### Next checks", ""])
    for check in analysis["next_checks"]:
        lines.append(f"- {check}")
    return "\n".join(lines) + "\n"
