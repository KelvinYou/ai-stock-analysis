from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from stock_analysis.config import Settings, load_env
from stock_analysis.data.cloud import build_store
from stock_analysis.memory.cloud import build_outcome_store
from stock_analysis.memory.outcomes import records_from_backtest

from . import portfolio as portfolio_mod
from .cross_sectional import (
    CrossSectionalConfig,
    OverlappingSealedWindowsError,
    run_cross_sectional_backtest,
    run_cross_sectional_trial_backtest,
    trial_allocation_to_markdown,
)
from .cross_sectional import to_markdown as cross_sectional_to_markdown
from .experiment_ledger import (
    append_experiment_record,
    build_experiment_record,
    build_standalone_record,
)
from .external_validation import validate_session_bundle
from .factor import (
    FactorConfig,
    clean_price_history,
    load_price_history,
    run_factor_backtest,
)
from .factor import (
    to_markdown as factor_to_markdown,
)
from .portfolio import PortfolioConfig
from .quality_analysis import analyze_backtest, quality_to_markdown
from .replay import load_cash_rate_replay
from .runner import Backtester, BacktestResult, BacktestTrial
from .scorer import Scorer
from .session import prepare_session_bundle, recalibrate_session_result, score_session_bundle
from .signal_ablation import (
    SignalAblationConfig,
    run_signal_ablation,
    signal_ablation_to_markdown,
)

logger = logging.getLogger(__name__)


