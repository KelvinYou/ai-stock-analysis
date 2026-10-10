"""Immutable nine-view forward research cohorts; outcome reads require maturity."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from stock_analysis.backtest import stats
from stock_analysis.backtest.runner import Backtester
from stock_analysis.config import Settings
from stock_analysis.portfolio import (
    PORTFOLIO_ARMS,
    PortfolioBundle,
    PortfolioPlan,
    build_portfolio_plan,
    implementation_identity,
    implementation_runtime,
)

NY = ZoneInfo("America/New_York")


def _now():
    return datetime.now(UTC)


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def freeze_cohort(bundle: PortfolioBundle, protocol: dict, output: Path, *, now=None):
    now = now or _now()
    local = now.astimezone(NY)
    if bundle.as_of_date != local.date() or local.time() < time(16) or local.weekday() >= 5:
        raise ValueError("Freeze only after the decision session closes, on its actual date")
    plan = build_portfolio_plan(bundle)
    if plan.status != "ready" or plan.data_as_of != bundle.as_of_date:
        raise ValueError("Forward collection requires a ready, completed same-session panel")
    for snapshot in bundle.snapshots:
        captured = snapshot.ticker_data.fetched_at
        if captured.tzinfo is None:
            raise ValueError("Forward capture requires an explicit timezone, not a legacy naive clock")
        if (captured > now or captured.astimezone(NY).date() != bundle.as_of_date
            or captured.astimezone(NY).time() < time(16)):
            raise ValueError("Forward input must have been captured after the completed session")
    anchors = protocol.get("anchors", [])
    decisions = protocol.get("decision_sessions", {})
    if decisions:
        if set(decisions) != set(anchors) or not protocol.get("calendar_provenance"):
            raise ValueError("Pin the complete decision-session calendar and its provenance")
        for anchor, session in decisions.items():
            if not 0 <= (date.fromisoformat(anchor) - date.fromisoformat(session)).days <= 4:
                raise ValueError("Decision session must be on or just before its fixed anchor")
    registered_dates = list(decisions.values()) if decisions else anchors
    if protocol.get("activation_required") and (
        not decisions or not protocol.get("model_provenance") or not protocol.get("prompt_provenance")
    ):
        raise ValueError("Prepared protocol needs pinned calendar, model and prompt provenance before collection")
    if (protocol.get("version") != 2 or protocol.get("horizon_calendar_days") != 30
        or set(protocol.get("arms", [])) != set(PORTFOLIO_ARMS)
        or sorted(protocol.get("universe", [])) != sorted(plan.run_ids)
        or str(bundle.as_of_date) not in registered_dates
        or protocol.get("cost_bps_per_side") != [0, 10, 20]):
        raise ValueError("Cohort differs from the registered v2 universe, calendar, arms or costs")
    allocator = protocol.get("allocator", protocol)
    if allocator.get("lookback_months", 12) != 12 or allocator.get("top_n", 3) != 3:
        raise ValueError("Cohort differs from registered allocator rules")
    if (allocator.get("sleeve_weight", 1 / 3) != 1 / 3
        or protocol.get("cash_primary_annual_return", 0) != 0
        or protocol.get("allow_short", False) is not False
        or protocol.get("continuous_hold_weight", 1 / len(plan.run_ids)) != 1 / len(plan.run_ids)
        or protocol.get("ft_confidence_weights", {"high": 1, "medium": 0.75, "low": 0.5})
            != {"high": 1, "medium": 0.75, "low": 0.5}):
        raise ValueError("Cohort differs from registered cash, weights or long-only rules")
    if protocol.get("specification_sha256"):
        root = Path(__file__).resolve().parents[2]
        spec = (root / protocol["specification"]).resolve()
        if not spec.is_relative_to(root) or _hash(spec) != protocol["specification_sha256"]:
            raise ValueError("Registered specification changed")
    output.mkdir(parents=True, exist_ok=False)
    _write(output / "bundle.json", bundle.model_dump(mode="json"))
    _write(output / "plan.json", plan.model_dump(mode="json"))
    _write(output / "protocol.json", protocol)
    package = Path(__file__).resolve().parent
    frozen_package = output / "implementation" / "stock_analysis"
    for source in sorted(package.rglob("*.py")):
        target = frozen_package / source.relative_to(package)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
    if implementation_identity(frozen_package) != plan.implementation_sha256:
        raise ValueError("Implementation changed while freezing; retain this partial capture for audit")
    manifest = {
        "version": 2, "scope": "prospective_research_only", "frozen_at_utc": now.isoformat(),
        "as_of_date": str(bundle.as_of_date), "horizon_days": 30,
        "exit_target": str(bundle.as_of_date + timedelta(days=30)),
        "score_not_before_utc": str(bundle.as_of_date + timedelta(days=31)),
        "plan_id": plan.plan_id, "protocol_sha256": _hash(output / "protocol.json"),
        "implementation_sha256": plan.implementation_sha256,
        "runtime_versions": implementation_runtime(),
        "hashes": {str(path.relative_to(output)): _hash(path)
                   for path in sorted(output.rglob("*")) if path.is_file()},
        "provider_confirmation": False, "promotion_ready": False,
        "missing_promotion_evidence": ["authenticated_provider_attestation", "verified_total_returns",
                                       "broker_calibrated_costs", "mature_independent_forward_sample"],
    }
    _write(output / "manifest.json", manifest)
    (output / "manifest.sha256").open("x").write(_hash(output / "manifest.json") + "\n")
    return manifest


def verify_cohort(folder: Path):
    manifest_path = folder / "manifest.json"
    if _hash(manifest_path) != (folder / "manifest.sha256").read_text().strip():
        raise ValueError("Frozen manifest changed")
    manifest = json.loads(manifest_path.read_text())
    for name, digest in manifest["hashes"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or _hash(path) != digest:
            raise ValueError(f"Frozen cohort artifact changed: {name}")
    return manifest


def score_cohort(folder: Path):
    manifest = verify_cohort(folder)
    if manifest["implementation_sha256"] != implementation_identity():
        raise ValueError("Scoring requires the frozen implementation and numerical runtime")
    today = _now().date()
    if today < date.fromisoformat(manifest["score_not_before_utc"]):
        raise ValueError("Cohort not mature; no outcome fetch allowed")
    if (folder / "score.json").exists():
        raise FileExistsError("Cohort is already scored; original outcomes are immutable")
    plan = PortfolioPlan.model_validate_json((folder / "plan.json").read_text())
    as_of = plan.as_of_date
    runner = Backtester(Settings(storage_backend="local"), market="US", horizon_days=30)
    histories = {}
    for ticker in sorted(plan.run_ids):
        histories[ticker] = runner._fetch_price_series(
            ticker, as_of - timedelta(days=7), min(today, as_of + timedelta(days=41)),
        )
    return score_with_histories(folder, histories, today=today)


def score_with_histories(folder: Path, histories: dict, *, today: date):
    """Deterministic scoring seam; public CLI always supplies completed provider bars."""
    manifest = verify_cohort(folder)
    if manifest["implementation_sha256"] != implementation_identity():
        raise ValueError("Scoring requires the frozen implementation and numerical runtime")
    if (folder / "score.json").exists():
        raise FileExistsError("Cohort is already scored; original outcomes are immutable")
    if today < date.fromisoformat(manifest["score_not_before_utc"]):
        raise ValueError("Cohort not mature")
    plan = PortfolioPlan.model_validate_json((folder / "plan.json").read_text())
    runner = Backtester(Settings(storage_backend="local"), market="US", horizon_days=30)
    returns, fills, paths = {}, {}, {}
    for ticker in sorted(plan.run_ids):
        history = histories[ticker]
        bars = runner._price_bars(history)
        if (not history.index.is_monotonic_increasing or not history.index.is_unique
            or len(bars) != len(history)):
            raise ValueError("Outcome history must be ordered, unique and contain valid daily bars")
        entry, entered = runner._price_on_or_after(history, plan.as_of_date + timedelta(days=1), price_column="Open")
        exit_, exited = runner._price_on_or_after(history, date.fromisoformat(manifest["exit_target"]))
        if entry is None or exit_ is None or entered is None or exited is None or exited >= today:
            raise ValueError("Incomplete or not fully completed outcome; keep the fixed panel")
        if not (math.isfinite(entry) and math.isfinite(exit_) and entry > 0 and exit_ > 0):
            raise ValueError("Invalid outcome price")
        fills[ticker] = {"entry_price": entry, "exit_price": exit_,
                         "entry_date": str(entered), "exit_date": str(exited)}
        returns[ticker] = exit_ / entry - 1
        paths[ticker] = [bar.model_dump(mode="json") for bar in bars]
    entries = {row["entry_date"] for row in fills.values()}
    exits = {row["exit_date"] for row in fills.values()}
    if len(entries) != 1 or len(exits) != 1:
        raise ValueError("Cohort outcomes must have synchronized common-session fills")
    arms = {}
    for bps in (0, 10, 20):
        multiplier = (1 - bps / 10000) ** 2
        arms[str(bps)] = {
            view.strategy: sum(weight * ((1 + returns[ticker]) * multiplier - 1)
                               for ticker, weight in view.weights.items())
            for view in plan.arms
        }
    payload = {"manifest_sha256": _hash(folder / "manifest.json"), "plan_id": plan.plan_id,
               "protocol_sha256": manifest["protocol_sha256"], "as_of_date": str(plan.as_of_date),
               "fills": fills, "price_paths": paths, "arms": arms,
               "scored_at_utc": _now().isoformat(), "promotion_ready": False,
               "price_basis": "provider_adjusted_OHLC_not_verified_total_returns"}
    _write(folder / "score.json", payload)
    (folder / "score.sha256").open("x").write(_hash(folder / "score.json") + "\n")
    return payload


def _daily_curves(rows, plans, bps):
    """Mark fixed shares daily, retain cash gaps, charge only actual entry/exit legs."""
    tickers = sorted(plans[0].run_ids)
    prices = {ticker: {} for ticker in tickers}
    for _, score in rows:
        for ticker in tickers:
            for bar in score["price_paths"][ticker]:
                day, close = bar["date"], bar["close"]
                if not math.isfinite(close) or close <= 0:
                    raise ValueError("Invalid daily outcome price")
                previous = prices[ticker].get(day)
                if previous is not None and not math.isclose(previous, close, rel_tol=1e-10):
                    raise ValueError("Overlapping outcome histories changed price basis")
                prices[ticker][day] = close
    first = rows[0][1]["fills"]
    start = next(iter(first.values()))["entry_date"]
    end = next(iter(rows[-1][1]["fills"].values()))["exit_date"]
    dates = sorted(day for day in set.intersection(*(set(p) for p in prices.values()))
                   if start <= day <= end)
    union = {day for values in prices.values() for day in values if start <= day <= end}
    if set(dates) != union:
        raise ValueError("Incomplete fixed daily panel; do not drop missing ticker sessions")
    if not dates or dates[0] != start or dates[-1] != end:
        raise ValueError("Missing common daily price panel")
    entries = {next(iter(score["fills"].values()))["entry_date"]: (score, plan)
               for (_, score), plan in zip(rows, plans, strict=True)}
    fee = 1 - bps / 10000
    curves = {}
    for name in PORTFOLIO_ARMS:
        cash, shares, active_exit, values = 1.0, {}, None, []
        if name == "continuous_strict_hold":
            cash = 0.0
            shares = {ticker: fee / len(tickers) / first[ticker]["entry_price"] for ticker in tickers}
            active_exit = end
        for day in dates:
            if name != "continuous_strict_hold" and day in entries:
                score, plan = entries[day]
                view = next(view for view in plan.arms if view.strategy == name)
                capital = cash
                shares = {ticker: capital * weight * fee / score["fills"][ticker]["entry_price"]
                          for ticker, weight in view.weights.items()}
                cash = capital * view.cash_weight
                active_exit = next(iter(score["fills"].values()))["exit_date"]
            marked = sum(quantity * prices[ticker][day] for ticker, quantity in shares.items())
            if day == active_exit:
                cash += marked * fee
                shares = {}
                marked = 0.0
            values.append(cash + marked)
        curves[name] = values
    return dates, curves


def compare_cohorts(folders: list[Path]):
    """Compare fixed sleeves and continuous hold without selling hold in episode gaps."""
    rows, protocols, seen_dates, plans_by_id = [], set(), set(), {}
    for folder in folders:
        manifest = verify_cohort(folder)
        if manifest["implementation_sha256"] != implementation_identity():
            raise ValueError("Comparison requires the frozen implementation and numerical runtime")
        if _hash(folder / "score.json") != (folder / "score.sha256").read_text().strip():
            raise ValueError("Scored outcome changed")
        score = json.loads((folder / "score.json").read_text())
        if (score["manifest_sha256"] != _hash(folder / "manifest.json")
            or score["protocol_sha256"] != manifest["protocol_sha256"]
            or score["plan_id"] != manifest["plan_id"]):
            raise ValueError("Score manifest binding mismatch")
        plans_by_id[manifest["plan_id"]] = PortfolioPlan.model_validate_json((folder / "plan.json").read_text())
        protocols.add(manifest["protocol_sha256"])
        if manifest["as_of_date"] in seen_dates:
            raise ValueError("Duplicate cohort date")
        seen_dates.add(manifest["as_of_date"])
        rows.append((manifest, score))
    if len(protocols) != 1 or not rows:
        raise ValueError("Comparison requires one frozen protocol")
    rows.sort(key=lambda row: row[0]["as_of_date"])
    plans = [plans_by_id[manifest["plan_id"]] for manifest, _ in rows]
    windows, previous_exit = [], None
    for _, score in rows:
        fill = next(iter(score["fills"].values()))
        entry, exit_ = date.fromisoformat(fill["entry_date"]), date.fromisoformat(fill["exit_date"])
        if previous_exit is not None and entry <= previous_exit:
            raise ValueError("Forward episode windows overlap")
        windows.append(("portfolio", entry, exit_))
        previous_exit = exit_
    effective_n = stats.effective_sample_size(windows)
    first = rows[0][1]["fills"]
    result = {"effective_n": effective_n, "n_strategies_tested": 9,
              "promotion_ready": False, "scope": "forward_research_only", "costs": {},
              "limits": ["Assumed fees and provider returns", "No authenticated provider attestation",
                         "Partial checkpoints do not permit promotion", "All-history search not reconstructed"]}
    for bps in (0, 10, 20):
        days, curves = _daily_curves(rows, plans, bps)
        daily_returns = {name: [equity / previous - 1
                              for equity, previous in zip(values, [1.0, *values[:-1]], strict=True)]
                         for name, values in curves.items()}
        series = {name: [score["arms"][str(bps)][name] for _, score in rows]
                  for name in PORTFOLIO_ARMS}
        previous_equity = 1.0
        hold_series = []
        for index, (_, score) in enumerate(rows):
            equity = sum(score["fills"][ticker]["exit_price"] / first[ticker]["entry_price"]
                         for ticker in first) / len(first) * (1 - bps / 10000)
            if index == len(rows) - 1:
                equity *= 1 - bps / 10000
            hold_series.append(equity / previous_equity - 1)
            previous_equity = equity
        series["continuous_strict_hold"] = hold_series
        sharpes = {name: statistics.mean(values) / statistics.stdev(values)
                   for name, values in series.items()
                   if len(values) >= 2 and statistics.stdev(values) > 0}
        variance = statistics.variance(sharpes.values()) if len(sharpes) > 1 else 0
        reports = []
        for name, values in series.items():
            sr = sharpes.get(name)
            excess = [math.log1p(a) - math.log1p(b)
                      for a, b in zip(values, hold_series, strict=True)]
            reports.append({
                "strategy": name, "net_return": math.prod(1 + r for r in values) - 1,
                "excess_vs_hold": math.prod(1 + r for r in values) - previous_equity,
                "effective_n": effective_n,
                "paired_episode_log_ci_95": stats.moving_block_bootstrap_ci(
                    excess, block_length=3, n_resamples=2000, seed=0),
                "paired_daily_log_ci_95": stats.moving_block_bootstrap_ci(
                    [math.log1p(a) - math.log1p(b) for a, b in zip(
                        daily_returns[name], daily_returns["continuous_strict_hold"], strict=True)],
                    block_length=21, n_resamples=2000, seed=0),
                "excess_vs_allocator": math.prod(1 + r for r in values)
                    - math.prod(1 + r for r in series["allocator_only"]),
                "paired_daily_log_ci_vs_allocator_95": stats.moving_block_bootstrap_ci(
                    [math.log1p(a) - math.log1p(b) for a, b in zip(
                        daily_returns[name], daily_returns["allocator_only"], strict=True)],
                    block_length=21, n_resamples=2000, seed=0),
                "max_drawdown": min(equity / max(1.0, *curves[name][:index + 1]) - 1
                                    for index, equity in enumerate(curves[name])),
                "daily_equity": [{"date": day, "equity": equity}
                                 for day, equity in zip(days, curves[name], strict=True)],
                "deflated_sharpe": None if sr is None else stats.deflated_sharpe_ratio(
                    sr, int(effective_n), stats.skewness(values), stats.kurtosis(values), 9, variance),
            })
            if not math.isclose(curves[name][-1], math.prod(1 + r for r in values), rel_tol=1e-10):
                raise ValueError("Daily/episode return reconciliation failed")
        result["costs"][str(bps)] = reports
    return result


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "export", "freeze", "verify", "score", "compare"])
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--run-ids", help="Comma-separated completed cloud run UUIDs")
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cohort", type=Path)
    parser.add_argument("--cohorts", nargs="+", type=Path)
    args = parser.parse_args()
    if args.action in {"plan", "export", "freeze"}:
        if bool(args.bundle) == bool(args.run_ids):
            parser.error("Provide exactly one of --bundle or --run-ids")
        if args.bundle:
            bundle = PortfolioBundle.model_validate_json(args.bundle.read_text())
        else:
            from stock_analysis.api.portfolio_data import load_portfolio_bundle
            bundle = load_portfolio_bundle(Settings.from_env(), args.run_ids.split(","))
        if args.action == "freeze":
            if not args.protocol or not args.cohort:
                parser.error("freeze requires --protocol and --cohort")
            value = freeze_cohort(bundle, json.loads(args.protocol.read_text()), args.cohort)
        else:
            if not args.output:
                parser.error("plan/export requires --output")
            value = (bundle if args.action == "export" else build_portfolio_plan(bundle)).model_dump(mode="json")
            _write(args.output, value)
    elif args.action == "compare":
        if not args.cohorts or not args.output:
            parser.error("compare requires --cohorts and --output")
        value = compare_cohorts(args.cohorts)
        _write(args.output, value)
    else:
        if not args.cohort:
            parser.error("verify/score requires --cohort")
        value = verify_cohort(args.cohort) if args.action == "verify" else score_cohort(args.cohort)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    cli()