def cli():
    load_env()
    parser = argparse.ArgumentParser(
        description="Backtest the AI stock analysis pipeline against historical prices."
    )
    parser.add_argument(
        "--mode",
        choices=[
            "api",
            "factor",
            "cross-sectional",
            "session-prepare",
            "session-score",
            "rescore",
            "external-validate",
        ],
        default="api",
        help=(
            "api runs the SDK pipeline; factor runs the deterministic momentum slice; "
            "cross-sectional runs fixed-universe monthly ranking; "
            "session-prepare writes point-in-time packets; session-score scores "
            "session predictions; rescore reuses an existing scored result's "
            "trials and price paths without refetching; external-validate hard-fails missing provider, "
            "universe, cost, sample, or benchmark evidence (default: api)."
        ),
    )
    parser.add_argument(
        "--tickers",
        help="Comma-separated list of tickers (e.g., AAPL,NVDA,MSFT).",
    )
    parser.add_argument("--start", help="Start date YYYY-MM-DD.")
    parser.add_argument("--end", help="End date YYYY-MM-DD.")
    parser.add_argument(
        "--interval",
        choices=["weekly", "biweekly", "monthly", "quarterly"],
        default="monthly",
        help="Spacing between as-of dates (default: monthly).",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=30,
        help="Forward-looking holding period in calendar days (default: 30).",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=365,
        help="Historical price window passed to agents, in days (default: 365).",
    )
    parser.add_argument(
        "--factor-lookback-bars",
        type=int,
        default=20,
        help="Momentum lookback for --mode factor (default: 20 trading bars).",
    )
    parser.add_argument(
        "--factor-holding-bars",
        type=int,
        default=20,
        help="Holding period for --mode factor (default: 20 trading bars).",
    )
    parser.add_argument(
        "--walk-forward-train-bars",
        type=int,
        default=252,
        help="Initial expanding walk-forward warm-up for --mode factor (default: 252).",
    )
    parser.add_argument(
        "--walk-forward-test-bars",
        type=int,
        default=63,
        help="Out-of-sample window for --mode factor (default: 63 trading bars).",
    )
    parser.add_argument(
        "--cross-sectional-lookback-months",
        type=int,
        default=12,
        help="Trailing monthly return window for --mode cross-sectional (default: 12).",
    )
    parser.add_argument(
        "--cross-sectional-top-n",
        type=int,
        default=3,
        help="Number of equal-weight winners for --mode cross-sectional (default: 3).",
    )
    parser.add_argument("--market", choices=["US", "MY"], default="US")
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Debate rounds per trial (default: 1 — backtest cost control).",
    )
    parser.add_argument(
        "--model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Model for analyst agents (default: haiku).",
    )
    parser.add_argument(
        "--debate-model",
        choices=["haiku", "sonnet", "opus"],
        default="sonnet",
        help="Model for debate agents (default: sonnet — haiku is too unreliable for structured output).",
    )
    parser.add_argument(
        "--synthesis-model",
        choices=["haiku", "sonnet", "opus"],
        default="haiku",
        help="Model for synthesis (default: haiku).",
    )
    parser.add_argument(
        "--output",
        default="backtest_report",
        help="Output file prefix — writes <prefix>.json and <prefix>.md.",
    )
    parser.add_argument(
        "--experiment-ledger",
        type=Path,
        help=(
            "Append scored and deterministic research runs to this JSONL ledger. Defaults to "
            "backtest_experiments.jsonl in the current directory; counts start "
            "with the first recorded run."
        ),
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=Path("backtest_session"),
        help="Directory for session packets, predictions, and outcomes.",
    )
    parser.add_argument("--recalibrate-session", action="store_true", help="Rescore sealed predictions with current production calibration; requires rescore and --session-dir.")
    parser.add_argument(
        "--score-report",
        type=Path,
        help="Scored JSON input for --mode rescore; optional for --mode external-validate.",
    )
    parser.add_argument(
        "--min-effective-n",
        type=float,
        default=30.0,
        help="Minimum portfolio-clustered effective sample size for --mode external-validate (default: 30).",
    )
    parser.add_argument(
        "--replay-dir",
        type=Path,
        help=(
            "Optional point-in-time evidence directory for api or session-prepare: "
            "fundamentals/, valuation/, news/ and macro.jsonl. Every record must carry "
            "an explicit first-available/embargo date."
        ),
    )
    parser.add_argument(
        "--cash-rate-replay",
        type=Path,
        help=(
            "Optional FRED:DFF CSV or JSON/JSONL observations for the cash-yield "
            "diagnostic. Used by api, session-score, and rescore modes."
        ),
    )
    parser.add_argument(
        "--record-outcomes",
        action="store_true",
        help=(
            "Append realized outcomes to the configured outcome backend so future runs "
            "see this track record. Off by default: recording changes what "
            "later runs read, so back-to-back backtests would stop being comparable."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Where per-ticker price history/outcomes live (default: data).",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Deprecated: API backtests always regenerate unversioned cached briefings.",
    )
    parser.add_argument(
        "--starting-balance",
        type=float,
        default=10_000.0,
        help="Simulated starting cash for portfolio simulation (default: 10000).",
    )
    parser.add_argument(
        "--position-size",
        type=float,
        default=0.10,
        help="Fraction of current cash allocated per trade (default: 0.10).",
    )
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Take short positions on sell/strong_sell signals (default: skip).",
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=0.0,
        help=(
            "One-way transaction cost in basis points (commission + spread + "
            "slippage), charged on entry and again on exit. Default 0 keeps "
            "historical reports comparable, but 0 is an assumption, not a "
            "neutral default — try 10 for liquid US large caps, 30-50+ for "
            "Bursa small caps."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.cash_rate_replay and args.mode not in {"api", "session-score", "rescore"}:
        parser.error(
            "--cash-rate-replay is only supported by api, session-score, and rescore"
        )

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.recalibrate_session and args.mode != "rescore":
        parser.error("--recalibrate-session requires --mode rescore")

    if args.mode == "session-score":
        result = score_session_bundle(args.session_dir)
        _score_and_write(result, args)
        return

    if args.mode == "rescore":
        if args.score_report is None:
            parser.error("--score-report is required for --mode rescore")
        if args.record_outcomes:
            parser.error("--mode rescore cannot record outcomes again")
        input_path = args.score_report.resolve()
        output_path = Path(f"{args.output}.json").resolve()
        if input_path == output_path:
            parser.error("--output must not overwrite the rescore input")
        raw = input_path.read_bytes()
        payload = json.loads(raw)
        result = BacktestResult.model_validate(payload["result"])
        if args.recalibrate_session:
            result = recalibrate_session_result(result, args.session_dir)
        args._rescore_source_sha256 = hashlib.sha256(raw).hexdigest()
        args._rescore_allocator_histories = payload.get("allocator_price_histories")
        _score_and_write(result, args)
        return

    if args.mode == "external-validate":
        report = validate_session_bundle(
            args.session_dir,
            score_report=args.score_report,
            min_effective_n=args.min_effective_n,
        )
        print(report.to_markdown())
        if report.status != "PASS":
            raise SystemExit(2)
        return

    if not args.tickers or not args.start or not args.end:
        parser.error("--tickers, --start, and --end are required for this mode")

    start = _parse_date(args.start)
    end = _parse_date(args.end)
    if start >= end:
        parser.error("--start must be before --end")

    dates = _build_dates(start, end, args.interval)
    if not dates:
        parser.error("No as-of dates generated — widen your date range.")

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        parser.error("--tickers is empty")
    if len(set(tickers)) != len(tickers):
        parser.error("--tickers must not contain duplicate symbols")

    if args.mode == "factor":
        if len(tickers) != 1:
            parser.error("--mode factor currently accepts exactly one ticker")
        _run_factor_and_write(tickers[0], start, end, args)
        return

    if args.mode == "cross-sectional":
        if len(tickers) < args.cross_sectional_top_n:
            parser.error("--mode cross-sectional needs at least top_n tickers")
        _run_cross_sectional_and_write(tickers, start, end, args)
        return

    if args.mode == "session-prepare":
        manifest = prepare_session_bundle(
            tickers=tickers,
            as_of_dates=dates,
            output_dir=args.session_dir,
            market=args.market,
            horizon_days=args.horizon,
            lookback_days=args.lookback,
            replay_dir=args.replay_dir,
        )
        print(
            f"Prepared {len(manifest.trials)} session trials in {args.session_dir}."
        )
        print(
            "Have the current session write SessionPrediction JSON objects to "
            f"{args.session_dir / manifest.predictions_file}, then run:"
        )
        print(
            "  stock-analysis-backtest --mode session-score "
            f"--session-dir {args.session_dir}"
        )
        return

    settings = Settings.from_env(
        quick_think_model=args.model,
        deep_think_model=args.debate_model,
        synthesis_model=args.synthesis_model,
        debate_rounds=args.rounds,
    )
    backtester = Backtester(
        settings=settings,
        market=args.market,
        horizon_days=args.horizon,
        lookback_days=args.lookback,
        replay_dir=args.replay_dir,
    )
    args._settings = settings

    print(
        f"Running {len(tickers)} tickers × {len(dates)} dates = "
        f"{len(tickers) * len(dates)} trials. Horizon: {args.horizon}d."
    )

    try:
        result = asyncio.run(
            backtester.run(tickers, dates, resume=False)
        )
    finally:
        backtester.close()
    _score_and_write(result, args)


def _nonoverlapping_trial_subset(
    trials: list[BacktestTrial],
) -> tuple[list[BacktestTrial], list[date]]:
    """Select earliest feasible sealed windows using dates only, never returns."""
    grouped: dict[date, list[BacktestTrial]] = {}
    for trial in trials:
        grouped.setdefault(trial.as_of_date, []).append(trial)
    universe = {trial.ticker.upper() for trial in trials}
    windows: list[tuple[date, date, date]] = []
    for as_of, rows in grouped.items():
        if len(rows) != len(universe) or {row.ticker.upper() for row in rows} != universe:
            raise ValueError(f"Incomplete trial group at {as_of}")
        entries = {row.entry_date or row.as_of_date for row in rows}
        exits = {row.exit_date for row in rows}
        if len(entries) != 1 or len(exits) != 1 or None in exits:
            raise ValueError(f"Unsynchronized trial window at {as_of}")
        windows.append((next(iter(entries)), next(iter(exits)), as_of))

    selected_dates: list[date] = []
    previous_exit: date | None = None
    for entry, exit_, as_of in sorted(windows):
        if previous_exit is None or entry > previous_exit:
            selected_dates.append(as_of)
            previous_exit = exit_
    selected = set(selected_dates)
    return [trial for trial in trials if trial.as_of_date in selected], selected_dates


def _attach_cash_rate_replay(
    result: BacktestResult, args
) -> BacktestResult:
    """Attach explicit FRED DFF observations and their fingerprint."""
    path = getattr(args, "cash_rate_replay", None)
    if path is None:
        return result
    completed = [
        trial
        for trial in result.trials
        if trial.exit_date is not None and trial.realized_return is not None
    ]
    if not completed:
        raise ValueError("Cash-yield diagnostic requires at least one completed trial")
    start_date = min(trial.entry_date or trial.as_of_date for trial in completed)
    end_date = max(trial.exit_date for trial in completed if trial.exit_date is not None)
    observations = load_cash_rate_replay(
        path, start_date=start_date, end_date=end_date
    )
    settings = dict(result.settings)
    settings.update(
        {
            "cash_rate_source": "FRED:DFF",
            "cash_rate_replay_file": path.name,
            "cash_rate_replay_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "cash_rate_return_convention": (
                "daily compounding of end-of-day uninvested cash, ACT/365; use the "
                "latest FRED:DFF observation whose available_as_of is not after "
                "the accrual date; carry at most four calendar days"
            ),
        }
    )
    return result.model_copy(
        update={"cash_rate_path": observations, "settings": settings}
    )


def _score_and_write(result, args) -> None:
    result = _attach_cash_rate_replay(result, args)
    cost_bps = getattr(args, "cost_bps", 0.0) or 0.0
    report = Scorer.score(result, cost_bps_per_side=cost_bps)
    markdown = Scorer.to_markdown(result, report)

    portfolio_config = PortfolioConfig(
        starting_balance=args.starting_balance,
        position_size_pct=args.position_size,
        allow_short=args.allow_short,
        cost_bps_per_side=cost_bps,
    )
    portfolio_report = portfolio_mod.simulate(result, portfolio_config)
    portfolio_md = portfolio_mod.to_markdown(portfolio_report)
    markdown += "\n" + portfolio_md

    settings = getattr(args, "_settings", None) or Settings.from_env()
    trial_allocation_report = None
    trial_allocation_error = None
    trial_allocation_scope = {"kind": "full_panel", "research_only": False}
    signal_ablation_report = None
    signal_ablation_error = None
    ablation_trials = result.trials
    allocator_histories_payload = None
    try:
        price_histories = _load_allocator_price_histories(result, args, settings)
        allocator_histories_payload = _freeze_allocator_histories(price_histories, result)
        price_histories = {
            ticker: pd.DataFrame(rows)
            for ticker, rows in allocator_histories_payload.items()
        }
        allocation_config = CrossSectionalConfig(
            lookback_months=args.cross_sectional_lookback_months,
            top_n=args.cross_sectional_top_n,
            cost_bps_per_side=cost_bps,
        )
        try:
            trial_allocation_report = run_cross_sectional_trial_backtest(
                price_histories,
                result.trials,
                config=allocation_config,
            )
        except OverlappingSealedWindowsError as exc:
            ablation_trials, selected_dates = _nonoverlapping_trial_subset(result.trials)
            trial_allocation_report = run_cross_sectional_trial_backtest(
                price_histories,
                ablation_trials,
                config=allocation_config,
            )
            trial_allocation_error = f"full panel unavailable: {exc}"
            trial_allocation_scope = {
                "kind": "nonoverlap_subset_diagnostic",
                "research_only": True,
                "selected_as_of_dates": [day.isoformat() for day in selected_dates],
                "selected_trials": len(ablation_trials),
                "total_trials": len(result.trials),
            }
            markdown += (
                "\n> **[Status: Warning]** Sealed-trial allocation and AI ablation below "
                f"use a deterministic non-overlapping subset ({len(selected_dates)} "
                f"dates, {len(ablation_trials)}/{len(result.trials)} trials). "
                "The full panel is still used for the primary pipeline/hold score; "
                "the subset is research-only and cannot satisfy its promotion gate.\n"
            )
        markdown += "\n" + trial_allocation_to_markdown(trial_allocation_report)
        try:
            signal_ablation_report = run_signal_ablation(
                ablation_trials,
                trial_allocation_report.period_log,
                config=SignalAblationConfig(
                    top_n=allocation_config.top_n,
                    cost_bps_per_side=allocation_config.cost_bps_per_side,
                    bootstrap_block_periods=allocation_config.bootstrap_block_periods,
                    bootstrap_resamples=allocation_config.bootstrap_resamples,
                    bootstrap_seed=allocation_config.bootstrap_seed,
                ),
            )
            markdown += "\n" + signal_ablation_to_markdown(signal_ablation_report)
        except ValueError as exc:
            signal_ablation_error = str(exc)
            logger.warning("Sealed-trial AI signal ablation unavailable: %s", exc)
            markdown += f"\n## AI Signal Ablation\n\n> **[Status: Warning]** Not computed: {exc}\n"
    except (FileNotFoundError, ValueError) as exc:
        trial_allocation_error = str(exc)
        logger.warning("Sealed-trial allocator unavailable: %s", exc)
        signal_ablation_error = (
            f"not run because the sealed-trial allocator is unavailable: {exc}"
        )
        markdown += (
            "\n## Sealed-Trial Cross-Sectional Allocation\n\n"
            f"> **[Status: Warning]** Not computed: {exc}\n"
        )
        markdown += (
            "\n## AI Signal Ablation\n\n"
            f"> **[Status: Warning]** Not computed: {signal_ablation_error}\n"
        )

    result_payload = result.model_dump(mode="json")
    portfolio_payload = portfolio_report.model_dump(mode="json")
    trial_allocation_payload = (
        trial_allocation_report.model_dump(mode="json")
        if trial_allocation_report is not None
        else None
    )
    signal_ablation_payload = (
        signal_ablation_report.model_dump(mode="json")
        if signal_ablation_report is not None
        else None
    )
    experiment_config = {
        "market": result.settings.get("market", getattr(args, "market", None)),
        "requested_start": getattr(args, "start", None),
        "requested_end": getattr(args, "end", None),
        "interval": getattr(args, "interval", None) if args.mode == "api" else None,
        "horizon_days": result.settings.get("horizon_days", getattr(args, "horizon", None)),
        "lookback_days": result.settings.get("lookback_days", getattr(args, "lookback", None)),
        "cost_bps_per_side": cost_bps,
        "resume_enabled": False,
        "rescore_source_sha256": getattr(args, "_rescore_source_sha256", None),
        "allocator_histories_sha256": (
            hashlib.sha256(
                json.dumps(allocator_histories_payload, sort_keys=True).encode()
            ).hexdigest()
            if allocator_histories_payload is not None
            else None
        ),
        "portfolio": portfolio_report.config.model_dump(mode="json"),
        "portfolio_comparison_strategies": [
            strategy.strategy for strategy in portfolio_report.strategies
        ],
        "sealed_trial_allocator": {
            "lookback_months": getattr(args, "cross_sectional_lookback_months", 12),
            "top_n": getattr(args, "cross_sectional_top_n", 3),
            "cost_bps_per_side": cost_bps,
            "trial_selection": trial_allocation_scope,
        },
        "signal_ablation": (
            signal_ablation_report.config.model_dump(mode="json")
            if signal_ablation_report is not None
            else None
        ),
    }
    experiment_record = build_experiment_record(
        mode=getattr(args, "mode", "api"),
        result=result_payload,
        score_report=report.model_dump(mode="json"),
        portfolio=portfolio_payload,
        cross_sectional_trial_allocation=trial_allocation_payload,
        signal_ablation=signal_ablation_payload,
        config=experiment_config,
        diagnostics={
            "sealed_trial_allocator": {
                "status": "scored" if trial_allocation_report is not None else "unavailable",
                "error": trial_allocation_error,
                "scope": trial_allocation_scope,
            },
            "signal_ablation": {
                "status": "scored" if signal_ablation_report is not None else "unavailable",
                "error": signal_ablation_error,
            },
        },
        session_dir=(args.session_dir if getattr(args, "mode", None) == "session-score" else None),
    )
    ledger_path = getattr(args, "experiment_ledger", None) or Path("backtest_experiments.jsonl")
    experiment_record = append_experiment_record(ledger_path, experiment_record)
    quality_analysis = analyze_backtest(
        mode=getattr(args, "mode", "api"),
        portfolio=portfolio_payload,
        score=report.model_dump(mode="json"),
        result=result_payload,
        signal_ablation=signal_ablation_payload,
        ledger=experiment_record,
    )
    family_counts: dict[str, int] = {}
    for arm in experiment_record["candidate_arms"]:
        family_counts[arm["family"]] = family_counts.get(arm["family"], 0) + 1
    family_summary = ", ".join(
        f"{family}={count}" for family, count in sorted(family_counts.items())
    )
    markdown += (
        "\n## Experiment Ledger\n\n"
        f"- Appended run `{experiment_record['run_id']}` as ledger row "
        f"{experiment_record['ledger']['sequence']} to `{ledger_path}`.\n"
        f"- Tested arms this run: {experiment_record['candidate_arms_tested_in_run']}"
        f" ({family_summary}); unique strategy configs: "
        f"{experiment_record['ledger']['unique_candidate_count_after']}; distinct scored "
        f"evaluations: {experiment_record['ledger']['unique_candidate_evaluation_count_after']}.\n"
        f"- New / repeated evaluation arms this run: "
        f"{experiment_record['ledger']['new_evaluation_arms_in_run']} / "
        f"{experiment_record['ledger']['reused_evaluation_arms_in_run']}.\n"
        "- The portfolio count includes benchmark/diagnostic rows to match the current-run "
        "DSR denominator.\n"
        "- Cross-run DSR adjustment is not applied. Counts begin with this ledger's "
        "first row; earlier/manual searches are not reconstructed.\n"
    )
    markdown += "\n" + quality_to_markdown(quality_analysis)

    payload = {
        "result": result_payload,
        "report": report.model_dump(mode="json"),
        "portfolio": portfolio_payload,
        "allocator_price_histories": allocator_histories_payload,
        "cross_sectional_trial_allocation": trial_allocation_payload,
        "cross_sectional_trial_allocation_error": trial_allocation_error,
        "cross_sectional_trial_allocation_scope": trial_allocation_scope,
        "signal_ablation": signal_ablation_payload,
        "signal_ablation_error": signal_ablation_error,
        "experiment": experiment_record,
        "quality_analysis": quality_analysis,
    }

    if settings.storage_backend == "supabase" and args.mode != "rescore":
        store = build_store(settings)
        try:
            artifact_id = store.save_backtest_artifact(
                mode="api",
                tickers=sorted({trial.ticker for trial in result.trials}),
                payload=payload,
                markdown=markdown,
                metadata={
                    "output": args.output,
                    "cost_bps_per_side": cost_bps,
                    "experiment_run_id": experiment_record["run_id"],
                    "experiment_ledger_sequence": experiment_record["ledger"]["sequence"],
                },
            )
        finally:
            close = getattr(store, "close", None)
            if close:
                close()
        print()
        print(markdown)
        print(f"Cloud artifact: {artifact_id}")
        print(
            f"Experiment ledger: {ledger_path} "
            f"(row {experiment_record['ledger']['sequence']}; "
            f"{experiment_record['candidate_arms_tested_in_run']} arms this run; "
            f"{experiment_record['ledger']['unique_candidate_count_after']} configs, "
            f"{experiment_record['ledger']['unique_candidate_evaluation_count_after']} evaluations in ledger)"
        )
    else:
        out_json = Path(f"{args.output}.json")
        out_md = Path(f"{args.output}.md")
        out_json.write_text(json.dumps(payload, indent=2))
        out_md.write_text(markdown)
        print()
        print(markdown)
        print(f"Raw results: {out_json}")
        print(f"Report:      {out_md}")
        print(
            f"Experiment ledger: {ledger_path} "
            f"(row {experiment_record['ledger']['sequence']}; "
            f"{experiment_record['candidate_arms_tested_in_run']} arms this run; "
            f"{experiment_record['ledger']['unique_candidate_count_after']} configs, "
            f"{experiment_record['ledger']['unique_candidate_evaluation_count_after']} evaluations in ledger)"
        )

    print()

    if getattr(args, "record_outcomes", False):
        outcome_store = build_outcome_store(settings)
        try:
            written = outcome_store.append(records_from_backtest(result))
            for ticker in sorted({t.ticker for t in result.trials}):
                outcome_store.save_calibration(ticker)
        finally:
            close = getattr(outcome_store, "close", None)
            if close:
                close()
        destination = "Supabase" if settings.storage_backend == "supabase" else f"{args.data_dir}/<TICKER>/outcomes.jsonl"
        print(f"Outcomes:    +{written} record(s) into {destination}")


def _load_allocator_price_histories(result, args, settings) -> dict[str, pd.DataFrame]:
    """Load the fixed-universe histories used by the sealed-trial allocator."""

    if getattr(args, "mode", None) == "rescore":
        frozen = getattr(args, "_rescore_allocator_histories", None)
        if not isinstance(frozen, dict):
            raise ValueError(
                "rescore input lacks frozen allocator histories; "
                "sealed allocator/ablation cannot be recomputed without new price reads"
            )
        return {ticker: pd.DataFrame(rows) for ticker, rows in frozen.items()}

    tickers = sorted({trial.ticker.upper() for trial in result.trials})
    if settings.storage_backend == "supabase":
        store = build_store(settings)
        try:
            return {
                ticker: pd.DataFrame(
                    [bar.model_dump(mode="json") for bar in store.load_price_history(ticker)]
                )
                for ticker in tickers
            }
        finally:
            close = getattr(store, "close", None)
            if close:
                close()

    return {
        ticker: load_price_history(Path(args.data_dir) / ticker / "price_history.csv")
        for ticker in tickers
    }


def _freeze_allocator_histories(
    histories: dict[str, pd.DataFrame], result: BacktestResult
) -> dict[str, list[dict[str, str | float]]]:
    """Serialize exactly the as-of price panel used for allocator ranking."""

    if not result.trials:
        raise ValueError("allocator requires at least one trial")
    cutoff = max(trial.as_of_date for trial in result.trials)
    frozen: dict[str, list[dict[str, str | float]]] = {}
    for ticker, frame in sorted(histories.items()):
        cleaned = clean_price_history(frame)
        cleaned = cleaned[cleaned["date"].dt.date <= cutoff]
        if cleaned.empty:
            raise ValueError(f"No allocator history on or before {cutoff}: {ticker}")
        frozen[ticker] = [
            {
                "date": row.date.date().isoformat(),
                "open": float(row.open),
                "close": float(row.close),
            }
            for row in cleaned.itertuples(index=False)
        ]
    return frozen


def _run_factor_and_write(ticker: str, start: date, end: date, args) -> None:
    config = FactorConfig(
        lookback_bars=args.factor_lookback_bars,
        holding_bars=args.factor_holding_bars,
        initial_train_bars=args.walk_forward_train_bars,
        test_window_bars=args.walk_forward_test_bars,
        cost_bps_per_side=args.cost_bps,
    )
    settings = Settings.from_env()
    store = build_store(settings)
    if settings.storage_backend == "supabase":
        price_history = pd.DataFrame(
            [bar.model_dump(mode="json") for bar in store.load_price_history(ticker)]
        )
    else:
        price_path = Path(args.data_dir) / ticker / "price_history.csv"
        price_history = load_price_history(price_path)
    report = run_factor_backtest(
        ticker,
        price_history,
        start=start,
        end=end,
        config=config,
    )
    experiment_record = _append_standalone_experiment(
        "factor", report.model_dump(mode="json"), {ticker: price_history}, args
    )
    markdown = factor_to_markdown(report)
    output_prefix = args.output if args.output != "backtest_report" else "factor_report"
    quality_analysis = analyze_backtest(
        mode="factor", report=report.model_dump(mode="json"), ledger=experiment_record
    )
    markdown += "\n" + quality_to_markdown(quality_analysis)
    markdown += "\n" + _standalone_ledger_markdown(experiment_record, args)
    try:
        if settings.storage_backend == "supabase":
            artifact_id = store.save_backtest_artifact(
                mode="factor",
                tickers=[ticker],
                payload={
                    "report": report.model_dump(mode="json"),
                    "quality_analysis": quality_analysis,
                },
                markdown=markdown,
                metadata={"output": output_prefix},
            )
            print(markdown)
            print(f"Cloud artifact: {artifact_id}")
        else:
            out_json = Path(f"{output_prefix}.json")
            out_md = Path(f"{output_prefix}.md")
            out_quality = Path(f"{output_prefix}.quality.json")
            out_json.write_text(report.model_dump_json(indent=2))
            out_md.write_text(markdown)
            out_quality.write_text(json.dumps(quality_analysis, indent=2))
            print(markdown)
            print(f"Raw results: {out_json}")
            print(f"Report:      {out_md}")
            print(f"Quality:     {out_quality}")
    finally:
        close = getattr(store, "close", None)
        if close:
            close()


def _run_cross_sectional_and_write(
    tickers: list[str], start: date, end: date, args
) -> None:
    config = CrossSectionalConfig(
        lookback_months=args.cross_sectional_lookback_months,
        top_n=args.cross_sectional_top_n,
        cost_bps_per_side=args.cost_bps,
    )
    settings = Settings.from_env()
    store = build_store(settings)
    try:
        if settings.storage_backend == "supabase":
            price_histories = {
                ticker: pd.DataFrame(
                    [bar.model_dump(mode="json") for bar in store.load_price_history(ticker)]
                )
                for ticker in tickers
            }
        else:
            price_histories = {
                ticker: load_price_history(Path(args.data_dir) / ticker / "price_history.csv")
                for ticker in tickers
            }

        report = run_cross_sectional_backtest(
            price_histories,
            start=start,
            end=end,
            config=config,
        )
        experiment_record = _append_standalone_experiment(
            "cross-sectional", report.model_dump(mode="json"), price_histories, args
        )
        markdown = cross_sectional_to_markdown(report)
        quality_analysis = analyze_backtest(
            mode="cross-sectional",
            report=report.model_dump(mode="json"),
            ledger=experiment_record,
        )
        markdown += "\n" + quality_to_markdown(quality_analysis)
        markdown += "\n" + _standalone_ledger_markdown(experiment_record, args)
        output_prefix = (
            args.output if args.output != "backtest_report" else "cross_sectional_report"
        )
        payload = {
            "report": report.model_dump(mode="json"),
            "quality_analysis": quality_analysis,
        }
        if settings.storage_backend == "supabase":
            artifact_id = store.save_backtest_artifact(
                mode="cross-sectional",
                tickers=report.universe,
                payload=payload,
                markdown=markdown,
                metadata={"output": output_prefix},
            )
            print(markdown)
            print(f"Cloud artifact: {artifact_id}")
        else:
            out_json = Path(f"{output_prefix}.json")
            out_md = Path(f"{output_prefix}.md")
            out_quality = Path(f"{output_prefix}.quality.json")
            out_json.write_text(report.model_dump_json(indent=2))
            out_md.write_text(markdown)
            out_quality.write_text(json.dumps(quality_analysis, indent=2))
            print(markdown)
            print(f"Raw results: {out_json}")
            print(f"Report:      {out_md}")
            print(f"Quality:     {out_quality}")
    finally:
        close = getattr(store, "close", None)
        if close:
            close()


def _append_standalone_experiment(mode: str, report: dict, histories: dict, args) -> dict:
    digest = hashlib.sha256()
    for ticker, frame in sorted(histories.items()):
        cleaned = clean_price_history(frame)
        digest.update(ticker.encode() + b"\0")
        digest.update(cleaned.to_json(orient="records", date_format="iso").encode())
    record = build_standalone_record(
        mode=mode,
        report=report,
        price_histories_sha256=digest.hexdigest(),
    )
    ledger_path = getattr(args, "experiment_ledger", None) or Path("backtest_experiments.jsonl")
    return append_experiment_record(ledger_path, record)


def _standalone_ledger_markdown(record: dict, args) -> str:
    path = getattr(args, "experiment_ledger", None) or Path("backtest_experiments.jsonl")
    return (
        "## Experiment Ledger\n\n"
        f"- Appended run `{record['run_id']}` as row {record['ledger']['sequence']} to `{path}`.\n"
        f"- Recorded candidate arms so far: {record['ledger']['unique_candidate_count_after']}; "
        "pre-ledger and manual searches are not reconstructed, and cross-run DSR is not applied.\n"
        f"- New / repeated evaluation arms this run: "
        f"{record['ledger']['new_evaluation_arms_in_run']} / "
        f"{record['ledger']['reused_evaluation_arms_in_run']}.\n"
    )


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _build_dates(start: date, end: date, interval: str) -> list[date]:
    step = {
        "weekly": 7,
        "biweekly": 14,
        "monthly": 30,
        "quarterly": 91,
    }[interval]
    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=step)
    return dates


if __name__ == "__main__":
    cli()
